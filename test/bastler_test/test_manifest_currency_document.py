"""
Tests that the manifest-currency rule reaches every skill it binds.

The rule lives in one document, referenced by each skill rather than restated in it,
so what needs guarding is the reference: a skill that writes plan data without citing
the rule is exactly the drift the document exists to end.

Which skills are bound is *derived* from what they do - a skill that runs a
plan-writing script is bound by that fact - rather than listed here, so a skill added
later is covered without this file being edited.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from bastler.package_layout import REPOSITORY_ROOT

SKILLS_DIRECTORY = REPOSITORY_ROOT / ".claude" / "skills"
"""
Where every skill's own directory lives.
"""

MAINTENANCE_SKILL = SKILLS_DIRECTORY / "stacked-pr-maintenance" / "SKILL.md"
"""
The pass that changes a tracked item's real state while writing no manifest.
"""

PLAN_WRITING_SCRIPTS = (
    "PLAN_ITEM_BOOTSTRAP_MODULE",
    "SAVE_PLAN_SCRIPT",
    "WRITE_PERSONAL_NOTES_FILE_SCRIPT",
)
"""
The constants naming a script that writes plan data, so a skill invoking one is writing
plan state and is bound by the rule.

The third is how the dashboard refresh pushes its own manifest corrections, which is
a plan-data write like any other - so the publisher is bound by what it does rather
than by being named here.
"""

CURRENCY_DOCUMENT_CONSTANT = "MANIFEST_CURRENCY_DOCUMENT"
"""
The constant a bound skill cites the rule through.
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
            f'source .claude/hooks/resolve-personal-notes-config.sh; printf "%s" "${{{name}}}"',
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def skills_writing_plan_data() -> list[Path]:
    """
    Every skill document that runs a script which writes plan data.

    :return: Their paths, in a stable order.
    """
    return sorted(
        skill
        for skill in SKILLS_DIRECTORY.glob("*/SKILL.md")
        if any(script in skill.read_text() for script in PLAN_WRITING_SCRIPTS)
    )


def test_the_rule_lives_where_the_shell_configuration_says_it_does():
    document = Path(shell_constant(CURRENCY_DOCUMENT_CONSTANT))

    assert document.name == "manifest-currency.md"
    assert (REPOSITORY_ROOT / document).is_file()


@pytest.mark.parametrize(
    "skill", skills_writing_plan_data(), ids=lambda skill: skill.parent.name
)
def test_a_skill_that_writes_plan_data_cites_the_currency_rule(skill: Path):
    assert CURRENCY_DOCUMENT_CONSTANT in skill.read_text()


def test_the_maintenance_pass_cites_the_rule_without_writing_the_manifest():
    maintenance = MAINTENANCE_SKILL.read_text()

    assert CURRENCY_DOCUMENT_CONSTANT in maintenance
    assert not any(script in maintenance for script in PLAN_WRITING_SCRIPTS)


def test_the_rule_names_no_plan_of_its_own():
    document = (
        REPOSITORY_ROOT / shell_constant(CURRENCY_DOCUMENT_CONSTANT)
    ).read_text()
    placeholders = set(re.findall(r"<([a-z-]+)>", document))

    assert "plan-id" in placeholders
    assert not re.search(r"plans/(?!<)[a-z][a-z0-9-]*/", document)
