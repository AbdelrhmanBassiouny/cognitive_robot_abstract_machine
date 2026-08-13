"""
Recording the upstream link on every branch ready to be promoted.

The upstream pull request is not opened here - the credential has no write access there.
What is written is the link that opens it prefilled, into the fork pull request's own
description, plus the label that stops a later pass rebuilding it.

The one thing this cannot compute is what the upstream reviewer reads: it is a reading of
a diff. So a caller who has one supplies it, and everything around it - the title, the
link back to the fork pull request, the encoding, the length budget - stays here. A
caller with no reading of the diff to offer, which is any run with no model in it,
promotes just the same and the upstream pull request opens with the link back and nothing
else.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from github_links import GitHubLinks
from maintenance_constants import PROMOTION_HEADING, PROMOTION_LINK_LABEL
from maintenance_board import PullRequestField
from maintenance_github import ForkPullRequests, PullRequestReader, PullRequestWriter
from stack import (
    BranchStatus,
    Configuration,
    LabelWrite,
    PromotionLink,
    Stack,
    promotion_order,
)

# %% the summaries a caller writes


class PromotionSummaryField(StrEnum):
    """
    The keys one summary is written under in the summaries document.
    """

    POINTS = "points"
    """
    The points the upstream pull request opens with.
    """

    TITLE = "title"
    """
    A title to open it with instead of the fork pull request's own.
    """


@dataclass(frozen=True)
class PromotionSummary:
    """
    What one upstream pull request opens with, as far as its author has written it.

    Both halves are optional, and a caller supplying neither is the ordinary case for a
    run with no model in it: what is left is the link back to the fork pull request,
    which is never the caller's to supply. A session promoting through the maintenance
    skill supplies both, since it can read the diff and the upstream cannot.
    """

    points: tuple[str, ...] = ()
    """
    The points, rendered as a bullet each; empty when nobody has written them.
    """

    title: str | None = None
    """
    The title to open with, or ``None`` to keep the fork pull request's own.
    """

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> PromotionSummary:
        """
        Read one summary out of the summaries document.

        :param data: The entry as it was written.
        :return: The summary.
        """
        return cls(
            points=tuple(data.get(PromotionSummaryField.POINTS) or ()),
            title=data.get(PromotionSummaryField.TITLE),
        )

    @property
    def as_markdown(self) -> str:
        """
        Render the points as the bullet list the upstream pull request opens with.

        Rendering rather than transcribing is what makes "a point-based summary" hold:
        the caller supplies points, so prose cannot arrive dressed as one.

        :return: One bullet per point, empty when there are none.
        """
        return "\n".join(f"- {point}" for point in self.points)


@dataclass(frozen=True)
class PromotionSummaries:
    """
    Every summary written for this pass, keyed by the fork pull request it belongs to.
    """

    by_pull_request: Mapping[int, PromotionSummary] = field(default_factory=dict)
    """
    The summaries, by fork pull request number.
    """

    @classmethod
    def read_from(cls, path: Path | None) -> PromotionSummaries:
        """
        Read the summaries a caller wrote, or none when they wrote none.

        :param path: The document to read, or ``None`` when none was given.
        :return: The summaries.
        """
        if path is None:
            return cls()
        return cls.from_json(json.loads(path.read_text()))

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> PromotionSummaries:
        """
        Read the summaries document.

        :param data: The document, keyed by fork pull request number.
        :return: The summaries.
        """
        return cls(
            {
                int(number): PromotionSummary.from_json(entry)
                for number, entry in data.items()
            }
        )

    def for_pull_request(self, number: int) -> PromotionSummary:
        """
        Answer for a pull request whether or not anybody wrote for it.

        An absent entry and an empty one mean the same thing here - nobody has read this
        diff for the upstream - so both answer with the summary that adds nothing.

        :param number: The fork pull request to look up.
        :return: Its summary, empty when none was written.
        """
        return self.by_pull_request.get(number, PromotionSummary())


# %% what one pass's promotion did to each branch


class PromotionOutcome(StrEnum):
    """
    What became of one branch during a promotion.
    """

    PROMOTED = "promoted"
    """
    Its link was built and recorded, and the label applied.
    """

    ALREADY_LINKED = "already-linked"
    """
    It carries the link label already, so a link was built for it on an earlier pass.
    """

    WITHHELD = "withheld"
    """
    It is conflicted against its base, so it was left for its owner rather than promoted.
    """

    LINK_LABEL_CLEARED = "link-label-cleared"
    """
    Its link has been acted on, so the label that stopped it being rebuilt is spent.
    """


@dataclass(frozen=True)
class BranchPromotion:
    """
    What became of one branch, in terms the caller of a pass can act on.
    """

    branch: str
    """
    The branch, which is what identifies it.
    """

    pull_request_number: int
    """
    Its fork pull request, which is the key a summary is written under.
    """

    outcome: PromotionOutcome
    """
    What became of it.
    """

    url: str | None = None
    """
    The compare-and-create link, absent for a branch no link was built for this pass.
    """

    body_was_truncated: bool = False
    """
    Whether the prefilled description had to be shortened to fit the URL limit.
    """


# %% recording the link


def description_with_promotion_link(description: str, url: str) -> str:
    """
    Put a promotion link into a description, replacing any already there.

    :param description: The pull request's current description.
    :param url: The link to record.
    :return: The description to write back.
    """
    before, _, _ = description.partition(PROMOTION_HEADING)
    return f"{before.rstrip()}\n\n{PROMOTION_HEADING}\n\n{url}\n"


def promotion_link_in(description: str, configuration: Configuration) -> str | None:
    """
    Read back the promotion link a previous pass recorded in a description.

    The inverse of :func:`description_with_promotion_link`, so a caller reporting a
    pending link reports the one a reader will actually open rather than a freshly
    computed one that could differ from it. What a link looks like comes from the same
    builder that composes one, so the two cannot drift.

    :param description: The pull request's description.
    :param configuration: The resolved configuration, naming the upstream compared with.
    :return: The recorded link, or ``None`` if the description carries none.
    """
    _, heading, after = description.partition(PROMOTION_HEADING)
    if not heading:
        return None
    pattern = GitHubLinks(configuration.upstream_repository).comparison_pattern(
        configuration.upstream_base
    )
    found = pattern.search(after)
    return found.group(0) if found else None


def promote(
    stack: Stack, fork: ForkPullRequests, summaries: PromotionSummaries
) -> list[BranchPromotion]:
    """
    Build and record the upstream link for every branch ready to be promoted.

    The upstream pull request is not opened here - the app has no write access there, so
    that call fails every time. What is written is the link that opens it prefilled, into
    the fork pull request's own description, plus the label stopping a later pass
    rebuilding it. The ``in-review`` label stays the developer's to add, since the
    upstream pull request does not exist until they click Create.

    Both the decision and the label write read the labels the branch carries *now*, not
    the ones the board was exported with: the restack runs between those two moments and
    withholds a branch by labelling it, so a snapshot is already out of date here.

    :param stack: The derived stack.
    :param fork: The fork to read descriptions from and write links back to.
    :param summaries: What each upstream pull request is to open with, where anybody has
        written it.
    :return: One entry per branch considered, in dependency order.
    """
    promotions: list[BranchPromotion] = []
    withheld = stack.configuration.needs_resolution_label
    for branch in promotion_order(stack):
        number = branch.pull_request_number
        pull_request = fork.pull_request(number)
        labels = PullRequestField.LABELS.read(pull_request, number)
        if PROMOTION_LINK_LABEL in labels:
            promotions.append(
                BranchPromotion(branch.name, number, PromotionOutcome.ALREADY_LINKED)
            )
            continue
        if withheld in labels:
            promotions.append(
                BranchPromotion(branch.name, number, PromotionOutcome.WITHHELD)
            )
            continue
        summary = summaries.for_pull_request(number)
        description = str(PullRequestField.BODY.read(pull_request, number) or "")
        link = PromotionLink.build(
            stack.configuration,
            branch.name,
            summary.title
            or str(PullRequestField.TITLE.read(pull_request, number) or branch.name),
            _prefilled_description(summary, number, stack.configuration),
        )
        fork.set_description(
            number,
            description_with_promotion_link(description, link.url),
        )
        fork.replace_labels(
            number,
            LabelWrite.replacing(labels, added=[PROMOTION_LINK_LABEL]).labels,
        )
        promotions.append(
            BranchPromotion(
                branch=branch.name,
                pull_request_number=number,
                outcome=PromotionOutcome.PROMOTED,
                url=link.url,
                body_was_truncated=link.body_was_truncated,
            )
        )
    return promotions


def _prefilled_description(
    summary: PromotionSummary, pull_request_number: int, configuration: Configuration
) -> str:
    """
    Build what the upstream pull request opens with.

    :param summary: What its author wrote for the upstream reviewer, if anything.
    :param pull_request_number: The fork pull request, to link back to.
    :param configuration: The resolved configuration, naming the fork.
    :return: The points where there are any, and always the link back to the full story.
    """
    detail = (
        f"Full detail: "
        f"{GitHubLinks(configuration.fork_repository).pull_request(pull_request_number)}"
    )
    points = summary.as_markdown
    return f"{points}\n\n{detail}" if points else detail


def clear_spent_promotion_labels(
    stack: Stack, fork: PullRequestWriter
) -> list[BranchPromotion]:
    """
    Drop the link label from every branch whose link has already been acted on.

    :param stack: The derived stack.
    :param fork: The fork to write to.
    :return: One entry per branch whose label was cleared.
    """
    spent = [
        branch
        for branch in stack.branches
        if PROMOTION_LINK_LABEL in branch.labels
        and branch.status in {BranchStatus.IN_REVIEW, BranchStatus.MERGED}
    ]
    for branch in spent:
        fork.replace_labels(
            branch.pull_request_number,
            LabelWrite.replacing(branch.labels, removed=[PROMOTION_LINK_LABEL]).labels,
        )
    return [
        BranchPromotion(
            branch.name,
            branch.pull_request_number,
            PromotionOutcome.LINK_LABEL_CLEARED,
        )
        for branch in spent
    ]


# %% the links still waiting to be opened


@dataclass
class RecordedPromotionLinkMissingError(ValueError):
    """
    Raised when a branch says its link was built but carries no link.

    The label and the link are written in the same breath, so one without the other is a
    description somebody has edited since - and reporting a pending promotion with an
    empty link would send a reader to nothing.
    """

    pull_request_number: int
    """
    The pull request carrying the label.
    """

    def __str__(self) -> str:
        """:return: Which pull request contradicts itself, and how."""
        return (
            f"pull request {self.pull_request_number} carries "
            f"'{PROMOTION_LINK_LABEL}' but its description has no link under "
            f"'{PROMOTION_HEADING}'; re-run the promotion to rebuild it"
        )


@dataclass(frozen=True)
class PendingPromotion:
    """
    One upstream pull request whose link is built and waiting to be opened.
    """

    pull_request_number: int
    """
    The fork pull request the link was built from.
    """

    title: str
    """
    Its title.
    """

    branch: str
    """
    Its branch.
    """

    url: str
    """
    The recorded compare-and-create link, ready to open.
    """


def pending_promotions(
    configuration: Configuration, fork: PullRequestReader
) -> tuple[PendingPromotion, ...]:
    """
    Every fork pull request whose upstream link is built but not yet acted on.

    Read straight from the fork rather than from a board, so this answers in a session
    that did not run the pass - which is the point of it, since the pass discards its
    board when it finishes.

    :param configuration: The resolved configuration, naming the labels and the upstream.
    :param fork: The fork to read from.
    :return: The pending promotions, in pull request number order.
    :raises RecordedPromotionLinkMissingError: If one carries the label but no link.
    """
    pending: list[PendingPromotion] = []
    for record in fork.open_pull_requests():
        number = int(PullRequestField.NUMBER.read(record))
        labels = PullRequestField.LABELS.read(record, number)
        if (
            PROMOTION_LINK_LABEL not in labels
            or configuration.in_review_label in labels
        ):
            continue
        url = promotion_link_in(
            str(PullRequestField.BODY.read(record, number) or ""), configuration
        )
        if url is None:
            raise RecordedPromotionLinkMissingError(number)
        pending.append(
            PendingPromotion(
                pull_request_number=number,
                title=str(PullRequestField.TITLE.read(record, number) or ""),
                branch=PullRequestField.HEAD.read(record, number),
                url=url,
            )
        )
    return tuple(sorted(pending, key=lambda entry: entry.pull_request_number))
