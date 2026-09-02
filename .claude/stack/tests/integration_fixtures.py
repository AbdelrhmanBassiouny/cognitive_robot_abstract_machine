"""
What the integration builder's tests are written in terms of.

The branches a build is made of, the factories that describe one without a repository,
and the scratch-fork arrangements more than one module builds on. Not a test module:
pytest collects ``test_*.py`` only, so nothing here runs on its own.
"""

from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from git_commands import BranchPublication, ProposedPush
from stack import Branch, BranchStatus, IntegrationStrategy, PullRequest, Stack

from integration_carried_pipeline import PIPELINE_PATHS
from integration_verdict import ChecksVerdict
from workflow_document import REPOSITORY_ROOT
import integration_constants
import integration_tips
import integration
from integration_assembly import build_integration
from integration_block_record import BlockStanding, MeasuredHead
from integration_failure import IntegrationTestFailure
from integration_report import IntegrationReport
from integration_run import IntegrationRun
from integration_tips import (
    PullRequestStackTipOutcome,
    ResolutionAuthor,
    ResolutionProvenance,
    TipStatus,
)

from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    a_stack,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

INTEGRATION_SCRIPT = Path(integration.__file__)
"""
The builder under test, invoked as a subprocess wherever an exit status is the
assertion.

Read off the imported module rather than rebuilt from this file's location, so the
subprocess runs the same file the rest of the suite imports.
"""

A_BUILD_BRANCH = "integration-20260810-120000"
"""
A fixed build branch name, so a test asserting on content never depends on the clock.
"""

FIRST_TIP = "first-tip"
"""
The tip merged first wherever merge order matters.
"""

SECOND_TIP = "second-tip"
"""
The tip merged after :data:`FIRST_TIP`, and the one a collision between the two skips.
"""

THIRD_TIP = "third-tip"
"""
A third tip, for the cases that need a build to carry on past a skip.
"""

ONLY_TIP = "only-tip"
"""
The single tip of a build whose subject is the build itself rather than a collision.
"""

STALE_TIP = "stale-tip"
"""
A tip whose commits are already in the upstream base.
"""

UNRELATED_TIP = "unrelated-tip"
"""
A tip sharing no history with the base, so merging it fails without conflicting.
"""

NEEDS_THE_MODULE = "needs-the-module"
"""
The tip whose test comes to depend on a module another tip removes.
"""

REMOVES_THE_MODULE = "removes-the-module"
"""
The tip that removes it - the culprit of the integration test failure these two make together.
"""

INNOCENT_TIP = "innocent-tip"
"""
A tip merged before the breaking pair, so blaming everything already in the build is
caught naming it.
"""

A_PULL_REQUEST_NUMBER = 111
"""
The fork pull request publishing the branch a block-branch test acts on.
"""

A_FORK_REMOTE = "origin"
"""
The remote the scratch fork is reached as, which is where a record about it lives.
"""

A_MEASURED_COMMIT = "5d41402abc4b2a76b9719d911017c592a1b2c3d4"
"""
The commit the culprit of a localised failure pointed at when the break was measured.
"""

A_PARTNER_S_MEASURED_COMMIT = "7d793037a0760186574b0282f2f435e7a1b2c3d4"
"""
The commit the branch it breaks pointed at when the break was measured.
"""

CONFLICT_MARKER = "<" * 7
"""
The marker git opens a conflicted hunk with, at its default
``merge.conflictMarkerSize``.

Whether a path is *unmerged* is asked of git directly, through
:meth:`GitCommandRunner.unmerged_paths`; whether the file on disk still carries the
markers a developer edits between is only answerable by reading it, so the marker is
named here rather than spelled at the assertion.
"""

# %% the objects a build is described with


def the_pipeline_this_checkout_carries() -> dict[str, str]:
    """
    A build a rebuild would publish carries the branches the pipeline lives on, and
    publication is refused for one that does not - so a test about publishing has to
    assemble a build that does, or it is answered about something it is not asking.

    :return: Every file a rebuild needs, with the content this checkout holds at it.
    """
    return {path: (REPOSITORY_ROOT / path).read_text() for path in PIPELINE_PATHS}


def write_into(root: Path, files: Mapping[str, str]) -> None:
    """
    :param root: The checkout to write them into.
    :param files: What to write, by path, directories included.
    """
    for path, content in files.items():
        written = root / path
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_text(content)


def publishing(remote: str, branch: str) -> ProposedPush:
    """
    :param remote: The remote to publish to.
    :param branch: The branch to publish under its own name.
    :return: The push saying so, authorising no rewrite.
    """
    return ProposedPush(
        remote=remote, publication=BranchPublication.under_its_own_name(branch)
    )


def create_branch_object(
    name: str,
    number: int,
    parent: str = UPSTREAM_BASE,
    status: BranchStatus = BranchStatus.READY,
    labels: Sequence[str] = (),
    checks: ChecksVerdict | None = None,
    block_standing: BlockStanding | None = None,
) -> Branch:
    """
    :param name: The branch name.
    :param number: The fork pull request number.
    :param parent: The branch it sits on, which is its pull request's base.
    :param status: Its lifecycle position, which decides whether a build may carry it.
    :param labels: What its pull request carries, one of which may withhold it.
    :param checks: What its own checks amount to, or None where nothing has read them.
    :param block_standing: Whether the tree its block was measured in still exists, or
        None where nothing has read that.
    :return: A stack node, for the selection tests that need no repository.
    """
    return Branch(
        name=name,
        parent=parent,
        pull_request_number=number,
        status=status,
        strategy=IntegrationStrategy.MERGE,
        labels=list(labels),
        ci=None if checks is None else str(checks),
        block_standing=None if block_standing is None else str(block_standing),
    )


def create_stack_object(
    branches: list[Branch], landed: frozenset[str] = frozenset()
) -> Stack:
    """
    :param branches: The stack's nodes.
    :param landed: The branches whose commits are already in the upstream base.
    :return: A stack whose landedness is declared rather than read from git.
    """
    return Stack(
        configuration=make_configuration(),
        branches=branches,
        is_merged=lambda name: name in landed,
    )


@dataclass(frozen=True)
class RunAgainstAGivenFork(IntegrationRun):
    """
    A run whose fork is handed to it, so a command that reads or writes pull requests
    can be exercised against a scratch repository without a credential.
    """

    given: object = None
    """
    The fork this run reads and writes.
    """

    def fork(self) -> object:
        """:return: The fork it was given."""
        return self.given


def build(
    checkout: ForkCheckout,
    pull_requests: list[PullRequest],
    provenance: ResolutionProvenance | None = None,
    test_command: str | None = None,
    build_branch: str = A_BUILD_BRANCH,
) -> IntegrationReport:
    """
    Run one build against the scratch fork.

    :param checkout: The checkout to build in.
    :param pull_requests: The board entries the stack is derived from.
    :param provenance: Who authored each recorded resolution.
    :param test_command: The suite to run on the finished branch, or ``None`` to skip.
    :param build_branch: The branch to build onto.
    :return: The build report.
    """
    return build_integration(
        stack=a_stack(checkout, pull_requests),
        git=checkout.git,
        build_branch=build_branch,
        provenance=provenance or ResolutionProvenance({}),
        test_command=test_command,
    )


def outcome_for(report: IntegrationReport, branch: str) -> PullRequestStackTipOutcome:
    """
    :param report: The build report.
    :param branch: The tip to look up.
    :return: That tip's outcome.
    """
    return next(entry for entry in report.tips if entry.branch == branch)


def create_report(
    tips: tuple[PullRequestStackTipOutcome, ...] = (),
    tests_passed: bool | None = None,
    left_out: tuple[PullRequestStackTipOutcome, ...] = (),
) -> IntegrationReport:
    """
    :param tips: What became of each tip.
    :param tests_passed: Whether the suite passed, or ``None`` if it was not run.
    :param left_out: The branches the build never tried to merge.
    :return: A report to read a status off.
    """
    return IntegrationReport(
        build_branch=A_BUILD_BRANCH,
        base=UPSTREAM_BASE,
        tips=tips,
        tests_passed=tests_passed,
        left_out=left_out,
    )


def create_blocked_branch(
    branch: str, blocked_ancestor: str | None = None
) -> PullRequestStackTipOutcome:
    """
    :param branch: The branch a label withheld.
    :param blocked_ancestor: The blocked branch beneath it, if that is why.
    :return: One entry of a build's left-out list.
    """
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=0,
        status=integration_tips.TipStatus.BLOCKED,
        attributed_to=blocked_ancestor,
    )


def create_unreviewed_branch(
    branch: str, unreviewed_ancestor: str | None = None
) -> PullRequestStackTipOutcome:
    """
    :param branch: The branch left out.
    :param unreviewed_ancestor: The draft beneath it, if that is why.
    :return: One entry of a build's unreviewed list.
    """
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=1,
        status=TipStatus.UNREVIEWED,
        attributed_to=unreviewed_ancestor,
    )


def create_tip(
    branch: str,
    status: TipStatus,
    resolved_by: ResolutionAuthor | None = None,
) -> PullRequestStackTipOutcome:
    """
    :param branch: The tip's branch.
    :param status: What became of it.
    :param resolved_by: Who authored the resolution replayed for it, if any.
    :return: The outcome.
    """
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=1,
        status=status,
        resolved_by=resolved_by,
    )


def create_integration_test_failure(
    culprit: str = REMOVES_THE_MODULE,
    number: int = A_PULL_REQUEST_NUMBER,
    breaks_against: str | None = NEEDS_THE_MODULE,
    measured_over: Sequence[MeasuredHead] | None = None,
) -> IntegrationTestFailure:
    """
    :param culprit: The tip whose arrival turned the suite.
    :param number: The pull request that publishes it.
    :param breaks_against: The earlier tip it fails against alone.
    :param measured_over: The heads the break was found between, or None for the
        culprit's and its partner's at fixed commits.
    :return: A localised failure to block a branch for.
    """
    return IntegrationTestFailure(
        culprit=culprit,
        culprit_pull_request_number=number,
        already_included=(INNOCENT_TIP, NEEDS_THE_MODULE),
        breaks_against=breaks_against,
        measured_over=(
            (
                MeasuredHead(culprit, number, A_MEASURED_COMMIT),
                MeasuredHead(NEEDS_THE_MODULE, 2, A_PARTNER_S_MEASURED_COMMIT),
            )
            if measured_over is None
            else tuple(measured_over)
        ),
    )


@dataclass
class GitAnsweringForTheFork:
    """
    A runner answering what the fork has published and recorded, and remembering every
    push made through it instead of making one.
    """

    heads: dict[str, str] = field(default_factory=dict)
    """
    What the fork has each of its branches pointing at.
    """

    references: dict[str, str] = field(default_factory=dict)
    """
    Every reference below ``refs/`` the fork carries besides its branches, with its
    commit - the records a rebuild keeps there.
    """

    pushes: list[tuple[str, ...]] = field(default_factory=list)
    """
    Every push made through it, in order.
    """

    def run(self, *arguments: str) -> str:
        """:param arguments: What git was asked to do.
        :return: What the fork answers."""
        if arguments[0] == "for-each-ref":
            return "\n".join(f"{branch} {head}" for branch, head in self.heads.items())
        if arguments[0] == "ls-remote":
            pattern = arguments[-1]
            return "\n".join(
                f"{commit}\t{reference}"
                for reference, commit in self.references.items()
                if fnmatch.fnmatch(reference, pattern)
            )
        self.pushes.append(arguments)
        return ""


# %% scratch-fork arrangements more than one module builds on


def a_recorded_resolution(checkout: ForkCheckout) -> None:
    """
    Record a rerere resolution for a collision between two tips, the way a build that
    hit it and had it resolved would leave behind.

    :param checkout: The checkout whose rerere cache to seed.
    """
    for setting in integration_constants.RERERE_SETTINGS:
        checkout.git.configure(setting)
    checkout.git.checkout("recording", "origin/first-tip")
    conflicting = subprocess.run(
        ["git", "merge", "--no-edit", "origin/second-tip"],
        cwd=checkout.project_root,
        capture_output=True,
        text=True,
    )
    assert conflicting.returncode != 0, "the tips were meant to collide"
    (checkout.project_root / "contested").write_text("what a resolution chose\n")
    checkout.git.stage("contested")
    checkout.git.conclude_merge().raise_if_failed()
    checkout.git.switch_to(UPSTREAM_BASE)


def two_colliding_tips(checkout: ForkCheckout) -> list[PullRequest]:
    """
    :param checkout: The checkout to build the tips in.
    :return: The board entries for two tips that collide on one file.
    """
    checkout.branch_from(FIRST_TIP, UPSTREAM_BASE)
    checkout.commit_on(FIRST_TIP, "contested", "what the first tip wrote\n")
    checkout.git.checkout(SECOND_TIP, UPSTREAM_BASE)
    checkout.commit("contested", "what the second tip wrote\n")
    checkout.git.push(publishing("origin", SECOND_TIP))
    checkout.git.fetch("origin")
    return [
        PullRequest(number=1, head=FIRST_TIP, base=UPSTREAM_BASE, draft=False),
        PullRequest(number=2, head=SECOND_TIP, base=UPSTREAM_BASE, draft=False),
    ]


def create_red_branch(
    branch: str, red_ancestor: str | None = None
) -> PullRequestStackTipOutcome:
    """
    :param branch: The branch whose own checks failed.
    :param red_ancestor: The red branch beneath it, if that is why.
    :return: One entry of a build's left-out list.
    """
    return PullRequestStackTipOutcome(
        branch=branch,
        pull_request_number=0,
        status=integration_tips.TipStatus.CHECKS_FAILED,
        attributed_to=red_ancestor,
    )
