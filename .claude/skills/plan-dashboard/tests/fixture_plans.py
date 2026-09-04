"""
The plans directory the cross-plan reference tests resolve against.

Every value a test asserts about these fixtures - a repository, a title, a
pull request number - is read back out of the manifest that declares it, so
nothing here is a second copy of the fixture that keeps passing once the
fixture changes. Only the ids are named in code, since they are how a test
points at one plan or item in the first place.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from build_dashboard import DependencyReference, ManifestKey, PlanFile

FIXTURE_PLANS_DIRECTORY = Path(__file__).parent / "fixtures" / "plans"
"""
The plans directory itself, holding one subdirectory per fixture plan plus the
dashboard-URL cache naming one of them.
"""

PLAN_UNDER_TEST_ID = "test-plan"
"""
The id of the plan these tests render, which :attr:`ForeignItemId.DEPENDING_BACK` names
to close a cross-plan cycle.
"""


class FixturePlanId(StrEnum):
    """
    The plans the fixture directory holds, plus one it deliberately doesn't.
    """

    OTHER = "other-plan"
    """
    A published plan, the one most references point into.
    """

    UNPUBLISHED = "unpublished-plan"
    """
    A plan the dashboard-URL cache names no URL for.
    """

    ABSENT = "ghost-plan"
    """
    No such plan, for the reference that must be rejected.
    """


class ForeignItemId(StrEnum):
    """
    The items the fixture plans hold, one per state a dependency can be in, plus one id
    that names nothing.
    """

    READY = "foreign-ready"
    """
    In :attr:`FixturePlanId.OTHER`, with a pull request out of draft.
    """

    DRAFT = "foreign-draft"
    """
    In :attr:`FixturePlanId.OTHER`, with a pull request still in draft.
    """

    DONE = "foreign-done"
    """
    In :attr:`FixturePlanId.OTHER`, already landed.
    """

    NOT_STARTED = "foreign-not-started"
    """
    In :attr:`FixturePlanId.OTHER`, with no pull request at all.
    """

    DEPENDING_BACK = "foreign-depending-back"
    """
    In :attr:`FixturePlanId.OTHER`, depending on :data:`PLAN_UNDER_TEST_ID`.
    """

    UNPUBLISHED = "unpublished-item"
    """
    The only item of :attr:`FixturePlanId.UNPUBLISHED`.
    """

    ABSENT = "ghost-item"
    """
    No such item, for the reference that must be rejected.
    """


def foreign_reference(item_identifier: str, plan_id: str = FixturePlanId.OTHER) -> str:
    """
    The ``depends_on`` text naming one item of another plan.

    :param item_identifier: The foreign item's own id.
    :param plan_id: The plan holding it.
    """
    return DependencyReference(item_identifier=item_identifier, plan_id=plan_id).text


def fixture_manifest(plan_id: str) -> dict[str, Any]:
    """
    One fixture plan's manifest, exactly as the file writes it.

    :param plan_id: The plan's id, which is also its directory's name.
    """
    manifest_path = FIXTURE_PLANS_DIRECTORY / plan_id / PlanFile.MANIFEST
    return yaml.safe_load(manifest_path.read_text())


def fixture_item(plan_id: str, item_identifier: str) -> dict[str, Any]:
    """
    One fixture item's entry, exactly as its manifest writes it.

    :param plan_id: The plan holding it.
    :param item_identifier: That item's own id.
    """
    for entry in fixture_manifest(plan_id)[ManifestKey.ITEMS]:
        if entry[ManifestKey.ID] == item_identifier:
            return entry
    raise KeyError(f"no item {item_identifier!r} in fixture plan {plan_id!r}")


def fixture_repository(plan_id: str) -> str:
    """
    Where one fixture plan's pull requests live.

    :param plan_id: The plan's id.
    """
    return fixture_manifest(plan_id)[ManifestKey.DEFAULT_REPOSITORY]


def fixture_pull_request_number(plan_id: str, item_identifier: str) -> str:
    """
    One fixture item's pull request number, keyed the way ``pr_data.json`` keys it.

    :param plan_id: The plan holding it.
    :param item_identifier: That item's own id.
    """
    return str(fixture_item(plan_id, item_identifier)[ManifestKey.PULL_REQUEST_NUMBER])
