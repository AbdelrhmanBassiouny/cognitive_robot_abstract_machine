"""
What about the maintenance skill is worth asserting from code.

The skill is instructions, so most of what it says can only be checked by reading it.
The exceptions are what it must *not* say: a repository named in it is an instruction to
operate on somebody else's fork, and a command run from the working tree is an
instruction to run whichever version the branch checked out at that moment happens to
carry. Both are absences, computed from this checkout rather than from a string written
here, which is what makes them worth a test where a prose assertion would not be.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from maintenance_commands import PendingPromotionsCommand
from stack import (
    CONFIGURATION_PATH,
    ENTRY_POINT_NAME,
    TOOLING_DIRECTORY,
    Command,
    Repository,
    _configuration_values,
)

PROJECT_ROOT = Path(__file__).parents[3]
"""
The checkout the skill and the tooling it runs are both read from.
"""

MAINTENANCE_SKILL_DOCUMENT = (
    PROJECT_ROOT / ".claude/skills/stacked-pr-maintenance/SKILL.md"
)
"""
The instructions a maintenance pass follows.
"""

WORKING_TREE_INVOCATION = re.compile(
    rf"python {re.escape(str(TOOLING_DIRECTORY.relative_to(PROJECT_ROOT)))}"
    r"/(\S+\.py) ([\w-]+)"
)
"""
Matches a command the skill runs from the working tree, capturing the script and the
subcommand.
"""


def candidate_forks() -> set[Repository]:
    """
    Every repository this checkout could be operating on: the ones its remotes name,
    minus the upstream that is the same for everybody.

    Read from the remotes rather than from the resolved ``fork_repository`` so the check
    still has something to assert on a clone nobody has run setup on - which is every
    fresh CI checkout.

    :return: The candidate forks, empty if the checkout has no repository remote at all.
    """
    upstream = Repository.parse(
        _configuration_values(CONFIGURATION_PATH)["upstream_repository"]
    )
    listed = subprocess.run(
        ["git", "remote"], capture_output=True, text=True, check=True
    ).stdout.split()
    urls = (
        subprocess.run(
            ["git", "remote", "get-url", name],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        for name in listed
    )
    named = {
        Repository.from_remote_url(url)
        for url in urls
        if Repository.names_a_repository(url)
    }
    return named - {upstream}


def test_the_skill_names_no_fork_of_its_own():
    """
    The fork is configuration, so the skill has to read it rather than spell it out.
    """
    skill = MAINTENANCE_SKILL_DOCUMENT.read_text()

    for fork in candidate_forks():
        assert fork.owner not in skill
        assert str(fork) not in skill


def test_the_skill_restores_the_tooling_without_writing_the_index():
    """
    ``git checkout <ref> -- <path>`` writes the index as well as the working tree, so on
    a branch that does not carry the tooling the files end up staged - and the next
    commit the pass makes on that branch is a restack merge, which would carry them into
    somebody's feature branch. Only the working-tree restore may be handed to a pass.
    """
    skill = MAINTENANCE_SKILL_DOCUMENT.read_text()

    assert "git restore --source=<ref> --worktree -- .claude/stack/" in skill
    assert "git checkout <ref> -- .claude/stack/" not in skill


def test_the_skill_reports_the_pending_links_with_the_command_that_renders_them():
    """
    Rendering the table is mechanical, so it belongs to the executor - a document that
    describes the columns instead of naming the command is one asking a session to
    assemble them again, which is what the command replaced.
    """
    skill = MAINTENANCE_SKILL_DOCUMENT.read_text()

    assert PendingPromotionsCommand.invoked_as in skill


def test_the_skill_rests_on_no_notification_to_deliver_its_links():
    """
    The Finish section used to justify itself with "a scheduled run is configured to
    email its summary, so the summary *is* the delivery".

    No notification is sent by either kind of run now, so a document that assumes one is
    telling a reader their links will arrive somewhere they will not.
    """
    skill = MAINTENANCE_SKILL_DOCUMENT.read_text().lower()

    assert "email" not in skill


def test_the_skill_runs_nothing_from_the_working_tree_once_the_tool_is_pinned():
    """
    A pass switches branches in the checkout it runs from, so every command it runs.

    after step 0 must name the pinned copy. Only the two commands that pin - resolving
    which repositories the pass runs on, and the pinning itself - may still come from
    the working tree, because at that point there is nothing else to run.
    """
    skill = MAINTENANCE_SKILL_DOCUMENT.read_text()

    assert set(WORKING_TREE_INVOCATION.findall(skill)) == {
        (ENTRY_POINT_NAME, Command.CONFIGURATION),
        (ENTRY_POINT_NAME, Command.PIN_TOOLING),
    }
