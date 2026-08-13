"""
Recording the upstream link on every branch ready to be promoted.

The upstream pull request is not opened here - the credential has no write access there.
What is written is the link that opens it prefilled, into the fork pull request's own
description, plus the label that stops a later pass rebuilding it.

The one thing this cannot compute is the prefilled description: it is a reading of a
diff, written for the upstream reviewer. So the caller supplies it, and everything around
it - the title, the link back to the fork pull request, the encoding, the length budget -
stays here. A branch nobody has written one for is reported as awaiting it rather than
promoted with a body nobody wrote.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from maintenance_constants import (
    PROMOTION_HEADING,
    PROMOTION_LINK_LABEL,
    RECORDED_PROMOTION_LINK_PATTERN,
)
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


@dataclass
class EmptyPromotionSummaryError(ValueError):
    """
    Raised when a summary is present but says nothing.

    An entry with no points is indistinguishable in its effect from no entry at all, and
    the difference matters: one is a branch still waiting to be written for, the other is
    a branch somebody has declared finished.
    """

    pull_request_number: int
    """
    The pull request whose summary is empty.
    """

    def __str__(self) -> str:
        """:return: Which summary says nothing, and what it needs."""
        return (
            f"the summary for pull request {self.pull_request_number} has no "
            f"'{PromotionSummaryField.POINTS}'; write the points the upstream reviewer "
            f"is meant to read"
        )


@dataclass(frozen=True)
class PromotionSummary:
    """
    What one upstream pull request opens with, as its author wrote it.
    """

    points: tuple[str, ...]
    """
    The points, rendered as a bullet each.
    """

    title: str | None = None
    """
    The title to open with, or ``None`` to keep the fork pull request's own.
    """

    @classmethod
    def from_json(cls, data: Mapping[str, Any], number: int) -> PromotionSummary:
        """
        Read one summary out of the summaries document.

        :param data: The entry as it was written.
        :param number: The pull request it was written for, named in any rejection.
        :return: The summary.
        :raises EmptyPromotionSummaryError: If it carries no points.
        """
        points = tuple(data.get(PromotionSummaryField.POINTS) or ())
        if not points:
            raise EmptyPromotionSummaryError(number)
        return cls(points=points, title=data.get(PromotionSummaryField.TITLE))

    @property
    def as_markdown(self) -> str:
        """
        Render the points as the bullet list the upstream pull request opens with.

        Rendering rather than transcribing is what makes "a point-based summary" hold:
        the caller supplies points, so prose cannot arrive dressed as one.

        :return: One bullet per point.
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
        :raises EmptyPromotionSummaryError: If any entry carries no points.
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
        :raises EmptyPromotionSummaryError: If any entry carries no points.
        """
        return cls(
            {
                int(number): PromotionSummary.from_json(entry, int(number))
                for number, entry in data.items()
            }
        )

    def for_pull_request(self, number: int) -> PromotionSummary | None:
        """:param number: The fork pull request to look up.
        :return: Its summary, or ``None`` if nobody has written one."""
        return self.by_pull_request.get(number)


# %% what one pass's promotion did, and left


@dataclass(frozen=True)
class Promotion:
    """
    One branch's compare-and-create link, and where it was recorded.
    """

    branch: str
    """
    The branch promoted.
    """

    pull_request_number: int
    """
    Its fork pull request.
    """

    url: str
    """
    The compare-and-create link opening the upstream pull request.
    """

    body_was_truncated: bool
    """
    Whether the prefilled description had to be shortened to fit the URL limit.
    """


@dataclass(frozen=True)
class BranchAwaitingSummary:
    """
    A branch that would have been promoted, had anybody written its summary.
    """

    branch: str
    """
    The branch waiting.
    """

    pull_request_number: int
    """
    Its fork pull request, which is the key a summary is written under.
    """

    title: str
    """
    Its title, so a caller can tell which branch they are writing for.
    """


@dataclass(frozen=True)
class PromotionRound:
    """
    What one pass's promotion promoted, and what it left for somebody to write.
    """

    promoted: tuple[Promotion, ...] = ()
    """
    The branches whose link was built and recorded.
    """

    awaiting_summary: tuple[BranchAwaitingSummary, ...] = ()
    """
    The branches held back because nobody had written their summary.
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


def promotion_link_in(description: str) -> str | None:
    """
    Read back the promotion link a previous pass recorded in a description.

    The inverse of :func:`description_with_promotion_link`, so a caller reporting a
    pending link reports the one a reader will actually open rather than a freshly
    computed one that could differ from it.

    :param description: The pull request's description.
    :return: The recorded link, or ``None`` if the description carries none.
    """
    _, heading, after = description.partition(PROMOTION_HEADING)
    if not heading:
        return None
    found = RECORDED_PROMOTION_LINK_PATTERN.search(after)
    return found.group(0) if found else None


def promote(
    stack: Stack, fork: ForkPullRequests, summaries: PromotionSummaries
) -> PromotionRound:
    """
    Build and record the upstream link for every branch whose summary is written.

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
    :param summaries: What each branch's upstream pull request is to open with.
    :return: What was promoted, and what is waiting on a summary.
    """
    promoted: list[Promotion] = []
    awaiting: list[BranchAwaitingSummary] = []
    withheld = stack.configuration.needs_resolution_label
    for branch in promotion_order(stack):
        number = branch.pull_request_number
        pull_request = fork.pull_request(number)
        labels = PullRequestField.LABELS.read(pull_request, number)
        if PROMOTION_LINK_LABEL in labels or withheld in labels:
            continue
        title = str(PullRequestField.TITLE.read(pull_request, number) or branch.name)
        summary = summaries.for_pull_request(number)
        if summary is None:
            awaiting.append(BranchAwaitingSummary(branch.name, number, title))
            continue
        description = str(PullRequestField.BODY.read(pull_request, number) or "")
        link = PromotionLink.build(
            stack.configuration,
            branch.name,
            summary.title or title,
            _prefilled_description(summary, number, stack),
        )
        fork.set_description(
            number,
            description_with_promotion_link(description, link.url),
        )
        fork.replace_labels(
            number,
            LabelWrite.replacing(labels, added=[PROMOTION_LINK_LABEL]).labels,
        )
        promoted.append(
            Promotion(
                branch=branch.name,
                pull_request_number=number,
                url=link.url,
                body_was_truncated=link.body_was_truncated,
            )
        )
    return PromotionRound(tuple(promoted), tuple(awaiting))


def _prefilled_description(
    summary: PromotionSummary, pull_request_number: int, stack: Stack
) -> str:
    """
    Build what the upstream pull request opens with.

    :param summary: The points its author wrote for the upstream reviewer.
    :param pull_request_number: The fork pull request, to link back to.
    :param stack: The derived stack, naming the fork.
    :return: The points, plus a link back to the full detail.
    """
    return f"{summary.as_markdown}\n\n{_fork_pull_request_link(pull_request_number, stack.configuration)}"


def _fork_pull_request_link(
    pull_request_number: int, configuration: Configuration
) -> str:
    """
    :param pull_request_number: The fork pull request to link to.
    :param configuration: The resolved configuration, naming the fork.
    :return: The line linking the upstream reviewer back to the whole story.
    """
    return (
        f"Full detail: https://github.com/{configuration.fork_repository}"
        f"/pull/{pull_request_number}"
    )


def clear_spent_promotion_labels(
    stack: Stack, fork: PullRequestWriter
) -> tuple[str, ...]:
    """
    Drop the link label from every branch whose link has already been acted on.

    :param stack: The derived stack.
    :param fork: The fork to write to.
    :return: The branches whose label was cleared.
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
    return tuple(branch.name for branch in spent)


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

    :param configuration: The resolved configuration, naming the labels.
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
        url = promotion_link_in(str(PullRequestField.BODY.read(record, number) or ""))
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
