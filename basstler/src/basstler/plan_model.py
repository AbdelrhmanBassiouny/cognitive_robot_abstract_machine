"""
The parts of a plan's data model that more than one tool has to agree on.

Nothing here imports anything the tools reading it do not already have: the dashboard
build imports jinja2 and markdown of its own, and the bootstrap tool imports neither.
The dependency runs one way only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ItemStatus(StrEnum):
    """
    The statuses ``plan.yaml``'s ``status`` field accepts.

    Deliberately thin: everything about a pull request's actual GitHub state - open,
    draft, merged, its checks, its reviews - is never stored in the manifest. It is
    live-fetched and represented separately.
    """

    NOT_STARTED = "not started"
    """
    Nothing has begun.
    """

    IN_PROGRESS = "in progress"
    """
    The work is underway - what bootstrapping an item sets.
    """

    BLOCKED = "blocked"
    """
    Something outside the item has to move first.
    """

    DEFERRED = "deferred"
    """
    Deliberately parked rather than stuck.
    """

    DONE = "done"
    """
    Landed.
    """

    @classmethod
    def underscore_spellings(cls) -> dict[str, ItemStatus]:
        """
        The spelling manifests were written in before the values took spaces, which
        ``plan.yaml`` files still carry until they are rewritten.

        :return: Each status by its value with underscores in place of spaces.
        """
        return {status.value.replace(" ", "_"): status for status in cls}

    @classmethod
    def accepted_spellings(cls) -> frozenset[str]:
        """
        :return: Every text a manifest's ``status`` field may hold: each value, and its
            underscore spelling.
        """
        return frozenset(
            {status.value for status in cls} | set(cls.underscore_spellings())
        )

    @classmethod
    def _missing_(cls, value: object) -> ItemStatus | None:
        """
        Read a status from its underscore spelling as well as its value.

        :param value: The text no value matched.
        :return: The status that text spells, or ``None`` when it spells none.
        """
        return cls.underscore_spellings().get(value)


# %% manifest reading


class ManifestField(StrEnum):
    """
    The ``plan.yaml`` keys the typed reading below interprets.
    """

    IDENTIFIER = "id"
    """
    A plan's or an item's id.
    """

    TITLE = "title"
    """
    A plan's or an item's title.
    """

    DESCRIPTION = "description"
    """
    What the plan is for.
    """

    TRACKING_ISSUE = "tracking_issue"
    """
    The issue structural changes to the plan are recorded on.
    """

    ITEMS = "items"
    """
    The plan's list of items.
    """

    BRANCH = "branch"
    """
    The branch an item is worked on.
    """

    STATUS = "status"
    """
    An item's status.
    """

    NOTES = "notes"
    """
    What an item's next session needs to know about it.
    """

    BLOCKERS = "blockers"
    """
    Why an item is stuck.
    """

    DEPENDS_ON = "depends_on"
    """
    The ids of the items an item builds on.
    """


@dataclass(frozen=True)
class PlanItem:
    """
    One entry of a manifest's ``items`` list.
    """

    content: dict[str, Any]
    """
    The entry as parsed, every key kept so that writing it back loses nothing.
    """

    @property
    def identifier(self) -> str:
        """
        :return: The item's id.
        """
        return str(self.content[ManifestField.IDENTIFIER])

    @property
    def status(self) -> ItemStatus:
        """
        :return: The item's status.
        """
        return ItemStatus(self.content[ManifestField.STATUS])

    @property
    def notes(self) -> str:
        """
        :return: The item's notes with their line folding undone, empty when it has none.
        """
        return " ".join(str(self.content.get(ManifestField.NOTES) or "").split())

    @property
    def blockers(self) -> list[str]:
        """
        :return: Each blocker with its line folding undone.
        """
        return [
            " ".join(str(blocker).split())
            for blocker in self.content.get(ManifestField.BLOCKERS) or []
        ]

    @property
    def dependencies(self) -> list[str]:
        """
        :return: The ids of the items this one builds on.
        """
        return [
            str(dependency)
            for dependency in self.content.get(ManifestField.DEPENDS_ON) or []
        ]

    def without_dependencies(self, identifiers: set[str]) -> PlanItem:
        """
        :param identifiers: Item ids to stop depending on.
        :return: This item with every dependency on *identifiers* removed.
        """
        if not identifiers & set(self.dependencies):
            return self
        remaining = [
            dependency
            for dependency in self.dependencies
            if dependency not in identifiers
        ]
        return PlanItem({**self.content, ManifestField.DEPENDS_ON.value: remaining})


@dataclass(frozen=True)
class PlanManifest:
    """
    A parsed ``plan.yaml``.
    """

    content: dict[str, Any]
    """
    The manifest as parsed, every key kept so that writing it back loses nothing.
    """

    @property
    def identifier(self) -> str:
        """
        :return: The plan's id.
        """
        return str(self.content[ManifestField.IDENTIFIER])

    @property
    def description(self) -> str:
        """
        :return: The plan's description with its line folding undone.
        """
        return " ".join(str(self.content.get(ManifestField.DESCRIPTION) or "").split())

    @property
    def items(self) -> list[PlanItem]:
        """
        :return: The plan's items, in manifest order.
        """
        return [PlanItem(item) for item in self.content.get(ManifestField.ITEMS) or []]

    @property
    def landed_identifiers(self) -> set[str]:
        """
        :return: The ids of the items whose work has landed.
        """
        return {
            item.identifier for item in self.items if item.status is ItemStatus.DONE
        }

    def item_named(self, identifier: str) -> PlanItem:
        """
        :param identifier: The id of the item to return.
        :raises ItemNotTrackedError: If the plan has no item with that id.
        :return: The item with that id.
        """
        for item in self.items:
            if item.identifier == identifier:
                return item
        raise ItemNotTrackedError(
            plan_identifier=self.identifier, item_identifier=identifier
        )

    def item_on_branch(self, branch: str) -> PlanItem:
        """
        :param branch: The branch whose item to return.
        :raises ItemNotTrackedError: If no item of the plan is worked on that branch.
        :return: The item worked on that branch.
        """
        for item in self.items:
            if item.content.get(ManifestField.BRANCH) == branch:
                return item
        raise ItemNotTrackedError(
            plan_identifier=self.identifier, item_identifier=branch
        )

    def without_landed_items(self) -> PlanManifest:
        """
        A landed item tells a future session nothing it needs: its work is in the code
        and its history in git. Dropping it also drops every dependency on it, since a
        dependency that has landed is already satisfied.

        :return: This manifest with every landed item removed.
        """
        landed = self.landed_identifiers
        remaining = [
            item.without_dependencies(landed).content
            for item in self.items
            if item.identifier not in landed
        ]
        return PlanManifest({**self.content, ManifestField.ITEMS.value: remaining})


@dataclass
class ItemNotTrackedError(LookupError):
    """
    Raised when a plan is asked for an item it does not track.
    """

    plan_identifier: str
    """
    The plan that was searched.
    """

    item_identifier: str
    """
    The id, or the branch, that matched no item.
    """

    def __str__(self) -> str:
        """
        :return: Which item was missing from which plan.
        """
        return f"plan {self.plan_identifier!r} has no item {self.item_identifier!r}"
