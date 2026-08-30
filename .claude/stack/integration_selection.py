"""
Which tips a build carries, and which it leaves out and why.

Readiness is read down the whole chain rather than per branch: a tip contains its stack,
so a reviewed branch standing on a draft would bring that draft in under its own name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

from stack import Branch, PullRequest, Stack, order

from maintenance_git_commands import MaintenanceGitCommandRunner
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
from integration_pass_record import PassedChecks, RecordedSubject
from integration_plans import PlanFilter
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


def select_for_build(stack: Stack, plans: PlanFilter | None = None) -> BuildSelection:
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

    A build asked for particular plans holds a branch out the same way again, so one
    plan's branches can be judged on their own without a build of their own.

    :param stack: The derived stack, its branches carrying whatever
        :class:`BranchChecks` last read.
    :param plans: The plans this build was asked to carry, or ``None`` for all of them.
    :return: The integrated branches and the ones left out.
    """
    filtering = plans or PlanFilter.unfiltered()
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
        outside_the_plans = filtering.leaves_out(branch.name)
        carried = (
            branch.status.is_out_of_draft
            and not blocked
            and not red
            and outside_the_plans is None
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
        elif outside_the_plans is not None:
            reason = (outside_the_plans, branch.name)
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


@dataclass
class BranchChecks:
    """
    What each branch's own checks say, asking GitHub only about heads nothing has
    already seen pass.

    Most of a rebuild's readings are about branches that have not moved since the last
    one, and the answer to those is already on the fork.
    """

    fork: CandidatePullRequests
    """
    The fork to read the checks from.
    """

    git: MaintenanceGitCommandRunner
    """
    The runner the published heads are read through.
    """

    remote: str
    """
    The fork remote, whose copy of a branch is the one a build merges.
    """

    recorded: PassedChecks
    """
    What this fork has already seen pass, updated as each new pass is written.
    """

    def annotate(self, stack: Stack) -> Stack:
        """
        Read what each branch's own checks say, so a build can decline to carry a red
        one.

        A branch that is already red alone makes the candidate red for a reason no reader
        can tell apart from two branches breaking each other - which is the one thing the
        candidate exists to report.

        :param stack: The derived stack.
        :return: The same stack, its branches carrying the verdict on their own heads.
        """
        published = self._published_heads()
        for branch in stack.branches:
            branch.ci = str(self._verdict_for(branch.name, published.get(branch.name)))
        return stack

    def _verdict_for(self, branch: str, head: str | None) -> ChecksVerdict:
        """
        Answer for one branch, from the record where it has one.

        Read against the branch rather than a commit where GitHub is asked, so it
        answers for whatever the branch points at after a restack has moved it; a
        recorded pass is about the commit, so a branch that has moved has no record and
        is read.

        :param branch: The branch to answer for.
        :param head: What the fork has it pointing at, absent when the fork has no such
            branch.
        :return: What its checks amount to.
        """
        if head is not None and self.recorded.holds(RecordedSubject.BRANCH_HEAD, head):
            return ChecksVerdict.PASSED
        verdict = read_checks(self.fork, branch).verdict
        if verdict is ChecksVerdict.PASSED and head is not None:
            self.recorded = self.recorded.record(
                self.git, self.remote, RecordedSubject.BRANCH_HEAD, head, head
            )
        return verdict

    def _published_heads(self) -> dict[str, str]:
        """
        :return: What the fork has each of its branches pointing at, read in one call
            rather than one per branch.
        """
        listed = self.git.run(
            "for-each-ref",
            "--format=%(refname:strip=3) %(objectname)",
            f"refs/remotes/{self.remote}/",
        )
        return dict(line.split(" ", 1) for line in listed.splitlines() if " " in line)


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
    remote = run.configuration.fork_remote
    checks = BranchChecks(
        fork=fork,
        git=run.git,
        remote=remote,
        recorded=PassedChecks.read(run.git, remote),
    )
    stack = run.stack(fork)
    if not restack_first:
        return checks.annotate(stack)
    restack(stack, run.git, fork)
    run.refresh_remotes()
    return checks.annotate(run.stack(fork))


def tips_of(stack: Stack, plans: PlanFilter | None = None) -> list[Branch]:
    """
    The branches to merge, in the order they are merged.

    A tip is the deepest branch a build integrates, not the stack's own tip. One already
    contains its own stack, so its parent is left out, as is anything already in the
    upstream base or ruled out by :func:`select_for_build`.

    Order is part of the contract rather than incidental, since it decides *which* tip a
    conflict skips: ascending pull request number.

    :param stack: The derived stack.
    :param plans: The plans this build was asked to carry, or ``None`` for all of them.
    :return: The tips, in merge order.
    """
    integrated = select_for_build(stack, plans).integrated
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
