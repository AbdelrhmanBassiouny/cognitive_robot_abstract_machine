"""
Recorded conflict resolutions, and the replays a later build makes of them.
"""

from __future__ import annotations

from pathlib import Path

import integration
from integration import (
    ResolutionAuthor,
    ResolutionProvenance,
    TipStatus,
)

from test_maintenance import (
    ForkCheckout,
    fork_checkout,  # noqa: F401  (pytest collects it as a fixture)
    make_configuration,
)

from integration_fixtures import (
    CONFLICT_MARKER,
    FIRST_TIP,
    SECOND_TIP,
    a_recorded_resolution,
    build,
    outcome_for,
    two_colliding_tips,
)

# %% replayed resolutions


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

    replayed = outcome_for(report, SECOND_TIP)
    assert replayed.status is TipStatus.REPLAYED
    assert replayed.attributed_to == FIRST_TIP


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
        provenance=ResolutionProvenance({SECOND_TIP: ResolutionAuthor.SKILL}),
    )

    assert outcome_for(report, SECOND_TIP).resolved_by is ResolutionAuthor.SKILL


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

    assert outcome_for(report, SECOND_TIP).resolved_by is ResolutionAuthor.HUMAN


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

    staged = a_run(fork_checkout).stage_conflict(FIRST_TIP, SECOND_TIP)

    assert staged["conflicting_paths"] == ["contested"]
    assert CONFLICT_MARKER in (Path(staged["worktree"]) / "contested").read_text()


def test_a_recorded_resolution_is_replayed_by_the_next_build(
    fork_checkout: ForkCheckout,
):
    """
    The round trip is the point: a resolution recorded once is what stops the same
    collision costing a skipped tip on every later build.
    """
    pull_requests = two_colliding_tips(fork_checkout)
    run = a_run(fork_checkout)
    staged = run.stage_conflict(FIRST_TIP, SECOND_TIP)
    (Path(staged["worktree"]) / "contested").write_text("what a resolution chose\n")
    run.record_resolution(
        worktree=Path(staged["worktree"]),
        tip=SECOND_TIP,
        author=ResolutionAuthor.SKILL,
    )

    report = build(
        fork_checkout,
        pull_requests,
        provenance=ResolutionProvenance.read(run.provenance_path()),
    )

    replayed = outcome_for(report, SECOND_TIP)
    assert replayed.status is TipStatus.REPLAYED
    assert replayed.resolved_by is ResolutionAuthor.SKILL


def test_recording_a_resolution_leaves_no_worktree_behind(fork_checkout: ForkCheckout):
    """
    A resolution is recorded into the cache, not into a checkout somebody has to
    remember to remove.
    """
    two_colliding_tips(fork_checkout)
    run = a_run(fork_checkout)
    staged = run.stage_conflict(FIRST_TIP, SECOND_TIP)
    (Path(staged["worktree"]) / "contested").write_text("what a resolution chose\n")

    run.record_resolution(
        worktree=Path(staged["worktree"]),
        tip=SECOND_TIP,
        author=ResolutionAuthor.HUMAN,
    )

    assert not any(
        "stack-resolve-" in path for path in fork_checkout.git.worktree_paths()
    )


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
    staged = run.stage_conflict(FIRST_TIP, SECOND_TIP)
    (Path(staged["worktree"]) / "contested").write_text("what a resolution chose\n")

    run.record_resolution(
        worktree=Path(staged["worktree"]),
        tip=SECOND_TIP,
        author=ResolutionAuthor.HUMAN,
    )

    recorded = ResolutionProvenance.read(run.provenance_path())
    assert recorded.author_for("an-earlier-tip") is ResolutionAuthor.SKILL
