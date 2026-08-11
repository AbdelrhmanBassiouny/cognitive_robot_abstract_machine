"""
The things about the triage skill worth asserting from code.

The skill is instructions, so most of what it says can only be checked by reading it.
What is worth a test is what it must *not* say, and the handful of names it shares with
the module it drives: a status it matches on that no longer exists is an instruction
nobody can follow, and it would go stale silently.
"""

from __future__ import annotations

import re
from pathlib import Path

from integration import (
    COMMANDS,
    BisectCommand,
    IntegrationExitCode,
    ResolutionAuthor,
    TipStatus,
)

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


def test_every_command_the_skill_tells_the_reader_to_run_exists():
    """
    The skill drives the builder by naming its commands, so one it names that the
    builder does not answer is an instruction that fails where it is followed.

    Computed from the commands themselves, so adding or renaming one is what fails this
    rather than a literal list kept beside them.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()
    answered = {command.invoked_as for command in COMMANDS}

    named = set(re.findall(r"integration\.py (\S+)", skill))

    assert named, "the skill drives the builder, so it has to name at least one command"
    assert named <= answered, f"names commands that do not exist: {named - answered}"


def test_the_skill_localises_a_semantic_break_rather_than_judging_it_by_hand():
    """
    A failing suite over ten merged tips names nothing on its own, and bisecting it by
    hand is several worktrees and several suite runs - mechanical, and easy to get subtly
    wrong. The skill has to reach for the command that does it.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()

    assert f"integration.py {BisectCommand.invoked_as}" in skill


def test_the_skill_says_a_semantic_break_cannot_be_recorded():
    """
    The dangerous mistake here is reasoning by analogy from a merge collision:
    ``rerere`` replays a *conflict* resolution, a semantic break has no conflict to key
    one on, and an agent that recorded one would report a fix that does not exist.

    The document has to rule it out where a reader meets it.
    """
    skill = TRIAGE_SKILL_DOCUMENT.read_text()
    semantic_break_section = skill[skill.index("## Step 4") :]

    assert "Nothing can be recorded for a semantic break." in semantic_break_section


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
