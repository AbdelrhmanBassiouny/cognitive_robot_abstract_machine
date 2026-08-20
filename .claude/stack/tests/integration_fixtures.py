"""
What the integration builder's tests are written in terms of.

The branches a build is made of, the factories that describe one without a repository,
and the scratch-fork arrangements more than one module builds on. Not a test module:
pytest collects ``test_*.py`` only, so nothing here runs on its own.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from stack import Branch, BranchStatus, IntegrationStrategy, PullRequest, Stack

import integration
from integration import (
    IntegrationReport,
    IntegrationTestFailure,
    PullRequestStackTipOutcome,
    ResolutionAuthor,
    ResolutionProvenance,
    TipStatus,
    build_integration,
)

from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    a_stack,
    fork_checkout,
    make_configuration,
)

# `fork_checkout` is imported for pytest to collect as a fixture; naming it
# here keeps a linter from reading the import as unused.
__all__ = ["fork_checkout"]


INTEGRATION_SCRIPT = Path(__file__).parent.parent / "integration.py"
"""
The builder under test, invoked as a subprocess wherever an exit status is the
assertion.
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

# `fork_checkout` is imported for pytest to collect as a fixture; naming it here keeps
# linters from reading the import as unused.
__all__ = ["fork_checkout"]


# %% the objects a build is described with


def create_pull_request_object(
    number: int,
    head: str,
    base: str,
    labels: list[str] | None = None,
    draft: bool = False,
) -> PullRequest:
    """
    :param number: The fork pull request number.
    :param head: The branch it publishes.
    :param base: The branch it targets, which is its parent in the stack.
    :param labels: The labels it carries.
    :param draft: Whether its author has yet to review it, which keeps it out of a build.
    :return: The board entry.
    """
    return PullRequest(
        number=number,
        head=head,
        base=base,
        draft=draft,
        labels=list(labels or []),
    )


def create_branch_object(
    name: str,
    number: int,
    parent: str = UPSTREAM_BASE,
    status: BranchStatus = BranchStatus.READY,
) -> Branch:
    """
    :param name: The branch name.
    :param number: The fork pull request number.
    :param parent: The branch it sits on, which is its pull request's base.
    :param status: Its lifecycle position, which decides whether a build may carry it.
    :return: A stack node, for the selection tests that need no repository.
    """
    return Branch(
        name=name,
        parent=parent,
        pull_request_number=number,
        status=status,
        strategy=IntegrationStrategy.MERGE,
        labels=[],
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


def branch_names_in(checkout: ForkCheckout) -> set[str]:
    """
    :param checkout: The checkout to read.
    :return: Every branch it holds, whichever one is checked out.
    """
    return set(checkout.git.branch_names())


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
    unreviewed: tuple[PullRequestStackTipOutcome, ...] = (),
) -> IntegrationReport:
    """
    :param tips: What became of each tip.
    :param tests_passed: Whether the suite passed, or ``None`` if it was not run.
    :param unreviewed: The branches the build left out as unreviewed.
    :return: A report to read a status off.
    """
    return IntegrationReport(
        build_branch=A_BUILD_BRANCH,
        base=UPSTREAM_BASE,
        tips=tips,
        tests_passed=tests_passed,
        unreviewed=unreviewed,
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
) -> IntegrationTestFailure:
    """
    :param culprit: The tip whose arrival turned the suite.
    :param number: The pull request that publishes it.
    :param breaks_against: The earlier tip it fails against alone.
    :return: A localised failure to block a branch for.
    """
    return IntegrationTestFailure(
        culprit=culprit,
        culprit_pull_request_number=number,
        already_included=(INNOCENT_TIP, NEEDS_THE_MODULE),
        breaks_against=breaks_against,
    )


# %% scratch-fork arrangements more than one module builds on


def a_recorded_resolution(checkout: ForkCheckout) -> None:
    """
    Record a rerere resolution for a collision between two tips, the way a build that
    hit it and had it resolved would leave behind.

    :param checkout: The checkout whose rerere cache to seed.
    """
    for setting in integration.RERERE_SETTINGS:
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
    checkout.git.push_refspec("origin", "second-tip:second-tip")
    checkout.git.fetch("origin")
    return [
        create_pull_request_object(1, FIRST_TIP, UPSTREAM_BASE),
        create_pull_request_object(2, SECOND_TIP, UPSTREAM_BASE),
    ]
