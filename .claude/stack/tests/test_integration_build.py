"""
Assembling the branch: what it is named, what reaches it, and what it leaves alone.
"""

from __future__ import annotations

from datetime import datetime, timezone

from stack import PullRequest

import integration
from integration import (
    TipStatus,
    build_branch_name,
)

from test_maintenance import (
    ForkCheckout,
    UPSTREAM_BASE,
    UPSTREAM_REMOTE,
    fork_checkout,  # noqa: F401  (pytest collects it as a fixture)
)

from integration_fixtures import (
    A_BUILD_BRANCH,
    FIRST_TIP,
    ONLY_TIP,
    SECOND_TIP,
    STALE_TIP,
    THIRD_TIP,
    UNRELATED_TIP,
    build,
    outcome_for,
)

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
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)

    build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    assert fork_checkout.git.commit_at(
        integration.POINTER_BRANCH
    ) == fork_checkout.git.commit_at(A_BUILD_BRANCH)


# %% merging the tips


def test_a_build_contains_every_cleanly_merging_tip(fork_checkout: ForkCheckout):
    """
    The whole point of the branch: one checkout carrying every in-flight feature.
    """
    fork_checkout.branch_from(FIRST_TIP, UPSTREAM_BASE)
    fork_checkout.branch_from(SECOND_TIP, UPSTREAM_BASE)
    pull_requests = [
        PullRequest(number=1, head=FIRST_TIP, base=UPSTREAM_BASE, draft=False),
        PullRequest(number=2, head=SECOND_TIP, base=UPSTREAM_BASE, draft=False),
    ]

    report = build(fork_checkout, pull_requests)

    assert [entry.status for entry in report.tips] == [TipStatus.MERGED] * len(
        pull_requests
    )
    fork_checkout.git.switch_to(A_BUILD_BRANCH)
    assert fork_checkout.file_added_by(FIRST_TIP).exists()
    assert fork_checkout.file_added_by(SECOND_TIP).exists()


def test_a_build_leaves_an_unreviewed_branch_out_and_says_so(
    fork_checkout: ForkCheckout,
):
    """
    The selection and the report have to be joined up: a build that quietly carried
    fewer branches than the board holds, and reported only what it did carry, would read
    as having covered everything.
    """
    reviewed = "reviewed"
    unreviewed = "unreviewed"
    fork_checkout.branch_from(reviewed, UPSTREAM_BASE)
    fork_checkout.branch_from(unreviewed, UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [
            PullRequest(number=1, head=reviewed, base=UPSTREAM_BASE, draft=False),
            PullRequest(number=2, head=unreviewed, base=UPSTREAM_BASE, draft=True),
        ],
    )

    assert [entry.branch for entry in report.tips] == [reviewed]
    assert [entry.branch for entry in report.unreviewed] == [unreviewed]
    fork_checkout.git.switch_to(A_BUILD_BRANCH)
    assert not fork_checkout.file_added_by(unreviewed).exists()


def test_a_conflicting_tip_is_skipped_and_the_build_continues(
    fork_checkout: ForkCheckout,
):
    """
    A build that halted on the first conflict would leave nothing to work from, which
    is the entire thing the branch exists to provide.
    """
    fork_checkout.branch_from(FIRST_TIP, UPSTREAM_BASE)
    fork_checkout.commit_on(FIRST_TIP, "contested", "what the first tip wrote\n")
    fork_checkout.git.checkout(SECOND_TIP, UPSTREAM_BASE)
    fork_checkout.commit("contested", "what the second tip wrote\n")
    fork_checkout.git.push_refspec("origin", f"{SECOND_TIP}:{SECOND_TIP}")
    fork_checkout.branch_from(THIRD_TIP, UPSTREAM_BASE)

    report = build(
        fork_checkout,
        [
            PullRequest(number=1, head=FIRST_TIP, base=UPSTREAM_BASE, draft=False),
            PullRequest(number=2, head=SECOND_TIP, base=UPSTREAM_BASE, draft=False),
            PullRequest(number=3, head=THIRD_TIP, base=UPSTREAM_BASE, draft=False),
        ],
    )

    assert outcome_for(report, SECOND_TIP).status is TipStatus.SKIPPED
    assert outcome_for(report, THIRD_TIP).status is TipStatus.MERGED
    fork_checkout.git.switch_to(A_BUILD_BRANCH)
    assert fork_checkout.file_added_by(THIRD_TIP).exists()


def test_a_skipped_tip_names_the_tip_it_collided_with(fork_checkout: ForkCheckout):
    """
    "second-tip skipped" is not actionable; the pair is. Neither branch is at fault on
    its own, so the report names both and leaves the judgement to a reader.
    """
    fork_checkout.branch_from(FIRST_TIP, UPSTREAM_BASE)
    fork_checkout.commit_on(FIRST_TIP, "contested", "what the first tip wrote\n")
    fork_checkout.git.checkout(SECOND_TIP, UPSTREAM_BASE)
    fork_checkout.commit("contested", "what the second tip wrote\n")
    fork_checkout.git.push_refspec("origin", f"{SECOND_TIP}:{SECOND_TIP}")

    report = build(
        fork_checkout,
        [
            PullRequest(number=1, head=FIRST_TIP, base=UPSTREAM_BASE, draft=False),
            PullRequest(number=2, head=SECOND_TIP, base=UPSTREAM_BASE, draft=False),
        ],
    )

    skipped = outcome_for(report, SECOND_TIP)
    assert skipped.attributed_to == FIRST_TIP
    assert skipped.conflicting_paths == ("contested",)


def test_a_tip_conflicting_with_the_base_itself_names_the_base(
    fork_checkout: ForkCheckout,
):
    """
    A tip can be stale against the upstream rather than colliding with a sibling, and
    naming a sibling that had nothing to do with it would send its owner somewhere
    pointless.
    """
    fork_checkout.git.checkout(STALE_TIP, UPSTREAM_BASE)
    fork_checkout.commit("a-file", "what the stale tip wrote\n")
    fork_checkout.git.push_refspec("origin", "stale-tip:stale-tip")
    fork_checkout.git.switch_to(UPSTREAM_BASE)
    fork_checkout.commit("a-file", "what the upstream moved on to\n")
    fork_checkout.git.push_refspec(UPSTREAM_REMOTE, UPSTREAM_BASE)
    fork_checkout.git.fetch(UPSTREAM_REMOTE)

    report = build(
        fork_checkout,
        [PullRequest(number=1, head=STALE_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    skipped = outcome_for(report, STALE_TIP)
    assert skipped.status is TipStatus.SKIPPED
    assert skipped.attributed_to == UPSTREAM_BASE


def test_an_integration_stopped_before_it_began_is_not_reported_as_a_conflict(
    fork_checkout: ForkCheckout,
):
    """
    A merge also refuses on unrelated histories, an untracked file in the way, or a
    reference that does not resolve - none of which leave unmerged paths, and none of
    which are the tip owner's to fix. Reporting them as conflicts is the false-positive
    class the maintenance executor already had to correct once.
    """
    fork_checkout.git.checkout_orphan(UNRELATED_TIP)
    fork_checkout.git.remove("-rf", ".")
    fork_checkout.commit("its-own-file", "a history sharing no commit\n")
    fork_checkout.git.push_refspec("origin", "unrelated-tip:unrelated-tip")
    fork_checkout.git.fetch("origin")

    report = build(
        fork_checkout,
        [PullRequest(number=1, head=UNRELATED_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    stopped = outcome_for(report, UNRELATED_TIP)
    assert stopped.status is TipStatus.INTEGRATION_FAILED
    assert stopped.conflicting_paths == ()
    assert stopped.explanation != ""


# %% what a build does not do


def test_a_build_publishes_nothing(fork_checkout: ForkCheckout):
    """
    The script never writes to a branch: the integration branch is local, and the tips
    it merges belong to other people. Asserted on the fork's own refs rather than on
    the absence of a push, since a push that changed nothing looks the same either way.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)
    published_before = fork_checkout.commit_on_the_fork(ONLY_TIP)

    build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    assert fork_checkout.commit_on_the_fork(ONLY_TIP) == published_before
    assert (
        fork_checkout.git.remote_reference("origin", f"refs/heads/{A_BUILD_BRANCH}")
        == ""
    )


def test_a_build_leaves_the_invoking_checkout_on_its_own_branch(
    fork_checkout: ForkCheckout,
):
    """
    A build is something a developer runs while working, so it borrows the checkout's
    branch and gives it back rather than parking them on a build of its own.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)
    fork_checkout.git.switch_to(ONLY_TIP)

    build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    assert fork_checkout.git.checked_out_branch() == ONLY_TIP


def test_a_build_leaves_no_worktree_of_its_own_behind(fork_checkout: ForkCheckout):
    """
    Every branch switch happens in a worktree outside the project, which is removed
    whether the build finished or was abandoned.
    """
    fork_checkout.branch_from(ONLY_TIP, UPSTREAM_BASE)

    build(
        fork_checkout,
        [PullRequest(number=1, head=ONLY_TIP, base=UPSTREAM_BASE, draft=False)],
    )

    assert not any(
        "stack-restack-" in path for path in fork_checkout.git.worktree_paths()
    )
