"""
The one thing about the maintenance skill worth asserting from code.

The skill is instructions, so most of what it says can only be checked by reading it.
The exception is what it must *not* say: it runs on whichever fork invoked it, so a
repository named in it is an instruction to operate on somebody else's. That is an
absence, computed from the resolved configuration rather than from a string written
here, which is what makes it worth a test where a prose assertion would not be.
"""

from __future__ import annotations

from pathlib import Path

from stack import load_configuration

MAINTENANCE_SKILL_DOCUMENT = (
    Path(__file__).parents[3] / ".claude/skills/stacked-pr-maintenance/SKILL.md"
)
"""
The instructions a maintenance pass follows.
"""


def test_the_skill_names_no_fork_of_its_own():
    """
    The fork is configuration, so the skill has to read it rather than spell it out.
    """
    skill = MAINTENANCE_SKILL_DOCUMENT.read_text()

    fork = load_configuration().fork_repository

    assert fork.owner not in skill
    assert str(fork) not in skill
