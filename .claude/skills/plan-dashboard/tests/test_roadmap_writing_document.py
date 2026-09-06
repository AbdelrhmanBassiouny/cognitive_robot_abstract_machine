"""
Tests that the roadmap-writing rule reaches every skill that writes roadmap narrative.

The rule lives in one document, referenced by each skill rather than restated in it,
so what needs guarding is the reference: a skill that appends to a plan's roadmap
without citing the rule is exactly the drift the document exists to end.

Which skills are bound is *derived* from what they do - a skill that both writes plan
data and mentions ``roadmap.md`` is bound by that fact - rather than listed here, so a
skill added later is covered without this file being edited.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from plan_item_bootstrap import HookScript, PlanDocument

SKILLS_DIRECTORY = Path(__file__).resolve().parents[2]
"""
Where every skill's own directory lives.
"""

PLAN_CREATE_SKILL = SKILLS_DIRECTORY / "plan-create" / "SKILL.md"
"""
The skill whose migration guidance is what originally told sessions to preserve
everything a source doc said.
"""

ROADMAP_WRITING_DOCUMENT_CONSTANT = "ROADMAP_WRITING_DOCUMENT"
"""
The constant a bound skill cites the rule through.
"""

PLAN_WRITING_SCRIPTS = (
    "PLAN_ITEM_BOOTSTRAP_SCRIPT",
    "SAVE_PLAN_SCRIPT",
)
"""
The constants naming a script that writes plan data.

A skill mentioning one of these alongside ``roadmap.md`` is writing roadmap narrative,
not just reading it back.
"""


def shell_constant(name: str) -> str:
    """
    Resolve one constant from the shell configuration that defines it.

    Asking the shell rather than restating its value is what keeps this test from
    becoming a second, independently-drifting copy of the path.

    :param name: The constant to resolve.
    :return: Its value.
    """
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HookScript.CONFIGURATION.path}"; printf "%s" "${{{name}}}"',
        ],
        cwd=SKILLS_DIRECTORY.parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def roadmap_writing_document() -> str:
    """
    The rule document itself, found where the shell configuration says it is.

    :return: Its markdown.
    """
    return (
        SKILLS_DIRECTORY.parents[1] / shell_constant(ROADMAP_WRITING_DOCUMENT_CONSTANT)
    ).read_text()


def skills_writing_roadmap_narrative() -> list[Path]:
    """
    Every skill document that writes plan data and mentions the roadmap file.

    :return: Their paths, in a stable order.
    """
    return sorted(
        skill
        for skill in SKILLS_DIRECTORY.glob("*/SKILL.md")
        if PlanDocument.ROADMAP in (text := skill.read_text())
        and any(script in text for script in PLAN_WRITING_SCRIPTS)
    )


def test_the_rule_lives_where_the_shell_configuration_says_it_does():
    document = Path(shell_constant(ROADMAP_WRITING_DOCUMENT_CONSTANT))

    assert document.name == "roadmap-writing.md"
    assert (SKILLS_DIRECTORY.parents[1] / document).is_file()


@pytest.mark.parametrize(
    "skill", skills_writing_roadmap_narrative(), ids=lambda skill: skill.parent.name
)
def test_a_skill_that_writes_roadmap_narrative_cites_the_rule(skill: Path):
    assert ROADMAP_WRITING_DOCUMENT_CONSTANT in skill.read_text()


def test_plan_create_no_longer_instructs_preserving_everything():
    """
    The instruction this item replaces - keep every migrated line rather than
    compressing it - is exactly what re-spends the budget a split just cleared.
    """
    assert (
        "preserve its detail rather than compressing"
        not in PLAN_CREATE_SKILL.read_text()
    )


def test_the_rule_names_what_to_keep_and_what_to_compress():
    document = roadmap_writing_document()

    assert "## Keep" in document
    assert "## Compress" in document


def test_the_rule_does_not_hardcode_the_budget_numbers():
    """
    The budget's own numbers are ``SizeBudget``'s to define; a second, textual copy here
    is exactly the kind of duplicate this codebase's own conventions rule out, and it
    would silently go stale the moment the real constants changed.
    """
    document = roadmap_writing_document()

    assert not re.search(r"\b15\b", document)
    assert not re.search(r"\b2,?000\b", document)
