"""
Which tips a build carries, and which it leaves out and why.

Readiness is read down the whole chain rather than per branch: a tip contains its stack,
so a reviewed branch standing on a draft would bring that draft in under its own name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from stack import Branch, PullRequest, Stack, order

from maintenance_github import (
    CandidatePullRequests,
    GitHubRepository,
)
from maintenance_restack_procedure import restack
from integration_verdict import (
    ChecksVerdict,
    read_checks,
)

from integration_constants import BUILD_NAME_FORMAT, POINTER_BRANCH
from integration_tips import PullRequestStackTipOutcome, TipStatus

if TYPE_CHECKING:
    from integration_run import IntegrationRun


@dataclass(frozen=True)
class BuildSelection:
    """
    What a build may integrate, and what it never tries to.
    """

    integrated: tuple[Branch, ...]
    """
    Every branch reviewed and unblocked all the way down to the base, parents before
    children.
    """

    left_out: tuple[PullRequestStackTipOutcome, ...]
    """
    Every branch left out, each naming the branch that keeps it out.

    Named rather than merely absent: a build that integrates nine branches out of
    nineteen and says so only by omission reads as having covered everything.
    """


def work_in_flight(pull_requests: Iterable[PullRequest]) -> list[PullRequest]:
    """
    The open pull requests a build is assembled from.

    A candidate is opened against the branch a build would replace, so it is a build
    being judged rather than work in flight - and it looks to a build like an ordinary
    reviewed branch, so one still open when the next rebuild reads the fork would be
    merged into it.

    :param pull_requests: Every open pull request on the fork.
    :return: The ones that are work.
    """
    return [
        pull_request
        for pull_request in pull_requests
        if pull_request.base != POINTER_BRANCH
    ]


def select_for_build(stack: Stack) -> BuildSelection:
    """
    Split the stack into the work a build may integrate and the work it may not.

    A build integrates only what its author has reviewed, which this repository records by
    the pull request leaving draft. That cannot be decided per branch, because a tip
    contains its whole stack: merging a reviewed branch that stands on a draft would put
    the draft's commits into the build under the reviewed branch's name. So readiness is
    read down the whole chain, and a stack that is draft at its root is left out entire.
    A label that withholds a branch and a branch whose own checks failed hold their
    dependents out the same way, and for the same reason.

    A branch is read as red only from a *finished* failure, never from want of a pass: a
    restack rewrites every stale tip's head, so requiring green would empty the build
    whenever one ran.

    :param stack: The derived stack, its branches carrying whatever
        :func:`branches_annotated_with_their_own_checks` last read.
    :return: The integrated branches and the ones left out.
    """
    in_the_stack = {branch.name for branch in stack.branches}
    integrated: list[Branch] = []
    integrated_names: set[str] = set()
    left_out: list[PullRequestStackTipOutcome] = []
    reasons: dict[str, tuple[TipStatus, str]] = {}
    for branch in order(stack):
        stands_on_integrated_work = (
            branch.parent in integrated_names
            or branch.parent not in in_the_stack
            or stack.has_landed_upstream(branch.parent)
        )
        blocked = stack.is_blocked(branch)
        red = branch.ci == ChecksVerdict.FAILED
        carried = (
            branch.status.is_out_of_draft
            and not blocked
            and not red
            and stands_on_integrated_work
        )
        if carried:
            integrated.append(branch)
            integrated_names.add(branch.name)
            continue
        if blocked:
            reason = (TipStatus.BLOCKED, branch.name)
        elif red:
            reason = (TipStatus.CHECKS_FAILED, branch.name)
        elif not branch.status.is_out_of_draft:
            reason = (TipStatus.UNREVIEWED, branch.name)
        else:
            reason = reasons.get(branch.parent, (TipStatus.UNREVIEWED, branch.parent))
        reasons[branch.name] = reason
        status, held_out_by = reason
        left_out.append(
            PullRequestStackTipOutcome(
                branch=branch.name,
                pull_request_number=branch.pull_request_number,
                status=status,
                attributed_to=None if held_out_by == branch.name else held_out_by,
            )
        )
    return BuildSelection(integrated=tuple(integrated), left_out=tuple(left_out))


def branches_annotated_with_their_own_checks(
    stack: Stack, fork: CandidatePullRequests
) -> Stack:
    """
    Read what each branch's own checks say, so a build can decline to carry a red one.

    A branch that is already red alone makes the candidate red for a reason no reader can
    tell apart from two branches breaking each other - which is the one thing the
    candidate exists to report. Read against the branch rather than a commit, so it
    answers for whatever the branch points at after a restack has moved it.

    :param stack: The derived stack.
    :param fork: The fork to read the checks from.
    :return: The same stack, its branches carrying the verdict on their own heads.
    """
    for branch in stack.branches:
        branch.ci = str(read_checks(fork, branch.name).verdict)
    return stack


def stack_to_build(
    run: IntegrationRun, fork: GitHubRepository, restack_first: bool
) -> Stack:
    """
    The stack a build is made from, read after anything that could change it.

    A restack moves published tips and writes the label that withholds a branch it could
    not move, so a stack read before it describes a fork that no longer exists. Reading
    it again is what lets :func:`select_for_build` leave out the branch this very pass
    has just blocked.

    :param run: What this run has resolved.
    :param fork: The fork to read the open pull requests from.
    :param restack_first: Whether to bring stale tips forward before reading.
    :return: The stack to build from, annotated with each branch's own checks.
    """
    stack = run.stack(fork)
    if not restack_first:
        return branches_annotated_with_their_own_checks(stack, fork)
    restack(stack, run.git, fork)
    run.refresh_remotes()
    return branches_annotated_with_their_own_checks(run.stack(fork), fork)


def tips_of(stack: Stack) -> list[Branch]:
    """
    The branches to merge, in the order they are merged.

    A tip is the deepest branch a build integrates, not the stack's own tip. One already
    contains its own stack, so its parent is left out, as is anything already in the
    upstream base or ruled out by :func:`select_for_build`.

    Order is part of the contract rather than incidental, since it decides *which* tip a
    conflict skips: ascending pull request number.

    :param stack: The derived stack.
    :return: The tips, in merge order.
    """
    integrated = select_for_build(stack).integrated
    claimed_as_parent = {branch.parent for branch in integrated}
    return sorted(
        (
            branch
            for branch in integrated
            if branch.name not in claimed_as_parent
            and not stack.has_landed_upstream(branch.name)
        ),
        key=lambda branch: branch.pull_request_number,
    )


def build_branch_name(moment: datetime) -> str:
    """:param moment: When the build started.
    :return: The branch to assemble it on."""
    return f"{POINTER_BRANCH}-{moment.strftime(BUILD_NAME_FORMAT)}"
