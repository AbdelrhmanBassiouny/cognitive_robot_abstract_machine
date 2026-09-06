"""
Telling a branch's owner why a scheduled build's automatic pass left it out.

A build already says why it left a branch out, in its own report - but the report
reaches whoever reads the build, and a branch nobody is watching does not read its own
build. A semantic break already comments, because that comment is the only way the
branch it blocks is ever labelled at all. Every other reason a build leaves a branch out
stayed silent: a raw text conflict against a sibling tip, the build's own refusal to
merge at all, or standing on a branch one of those already applies to.

This module is that comment, for the reasons that stayed silent. It never judges
anything - that is ``/integration-conflict-triage``'s job - so it says only what the
build itself already decided, and links to the pull request the reason names when one is
still open.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from stack import Configuration, LabelWrite, Repository

from maintenance_board import (
    PullRequestField,
    branch_reference,
    get_session_link_in,
    pull_request_numbers_by_branch,
)
from maintenance_github import ForkPullRequests

from integration_report import IntegrationReport
from integration_tips import PullRequestStackTipOutcome, TipStatus

LEFT_OUT_COMMENT_PREFIX = "🟡 INTEGRATION - LEFT OUT:"
"""
Opens the comment a scheduled build's automatic pass leaves a branch with, naming why.
"""

CASCADED_STATUSES = frozenset(
    {
        TipStatus.BLOCKED,
        TipStatus.BLOCKED_WITHOUT_RECORD,
        TipStatus.CHECKS_FAILED,
        TipStatus.UNREVIEWED,
    }
)
"""
The statuses :func:`branches_left_out` reports only when they cascade from an ancestor.

A branch itself blocked, red or still draft already carries the reason in plain sight -
its own label, its own red check, its own draft toggle - and the one case that already
comments, a semantic break, already does. What stays silent otherwise is a healthy,
reviewed, green branch left out only because of what it stands on, which is worth
telling its owner precisely because nothing about the branch itself says so.
"""


def branches_left_out(
    report: IntegrationReport,
) -> tuple[PullRequestStackTipOutcome, ...]:
    """
    Every branch this build left out worth telling its owner about.

    A branch the build actually attempted and skipped is always worth it - a raw
    conflict, or the build's own refusal to merge - since nothing else will ever tell
    that owner why. A branch the build never tried because it stands on one of those,
    is red, or is still draft is worth it only when that reason belongs to an ancestor
    rather than to the branch itself: a branch's own label, its own red check, or its
    own draft toggle needs no build to point it out. A branch excluded only because
    this build was asked for a different plan is not left out for any reason its owner
    should hear about.

    :param report: What the build did.
    :return: The outcomes to comment on, each naming the branch and why.
    """
    return report.tips_left_out + tuple(
        outcome
        for outcome in report.left_out
        if outcome.status in CASCADED_STATUSES and outcome.attributed_to is not None
    )


@dataclass(frozen=True)
class LeftOutBranchReport:
    """
    What telling one branch's owner it was left out wrote, and where.
    """

    branch: str
    """
    The branch that was told.
    """

    pull_request_number: int
    """
    The fork pull request that publishes it.
    """

    status: TipStatus
    """
    What the build did with it.
    """

    label: str
    """
    The label applied, so a later pass does not tell it again unchanged.
    """

    comment: str
    """
    What was said on its pull request.
    """


def report_left_out(
    report: IntegrationReport, configuration: Configuration, fork: ForkPullRequests
) -> tuple[LeftOutBranchReport, ...]:
    """
    Tell every newly left-out branch's owner why, and silently forget the ones that
    rejoined.

    Gated by a label rather than by content, since a scheduled build runs several times
    a day: a branch still left out for the same reason next pass is left alone, because
    the label already says its owner was told.

    :param report: What the build did.
    :param configuration: The resolved configuration, naming the label to apply.
    :param fork: The fork to label and comment on.
    :return: What was written where, one entry per branch newly told.
    """
    label = configuration.integration_left_out_label
    reportable = branches_left_out(report)
    _clear_what_rejoined(
        fork, label, {outcome.pull_request_number for outcome in reportable}
    )
    pull_request_numbers = pull_request_numbers_by_branch(fork)
    written: list[LeftOutBranchReport] = []
    for outcome in reportable:
        number = outcome.pull_request_number
        pull_request = fork.pull_request(number)
        labels = PullRequestField.LABELS.read(pull_request, number)
        if label in labels:
            continue
        body = PullRequestField.BODY.read(pull_request, number)
        comment = _comment(
            outcome,
            configuration.fork_repository,
            pull_request_numbers,
            get_session_link_in(body),
        )
        fork.replace_labels(number, LabelWrite.replacing(labels, added=[label]).labels)
        fork.add_comment(number, comment)
        written.append(
            LeftOutBranchReport(
                branch=outcome.branch,
                pull_request_number=number,
                status=outcome.status,
                label=label,
                comment=comment,
            )
        )
    return tuple(written)


def _clear_what_rejoined(
    fork: ForkPullRequests, label: str, still_left_out: set[int]
) -> None:
    """
    Silently lift the label from every branch that rejoined a build.

    Silent because the label was only ever this pass's own memory that it had already
    spoken; a branch rejoining is not news the way being left out was.

    :param fork: The fork to read and write.
    :param label: The label a build's automatic pass applies.
    :param still_left_out: The pull requests this build still leaves out.
    """
    for record in fork.open_pull_requests():
        number = int(PullRequestField.NUMBER.read(record))
        labels = PullRequestField.LABELS.read(record, number)
        if label not in labels or number in still_left_out:
            continue
        fork.replace_labels(
            number, LabelWrite.replacing(labels, removed=[label]).labels
        )


def _comment(
    outcome: PullRequestStackTipOutcome,
    repository: Repository,
    pull_request_numbers: Mapping[str, int],
    session: str | None,
) -> str:
    """
    Write the comment telling a branch's owner why this build left it out.

    :param outcome: What the build did with it, and why.
    :param repository: The fork the reason's other branch would be published in.
    :param pull_request_numbers: Every open pull request's number, by branch.
    :param session: The session named in the pull request's description, if any.
    :return: The comment body.
    """
    addressed = (
        f"\n\n{session}"
        if session
        else "\n\nThis pull request's description names no session to address."
    )
    return (
        f"{LEFT_OUT_COMMENT_PREFIX} "
        f"{_reason(outcome, repository, pull_request_numbers)}\n\n"
        f"This is a scheduled build's own automatic pass talking, not a judgement - "
        f"nothing here has decided which of you, if either, should change. This "
        f"branch is labelled `integration-left-out` so this note is not repeated every "
        f"pass; the label clears on its own, without another comment, once it "
        f"rejoins a build.{addressed}"
    )


def _reason(
    outcome: PullRequestStackTipOutcome,
    repository: Repository,
    pull_request_numbers: Mapping[str, int],
) -> str:
    """
    :param outcome: What the build did with the branch, and why.
    :param repository: The fork the reason's other branch would be published in.
    :param pull_request_numbers: Every open pull request's number, by branch.
    :return: The one paragraph naming what happened and what it takes to rejoin.
    """
    branch = f"`{outcome.branch}`"
    if outcome.status is TipStatus.SKIPPED:
        paths = "\n".join(f"- `{path}`" for path in outcome.conflicting_paths)
        partner = _reference(outcome.attributed_to, repository, pull_request_numbers)
        return (
            f"this build could not merge {branch} - it conflicts with {partner} on:\n\n"
            f"{paths}\n\nNeither branch is wrong for that alone. Run "
            f"`/integration-conflict-triage` to have the pair looked at."
        )
    if outcome.status is TipStatus.INTEGRATION_FAILED:
        return (
            f"this build could not even attempt to merge {branch} - git refused:\n\n"
            f"```\n{outcome.explanation}\n```\n\nThis is the build's own problem, not "
            f"this branch's."
        )
    ancestor = _reference(outcome.attributed_to, repository, pull_request_numbers)
    if outcome.status in (TipStatus.BLOCKED, TipStatus.BLOCKED_WITHOUT_RECORD):
        return (
            f"this build left {branch} out because it stands on {ancestor}, which is "
            f"already blocked. This branch's own state is fine; it rejoins the pass "
            f"once that block is lifted."
        )
    if outcome.status is TipStatus.CHECKS_FAILED:
        return (
            f"this build left {branch} out because it stands on {ancestor}, whose own "
            f"checks are failing. This branch's own checks are fine; it rejoins the "
            f"pass once those pass again."
        )
    return (
        f"this build left {branch} out because it stands on {ancestor}, which is "
        f"still a draft. It rejoins the pass once that is marked ready for review."
    )


def _reference(
    branch: str,
    repository: Repository,
    pull_request_numbers: Mapping[str, int],
) -> str:
    """
    :param branch: The branch to name.
    :param repository: The fork the branch's pull request would live in.
    :param pull_request_numbers: Every open pull request's number, by branch.
    :return: A markdown link naming its pull request, or the bare branch name when no
        open pull request publishes it any more.
    """
    return branch_reference(repository, branch, pull_request_numbers.get(branch))
