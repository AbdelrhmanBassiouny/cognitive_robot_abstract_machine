"""
Tests for the integration builder - upstream main plus every in-flight stack tip.

Nearly everything here is only true of a real repository: which tip a conflict is
attributed to, whether a replayed resolution is distinguishable from a merge that never
began, whether a build published anything. Those run against real git in the scratch
fork ``test_maintenance`` already builds, with bare repositories standing in for the
fork and the upstream, so nothing touches the network.

Ordering, the build branch's name and the exit status are pure, and are tested as such.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from stack import Branch, BranchStatus, IntegrationStrategy, PullRequest, Stack

import integration
from integration import (
    IntegrationExitCode,
    IntegrationReport,
    ResolutionAuthor,
    ResolutionProvenance,
    TipOutcome,
    TipStatus,
    build_branch_name,
    build_integration,
    exit_code_for,
    exit_code_for_bisect,
    tips_of,
)

from test_maintenance import ForkCheckout, a_stack, fork_checkout, make_configuration

INTEGRATION_SCRIPT = Path(__file__).parent.parent / "integration.py"
"""
The builder under test, invoked as a subprocess wherever an exit status is the
assertion.
"""

UPSTREAM_BASE = "main"
"""
The branch every stack in these tests ultimately targets, and the base every build
starts from.
"""

A_BUILD_BRANCH = "integration-20260810-120000"
"""
A fixed build branch name, so a test asserting on content never depends on the clock.
"""

# `fork_checkout` is imported for pytest to collect as a fixture; naming it here keeps
# linters from reading the import as unused.
__all__ = ["fork_checkout"]


# %% building the stack the builder consumes


def a_pull_request(
    number: int, head: str, base: str, labels: list[str] | None = None
) -> PullRequest:
    """
    :param number: The fork pull request number.
    :param head: The branch it publishes.
    :param base: The branch it targets, which is its parent in the stack.
    :param labels: The labels it carries.
    :return: The board entry.
    """
    return PullRequest(
        number=number,
        head=head,
        base=base,
        draft=False,
        labels=list(labels or []),
    )


def a_branch(name: str, number: int, parent: str = UPSTREAM_BASE) -> Branch:
    """
    :param name: The branch name.
    :param number: The fork pull request number.
    :param parent: The branch it sits on, which is its pull request's base.
    :return: A stack node, for the selection tests that need no repository.
    """
    return Branch(
        name=name,
        parent=parent,
        pull_request_number=number,
        status=BranchStatus.READY,
        strategy=IntegrationStrategy.MERGE,
        labels=[],
    )


def a_stack_of(branches: list[Branch], landed: frozenset[str] = frozenset()) -> Stack:
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


def outcome_for(report: IntegrationReport, branch: str) -> TipOutcome:
    """
    :param report: The build report.
    :param branch: The tip to look up.
    :return: That tip's outcome.
    """
    return next(entry for entry in report.tips if entry.branch == branch)


# %% which branches a build is made of


def test_only_the_tip_of_a_stack_is_merged():
    """
    A tip contains its own stack, so merging its parent as well would merge the same
    commits twice and say nothing new.
    """
    tips = tips_of(
        a_stack_of([a_branch("bottom", 1), a_branch("top", 2, parent="bottom")])
    )

    assert [tip.name for tip in tips] == ["top"]


def test_a_branch_already_landed_upstream_is_left_out():
    """
    Its commits are in the base the build starts from, so merging it adds nothing.
    """
    tips = tips_of(
        a_stack_of(
            [a_branch("landed", 1), a_branch("in-flight", 2)],
            landed=frozenset({"landed"}),
        )
    )

    assert [tip.name for tip in tips] == ["in-flight"]


def test_tips_are_merged_in_ascending_pull_request_order():
    """
    Once a conflict can skip a tip, merge order decides *which* tip is skipped - so it
    is stated rather than left to whatever order the board happened to arrive in.
    """
    tips = tips_of(
        a_stack_of(
            [a_branch("later", 9), a_branch("earlier", 2), a_branch("middle", 5)]
        )
    )

    assert [tip.name for tip in tips] == ["earlier", "middle", "later"]


# %% the build branch's own name


def test_a_build_is_named_so_it_can_coexist_with_the_pointer():
    """
    Git stores refs as files, so ``refs/heads/integration/<timestamp>`` cannot exist
    while ``refs/heads/integration`` does. The separator is a hyphen for that reason,
    which looks like a style choice and is not.
    """
    name = build_branch_name(datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc))

    assert name == "integration-20260810-120000"
    assert not name.startswith(f"{integration.POINTER_BRANCH}/")


def test_the_pointer_moves_to_the_build_that_finished(fork_checkout: ForkCheckout):
    """
    The pointer is what a developer checks out, so it names the newest build rather
    than a build having to be looked up by timestamp.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)

    build(fork_checkout, [a_pull_request(1, "only-tip", UPSTREAM_BASE)])

    assert fork_checkout.run_git(
        "rev-parse", integration.POINTER_BRANCH
    ) == fork_checkout.run_git("rev-parse", A_BUILD_BRANCH)


# %% merging the tips


def test_a_build_contains_every_cleanly_merging_tip(fork_checkout: ForkCheckout):
    """
    The whole point of the branch: one checkout carrying every in-flight feature.
    """
    fork_checkout.branch_from("first-tip", UPSTREAM_BASE)
    fork_checkout.branch_from("second-tip", UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [
            a_pull_request(1, "first-tip", UPSTREAM_BASE),
            a_pull_request(2, "second-tip", UPSTREAM_BASE),
        ],
    )

    assert [entry.status for entry in report.tips] == [
        TipStatus.MERGED,
        TipStatus.MERGED,
    ]
    fork_checkout.run_git("checkout", "--quiet", A_BUILD_BRANCH)
    assert (fork_checkout.project_root / "first-tip-file").exists()
    assert (fork_checkout.project_root / "second-tip-file").exists()


def test_a_conflicting_tip_is_skipped_and_the_build_continues(
    fork_checkout: ForkCheckout,
):
    """
    A build that halted on the first conflict would leave nothing to work from, which
    is the entire thing the branch exists to provide.
    """
    fork_checkout.branch_from("first-tip", UPSTREAM_BASE)
    fork_checkout.commit_on("first-tip", "contested", "what the first tip wrote\n")
    fork_checkout.run_git("checkout", "--quiet", "-B", "second-tip", UPSTREAM_BASE)
    fork_checkout.commit("contested", "what the second tip wrote\n")
    fork_checkout.run_git("push", "--quiet", "origin", "second-tip:second-tip")
    fork_checkout.branch_from("third-tip", UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [
            a_pull_request(1, "first-tip", UPSTREAM_BASE),
            a_pull_request(2, "second-tip", UPSTREAM_BASE),
            a_pull_request(3, "third-tip", UPSTREAM_BASE),
        ],
    )

    assert outcome_for(report, "second-tip").status is TipStatus.SKIPPED
    assert outcome_for(report, "third-tip").status is TipStatus.MERGED
    fork_checkout.run_git("checkout", "--quiet", A_BUILD_BRANCH)
    assert (fork_checkout.project_root / "third-tip-file").exists()


def test_a_skipped_tip_names_the_tip_it_collided_with(fork_checkout: ForkCheckout):
    """
    "second-tip skipped" is not actionable; the pair is. Neither branch is at fault on
    its own, so the report names both and leaves the judgement to a reader.
    """
    fork_checkout.branch_from("first-tip", UPSTREAM_BASE)
    fork_checkout.commit_on("first-tip", "contested", "what the first tip wrote\n")
    fork_checkout.run_git("checkout", "--quiet", "-B", "second-tip", UPSTREAM_BASE)
    fork_checkout.commit("contested", "what the second tip wrote\n")
    fork_checkout.run_git("push", "--quiet", "origin", "second-tip:second-tip")

    report = build(
        fork_checkout,
        [
            a_pull_request(1, "first-tip", UPSTREAM_BASE),
            a_pull_request(2, "second-tip", UPSTREAM_BASE),
        ],
    )

    skipped = outcome_for(report, "second-tip")
    assert skipped.collided_with == "first-tip"
    assert skipped.conflicting_paths == ("contested",)


def test_a_tip_conflicting_with_the_base_itself_names_the_base(
    fork_checkout: ForkCheckout,
):
    """
    A tip can be stale against the upstream rather than colliding with a sibling, and
    naming a sibling that had nothing to do with it would send its owner somewhere
    pointless.
    """
    fork_checkout.run_git("checkout", "--quiet", "-B", "stale-tip", UPSTREAM_BASE)
    fork_checkout.commit("a-file", "what the stale tip wrote\n")
    fork_checkout.run_git("push", "--quiet", "origin", "stale-tip:stale-tip")
    fork_checkout.run_git("checkout", "--quiet", UPSTREAM_BASE)
    fork_checkout.commit("a-file", "what the upstream moved on to\n")
    fork_checkout.run_git("push", "--quiet", "cram2", UPSTREAM_BASE)
    fork_checkout.run_git("fetch", "--quiet", "cram2")

    report = build(fork_checkout, [a_pull_request(1, "stale-tip", UPSTREAM_BASE)])

    skipped = outcome_for(report, "stale-tip")
    assert skipped.status is TipStatus.SKIPPED
    assert skipped.collided_with == UPSTREAM_BASE


def test_an_integration_stopped_before_it_began_is_not_reported_as_a_conflict(
    fork_checkout: ForkCheckout,
):
    """
    A merge also refuses on unrelated histories, an untracked file in the way, or a
    reference that does not resolve - none of which leave unmerged paths, and none of
    which are the tip owner's to fix. Reporting them as conflicts is the false-positive
    class the maintenance executor already had to correct once.
    """
    fork_checkout.run_git("checkout", "--quiet", "--orphan", "unrelated-tip")
    fork_checkout.run_git("rm", "--quiet", "-rf", ".")
    fork_checkout.commit("its-own-file", "a history sharing no commit\n")
    fork_checkout.run_git("push", "--quiet", "origin", "unrelated-tip:unrelated-tip")
    fork_checkout.run_git("fetch", "--quiet", "origin")

    report = build(fork_checkout, [a_pull_request(1, "unrelated-tip", UPSTREAM_BASE)])

    stopped = outcome_for(report, "unrelated-tip")
    assert stopped.status is TipStatus.INTEGRATION_FAILED
    assert stopped.conflicting_paths == ()
    assert stopped.explanation != ""


# %% replayed resolutions


def a_recorded_resolution(checkout: ForkCheckout) -> None:
    """
    Record a rerere resolution for a collision between two tips, the way a build that
    hit it and had it resolved would leave behind.

    :param checkout: The checkout whose rerere cache to seed.
    """
    checkout.run_git("config", "rerere.enabled", "true")
    checkout.run_git("config", "rerere.autoupdate", "true")
    checkout.run_git("checkout", "--quiet", "-B", "recording", "origin/first-tip")
    conflicting = subprocess.run(
        ["git", "merge", "--no-edit", "origin/second-tip"],
        cwd=checkout.project_root,
        capture_output=True,
        text=True,
    )
    assert conflicting.returncode != 0, "the tips were meant to collide"
    (checkout.project_root / "contested").write_text("what a resolution chose\n")
    checkout.run_git("add", "contested")
    checkout.run_git("commit", "--quiet", "--no-edit")
    checkout.run_git("checkout", "--quiet", UPSTREAM_BASE)


def two_colliding_tips(checkout: ForkCheckout) -> list[PullRequest]:
    """
    :param checkout: The checkout to build the tips in.
    :return: The board entries for two tips that collide on one file.
    """
    checkout.branch_from("first-tip", UPSTREAM_BASE)
    checkout.commit_on("first-tip", "contested", "what the first tip wrote\n")
    checkout.run_git("checkout", "--quiet", "-B", "second-tip", UPSTREAM_BASE)
    checkout.commit("contested", "what the second tip wrote\n")
    checkout.run_git("push", "--quiet", "origin", "second-tip:second-tip")
    checkout.run_git("fetch", "--quiet", "origin")
    return [
        a_pull_request(1, "first-tip", UPSTREAM_BASE),
        a_pull_request(2, "second-tip", UPSTREAM_BASE),
    ]


def test_a_replayed_resolution_is_never_reported_as_a_clean_merge(
    fork_checkout: ForkCheckout,
):
    """
    rerere makes the collision invisible - the merge succeeds and the branch builds -
    and reporting that as clean would hide the fact that two branches still conflict
    upstream. A replay buys a working daily driver, not a discharged obligation.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    a_recorded_resolution(fork_checkout)

    report = build(fork_checkout, pull_requests)

    replayed = outcome_for(report, "second-tip")
    assert replayed.status is TipStatus.REPLAYED
    assert replayed.collided_with == "first-tip"


def test_a_replayed_resolution_carries_the_author_that_recorded_it(
    fork_checkout: ForkCheckout,
):
    """
    A resolution a skill wrote is replayed unreviewed on every later build, which is a
    different proposition from replaying one a developer wrote - so the report says
    which, rather than leaving them indistinguishable.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    a_recorded_resolution(fork_checkout)

    report = build(
        fork_checkout,
        pull_requests,
        provenance=ResolutionProvenance({"second-tip": ResolutionAuthor.SKILL}),
    )

    assert outcome_for(report, "second-tip").resolved_by is ResolutionAuthor.SKILL


def test_a_resolution_nobody_claimed_is_read_as_a_developer_s_own(
    fork_checkout: ForkCheckout,
):
    """
    The skill records every resolution it writes, so an unrecorded one is a developer's
    - and reading it as machine-authored would flag the one case that was always
    acceptable.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    a_recorded_resolution(fork_checkout)

    report = build(fork_checkout, pull_requests)

    assert outcome_for(report, "second-tip").resolved_by is ResolutionAuthor.HUMAN


def test_provenance_round_trips_through_the_file_it_is_persisted_in(tmp_path: Path):
    """
    Containers are ephemeral, so the authorship of a recorded resolution has to survive
    somewhere other than the cache it describes.
    """
    path = tmp_path / "resolution-authors.json"
    ResolutionProvenance({"a-branch": ResolutionAuthor.SKILL}).write(path)

    assert ResolutionProvenance.read(path).author_for("a-branch") is (
        ResolutionAuthor.SKILL
    )


def test_provenance_missing_altogether_reads_as_no_claims(tmp_path: Path):
    """
    A first build on a fresh container has no manifest, which is not an error.
    """
    assert ResolutionProvenance.read(tmp_path / "absent.json").author_for("x") is (
        ResolutionAuthor.HUMAN
    )


def a_run(checkout: ForkCheckout) -> integration.IntegrationRun:
    """
    :param checkout: The checkout to run in.
    :return: A run wired to the scratch fork, without asking GitHub anything.
    """
    return integration.IntegrationRun(
        configuration=make_configuration(), git=checkout.git
    )


def test_a_staged_conflict_is_left_live_for_a_resolution_to_be_written_into(
    fork_checkout: ForkCheckout,
):
    """
    What goes into the conflicted files is the judgement the script does not make, so it
    reproduces the collision and stops - handing back somewhere to make it.
    """
    two_colliding_tips(fork_checkout)

    staged = a_run(fork_checkout).stage_conflict("first-tip", "second-tip")

    assert staged["conflicting_paths"] == ["contested"]
    assert "<<<<<<<" in (Path(staged["worktree"]) / "contested").read_text()


def test_a_recorded_resolution_is_replayed_by_the_next_build(
    fork_checkout: ForkCheckout,
):
    """
    The round trip is the point: a resolution recorded once is what stops the same
    collision costing a skipped tip on every later build.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    run = a_run(fork_checkout)
    staged = run.stage_conflict("first-tip", "second-tip")
    (Path(staged["worktree"]) / "contested").write_text("what a resolution chose\n")
    run.record_resolution(
        worktree=Path(staged["worktree"]),
        tip="second-tip",
        author=ResolutionAuthor.SKILL,
    )

    report = build(
        fork_checkout,
        pull_requests,
        provenance=ResolutionProvenance.read(run.provenance_path()),
    )

    replayed = outcome_for(report, "second-tip")
    assert replayed.status is TipStatus.REPLAYED
    assert replayed.resolved_by is ResolutionAuthor.SKILL


def test_recording_a_resolution_leaves_no_worktree_behind(fork_checkout: ForkCheckout):
    """
    A resolution is recorded into the cache, not into a checkout somebody has to
    remember to remove.
    """
    two_colliding_tips(fork_checkout)
    run = a_run(fork_checkout)
    staged = run.stage_conflict("first-tip", "second-tip")
    (Path(staged["worktree"]) / "contested").write_text("what a resolution chose\n")

    run.record_resolution(
        worktree=Path(staged["worktree"]),
        tip="second-tip",
        author=ResolutionAuthor.HUMAN,
    )

    assert "stack-resolve-" not in fork_checkout.run_git("worktree", "list")


def test_recording_a_resolution_keeps_the_claims_already_made(
    fork_checkout: ForkCheckout,
):
    """
    The manifest accumulates across builds, so a write that replaced it would forget
    every earlier resolution's author and read them all back as a developer's.
    """
    two_colliding_tips(fork_checkout)
    run = a_run(fork_checkout)
    ResolutionProvenance({"an-earlier-tip": ResolutionAuthor.SKILL}).write(
        run.provenance_path()
    )
    staged = run.stage_conflict("first-tip", "second-tip")
    (Path(staged["worktree"]) / "contested").write_text("what a resolution chose\n")

    run.record_resolution(
        worktree=Path(staged["worktree"]),
        tip="second-tip",
        author=ResolutionAuthor.HUMAN,
    )

    recorded = ResolutionProvenance.read(run.provenance_path())
    assert recorded.author_for("an-earlier-tip") is ResolutionAuthor.SKILL


# %% what a build does not do


def test_a_build_publishes_nothing(fork_checkout: ForkCheckout):
    """
    The script never writes to a branch: the integration branch is local, and the tips
    it merges belong to other people. Asserted on the fork's own refs rather than on
    the absence of a push, since a push that changed nothing looks the same either way.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)
    published_before = fork_checkout.commit_on_the_fork("only-tip")

    build(fork_checkout, [a_pull_request(1, "only-tip", UPSTREAM_BASE)])

    assert fork_checkout.commit_on_the_fork("only-tip") == published_before
    assert (
        fork_checkout.run_git("ls-remote", "origin", f"refs/heads/{A_BUILD_BRANCH}")
        == ""
    )


def test_a_build_leaves_the_invoking_checkout_on_its_own_branch(
    fork_checkout: ForkCheckout,
):
    """
    A build is something a developer runs while working, so it borrows the checkout's
    branch and gives it back rather than parking them on a build of its own.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)
    fork_checkout.run_git("checkout", "--quiet", "only-tip")

    build(fork_checkout, [a_pull_request(1, "only-tip", UPSTREAM_BASE)])

    assert fork_checkout.run_git("branch", "--show-current") == "only-tip"


def test_a_build_leaves_no_worktree_of_its_own_behind(fork_checkout: ForkCheckout):
    """
    Every branch switch happens in a worktree outside the project, which is removed
    whether the build finished or was abandoned.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)

    build(fork_checkout, [a_pull_request(1, "only-tip", UPSTREAM_BASE)])

    assert "stack-restack-" not in fork_checkout.run_git("worktree", "list")


# %% running the suite on the finished branch


def test_a_passing_suite_leaves_the_build_a_success(fork_checkout: ForkCheckout):
    """
    The single run on the finished branch is what replaced the per-branch CI gate.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [a_pull_request(1, "only-tip", UPSTREAM_BASE)],
        test_command=f"{sys.executable} -c pass",
    )

    assert report.tests_passed is True
    assert exit_code_for(report) is IntegrationExitCode.SUCCESS


def test_a_failing_suite_is_never_reported_as_a_clean_build(
    fork_checkout: ForkCheckout,
):
    """
    A semantic conflict - one branch renaming what another calls - merges cleanly and
    breaks on import, so a green merge says nothing about whether the result works.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [a_pull_request(1, "only-tip", UPSTREAM_BASE)],
        test_command=f"{sys.executable} -c 'raise SystemExit(1)'",
    )

    assert report.tests_passed is False
    assert exit_code_for(report) is IntegrationExitCode.TESTS_FAILED


def test_a_suite_that_was_not_run_is_neither_a_pass_nor_a_failure(
    fork_checkout: ForkCheckout,
):
    """
    ``--no-test`` has to be distinguishable from a suite that ran and passed, or a
    caller reading the document cannot tell a checked build from an unchecked one.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)

    report = build(fork_checkout, [a_pull_request(1, "only-tip", UPSTREAM_BASE)])

    assert report.tests_passed is None
    assert exit_code_for(report) is IntegrationExitCode.SUCCESS


def test_a_build_asked_for_a_suite_it_has_no_command_for_is_refused():
    """
    Reading an unconfigured suite as one that passed is the silence running it exists to
    break, so it is refused - and refused before anything is built, since a build that
    cost minutes only to find it cannot be checked has wasted them.
    """
    configuration = dataclasses.replace(
        make_configuration(), integration_test_command=""
    )

    with pytest.raises(integration.TestCommandNotConfiguredError):
        integration.BuildCommand()._test_command(configuration, run_tests=True)


def test_a_build_that_was_told_not_to_test_needs_no_command():
    """
    ``--no-test`` is the way past the refusal above, rather than a reason to configure a
    suite a checkout has no use for.
    """
    configuration = dataclasses.replace(
        make_configuration(), integration_test_command=""
    )

    assert integration.BuildCommand()._test_command(configuration, run_tests=False) is (
        None
    )


def test_a_failing_suite_over_a_machine_written_replay_is_its_own_status(
    fork_checkout: ForkCheckout,
):
    """
    Re-resolving into the same failure is how a build starts thrashing, so the status a
    caller acts on distinguishes this from an ordinary red suite: report and stop.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    a_recorded_resolution(fork_checkout)

    report = build(
        fork_checkout,
        pull_requests,
        provenance=ResolutionProvenance({"second-tip": ResolutionAuthor.SKILL}),
        test_command=f"{sys.executable} -c 'raise SystemExit(1)'",
    )

    assert exit_code_for(report) is IntegrationExitCode.SUSPECT_REPLAY


# %% localising a semantic break


THE_SUITE_RUNNER = """\
import pathlib
import sys

# Only a build carrying the test needs the module it imports, which is what makes this
# fail for a combination of tips rather than for either one of them.
if pathlib.Path("test_needs_the_module.py").exists():
    import a_module

    assert a_module.VALUE
sys.exit(0)
"""
"""
A suite whose verdict depends on what the build actually contains, so a semantic break
is reproduced rather than declared. Lives on the base, where every build has it.
"""


def two_tips_that_break_only_together(checkout: ForkCheckout) -> list[PullRequest]:
    """
    Build tips that each pass alone, merge cleanly, and fail the suite together.

    The shape a semantic break really takes: one branch's test comes to depend on
    something another branch removes. Neither is wrong, neither conflicts textually, and
    only a build carrying both can see it. An innocent tip merges first, so a bisect that
    blamed everything already in the build would be caught naming it.

    :param checkout: The checkout to build them in.
    :return: The board entries.
    """
    checkout.run_git("checkout", "--quiet", UPSTREAM_BASE)
    (checkout.project_root / "a_module.py").write_text("VALUE = 1\n")
    (checkout.project_root / "check_the_build.py").write_text(THE_SUITE_RUNNER)
    checkout.run_git("add", "a_module.py", "check_the_build.py")
    checkout.run_git("commit", "--quiet", "-m", "the module both tips are about")
    checkout.run_git("push", "--quiet", "origin", UPSTREAM_BASE)
    checkout.run_git("push", "--quiet", "cram2", UPSTREAM_BASE)
    checkout.run_git("fetch", "--quiet", "cram2")

    checkout.branch_from("innocent-tip", UPSTREAM_BASE)

    checkout.run_git("checkout", "--quiet", "-B", "needs-the-module", UPSTREAM_BASE)
    (checkout.project_root / "test_needs_the_module.py").write_text(
        "import a_module\n\n\ndef test_it_is_there():\n    assert a_module.VALUE\n"
    )
    checkout.run_git("add", "test_needs_the_module.py")
    checkout.run_git("commit", "--quiet", "-m", "a test that needs the module")
    checkout.run_git("push", "--quiet", "origin", "needs-the-module:needs-the-module")

    checkout.run_git("checkout", "--quiet", "-B", "removes-the-module", UPSTREAM_BASE)
    checkout.run_git("rm", "--quiet", "a_module.py")
    checkout.run_git("commit", "--quiet", "-m", "the module goes away")
    checkout.run_git(
        "push", "--quiet", "origin", "removes-the-module:removes-the-module"
    )
    checkout.run_git("fetch", "--quiet", "origin")
    checkout.run_git("checkout", "--quiet", UPSTREAM_BASE)
    return [
        a_pull_request(1, "innocent-tip", UPSTREAM_BASE),
        a_pull_request(2, "needs-the-module", UPSTREAM_BASE),
        a_pull_request(3, "removes-the-module", UPSTREAM_BASE),
    ]


def bisect(
    checkout: ForkCheckout, pull_requests: list[PullRequest], test_command: str
) -> integration.BisectReport:
    """
    Run one bisect against the scratch fork.

    :param checkout: The checkout to build in.
    :param pull_requests: The board entries the stack is derived from.
    :param test_command: The suite that decides whether a build works.
    :return: What it localised.
    """
    return integration.bisect_integration(
        stack=a_stack(checkout, pull_requests),
        git=checkout.git,
        build_branch=A_BUILD_BRANCH,
        provenance=ResolutionProvenance({}),
        test_command=test_command,
    )


A_SUITE_OVER_THE_BUILD = f"{sys.executable} check_the_build.py"
"""
The command that runs :data:`THE_SUITE_RUNNER` against whatever a build contains.
"""


def test_a_bisect_names_the_tip_whose_arrival_broke_the_suite(
    fork_checkout: ForkCheckout,
):
    """
    A build that merged cleanly and then failed says nothing about which branch to look
    at. Adding tips one at a time until the suite turns does, and it is the same order
    the build itself used - so the answer describes the build that failed rather than
    some other ordering of it.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    report = bisect(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert report.semantic_break is not None
    assert report.semantic_break.culprit == "removes-the-module"


def test_a_bisect_names_the_tip_the_culprit_actually_breaks_against(
    fork_checkout: ForkCheckout,
):
    """
    Naming everything already in the build is not actionable when only one of them is
    involved - the innocent tip merged first has nothing to do with it.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    report = bisect(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert report.semantic_break.breaks_against == "needs-the-module"


def test_a_bisect_of_a_build_that_works_localises_nothing(fork_checkout: ForkCheckout):
    """
    There is no break to attribute, and inventing one would send somebody after a branch
    that is fine.
    """
    fork_checkout.branch_from("only-tip", UPSTREAM_BASE)

    report = bisect(
        fork_checkout,
        [a_pull_request(1, "only-tip", UPSTREAM_BASE)],
        f"{sys.executable} -c pass",
    )

    assert report.semantic_break is None
    assert exit_code_for_bisect(report) is IntegrationExitCode.SUCCESS


def test_a_localised_break_is_never_reported_as_a_clean_bisect(
    fork_checkout: ForkCheckout,
):
    """
    The exit status is the only half a caller with no model in it reads, and a bisect
    that found the break is the case it most needs to hear about.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    report = bisect(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    assert exit_code_for_bisect(report) is IntegrationExitCode.TESTS_FAILED


def test_a_bisect_leaves_no_branch_of_its_own_behind(fork_checkout: ForkCheckout):
    """
    Narrowing asks one question per candidate, and a branch per question would
    accumulate a ref for every break ever localised. Only the build it assembled is a
    thing anybody meant to keep.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    bisect(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD)

    branches = {
        line.strip().lstrip("* ")
        for line in fork_checkout.run_git("branch", "--list").splitlines()
    }
    assert not {branch for branch in branches if "against" in branch}


def test_a_bisect_report_serialises_what_it_localised(fork_checkout: ForkCheckout):
    """
    ``--json`` is what the triage skill reads, so the pair has to survive the document.
    """
    pull_requests = two_tips_that_break_only_together(fork_checkout)

    document = json.loads(
        bisect(fork_checkout, pull_requests, A_SUITE_OVER_THE_BUILD).as_json()
    )

    assert document["status"] == "tests-failed"
    assert document["semantic_break"]["culprit"] == "removes-the-module"
    assert document["semantic_break"]["breaks_against"] == "needs-the-module"


# %% the exit status every build derives from what it left behind


def a_report(
    tips: tuple[TipOutcome, ...] = (),
    tests_passed: bool | None = None,
) -> IntegrationReport:
    """
    :param tips: What became of each tip.
    :param tests_passed: Whether the suite passed, or ``None`` if it was not run.
    :return: A report to read a status off.
    """
    return IntegrationReport(
        build_branch=A_BUILD_BRANCH,
        base=UPSTREAM_BASE,
        tips=tips,
        tests_passed=tests_passed,
    )


def a_tip(
    branch: str,
    status: TipStatus,
    resolved_by: ResolutionAuthor | None = None,
) -> TipOutcome:
    """
    :param branch: The tip's branch.
    :param status: What became of it.
    :param resolved_by: Who authored the resolution replayed for it, if any.
    :return: The outcome.
    """
    return TipOutcome(
        branch=branch,
        pull_request_number=1,
        status=status,
        resolved_by=resolved_by,
    )


def test_a_build_that_merged_everything_is_a_success():
    """
    :return: Nothing; the clean case has to stay clean or every status below is noise.
    """
    assert (
        exit_code_for(a_report(tips=(a_tip("a", TipStatus.MERGED),)))
        is IntegrationExitCode.SUCCESS
    )


@pytest.mark.parametrize(
    "status",
    [TipStatus.SKIPPED, TipStatus.INTEGRATION_FAILED],
)
def test_a_tip_left_out_of_the_build_is_never_reported_as_a_clean_build(
    status: TipStatus,
):
    """
    A caller acting on the status alone - which is what a scheduled job does - would
    otherwise read a partial build as a whole one.

    :param status: A status meaning the tip did not make it into the build.
    """
    assert (
        exit_code_for(a_report(tips=(a_tip("a", status),)))
        is IntegrationExitCode.TIP_LEFT_OUT
    )


def test_a_replayed_tip_alone_does_not_spoil_the_status():
    """
    A replay is reported, not treated as a failure: the tip is in the build and the
    branch works. What it must not do is read as a clean *merge*, which is the tip's
    own status rather than the build's.
    """
    assert (
        exit_code_for(a_report(tips=(a_tip("a", TipStatus.REPLAYED),)))
        is IntegrationExitCode.SUCCESS
    )


def test_a_failing_suite_outranks_a_tip_left_out():
    """
    A build missing one branch is still usable; a build whose suite fails is not.
    """
    assert (
        exit_code_for(
            a_report(tips=(a_tip("a", TipStatus.SKIPPED),), tests_passed=False)
        )
        is IntegrationExitCode.TESTS_FAILED
    )


def test_every_status_names_itself_for_a_caller():
    """
    A process exit status can only be an integer, so the name accompanies the number
    rather than a caller having to decode one.
    """
    assert IntegrationExitCode.TIP_LEFT_OUT.name_for_a_caller == "tip-left-out"


def test_the_report_serialises_what_the_build_left_behind():
    """
    ``--json`` is what a caller with no model in it reads, so the document leads with
    the status rather than burying it among the outcomes.
    """
    document = json.loads(a_report(tips=(a_tip("a-tip", TipStatus.SKIPPED),)).as_json())

    assert document["status"] == "tip-left-out"
    assert document["exit_code"] == int(IntegrationExitCode.TIP_LEFT_OUT)
    assert document["tips"][0]["branch"] == "a-tip"


# %% the command line


def run_integration(
    checkout: ForkCheckout, *arguments: str
) -> subprocess.CompletedProcess:
    """
    Invoke the builder as a subprocess, where the exit status is the assertion.

    :param checkout: The checkout to run in.
    :param arguments: The command line to pass.
    :return: The finished process.
    """
    environment = {
        key: value
        for key, value in dict(**subprocess.os.environ).items()
        if key not in {"GH_TOKEN", "GITHUB_TOKEN"}
    }
    return subprocess.run(
        [sys.executable, str(INTEGRATION_SCRIPT), *arguments],
        cwd=checkout.project_root,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_a_command_that_exists_is_reachable_from_the_command_line():
    """
    Commands are found from their own subclasses, so one that exists cannot be left
    unreachable by forgetting to list it.
    """
    assert "build" in {command.invoked_as for command in integration.COMMANDS}


def test_a_missing_credential_is_its_own_exit_status(fork_checkout: ForkCheckout):
    """
    The fork's open pull requests are what a build is derived from, so a run without a
    token is sent after a token rather than after something it cannot fix.
    """
    fork_checkout.run_git("remote", "remove", "cram2")

    finished = run_integration(fork_checkout, "build", "--no-test")

    assert finished.returncode == int(IntegrationExitCode.CREDENTIAL_UNAVAILABLE)
    assert IntegrationExitCode.CREDENTIAL_UNAVAILABLE.name_for_a_caller in (
        finished.stderr
    )
