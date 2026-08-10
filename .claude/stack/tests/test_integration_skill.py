"""
The things about the triage skill worth asserting from code.

The skill is instructions, so most of what it says can only be checked by reading it.
What is worth a test is what it must *not* say, and the handful of names it shares with
the module it drives: a status it matches on that no longer exists is an instruction
nobody can follow, and it would go stale silently.
"""

from __future__ import annotations

from pathlib import Path

from integration import IntegrationExitCode, ResolutionAuthor, TipStatus

from test_maintenance_skill import candidate_forks

TRIAGE_SKILL_DOCUMENT = (
    Path(__file__).parents[3] / ".claude/skills/integration-conflict-triage/SKILL.md"
)
"""
The instructions a triage pass follows.
"""


def test_the_skill_names_no_fork_of_its_own():
    """
    The skill runs on whichever fork invoked it, so a repository named in it is an
    instruction to operate on somebody else's.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()

    for fork in candidate_forks():
        assert fork.owner not in skill
        assert str(fork) not in skill


def test_the_skill_restores_the_tooling_without_writing_the_index():
    """
    ``git checkout <ref> -- <path>`` writes the index as well as the working tree, so
    restoring the tooling onto a branch that does not carry it would leave the files
    staged, where the next commit made on that branch would carry them in.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()

    assert "git restore --source=<ref> --worktree -- .claude/stack/" in skill
    assert "git checkout <ref> -- .claude/stack/" not in skill


def test_every_status_the_skill_acts_on_is_one_the_builder_can_emit():
    """
    The skill dispatches on the status a build exits with, so a name it matches on that
    the builder never produces is a branch of the instructions nothing reaches.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()

    for status in (
        IntegrationExitCode.SUCCESS,
        IntegrationExitCode.TIP_LEFT_OUT,
        IntegrationExitCode.TESTS_FAILED,
        IntegrationExitCode.SUSPECT_REPLAY,
    ):
        assert f"`{status.name_for_a_caller}`" in skill


def test_the_skill_triages_exactly_the_outcomes_that_leave_something_to_judge():
    """
    Only the outcomes that leave a live collision reach the reader.

    A tip that merged cleanly asks nothing of anybody, while one that was skipped or
    replayed names a pair whose collision is still there. Sending someone to look at a
    clean merge is sending them nowhere.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()

    assert f"`{TipStatus.SKIPPED}`" in skill
    assert f"`{TipStatus.REPLAYED}`" in skill
    assert f"`{TipStatus.MERGED}`" not in skill


def test_the_skill_records_its_own_resolutions_as_machine_written():
    """
    The skill claims its own resolutions rather than passing them off as a developer's.

    Provenance is the whole reason a later build can tell a replay it should trust from
    one it should not, and this skill is the only writer able to get it wrong in the
    dangerous direction.

    Asserted as an absence rather than as a sentence, computed from the authors that
    exist: the skill may name the machine-written one and no other, which stays true
    however the surrounding prose is worded.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()

    assert f"--author {ResolutionAuthor.SKILL}" in skill
    assert f"--author {ResolutionAuthor.HUMAN}" not in skill
