"""
Tests that the manifest-staleness rule reaches every skill it binds.

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
The pass that changes a tracked item's real state without owning the item.
"""

PLAN_CREATE_SKILL = SKILLS_DIRECTORY / "plan-create" / "SKILL.md"
"""
The skill whose own act of creating a plan is what makes the master index stale.
"""

MASTER_INDEX_KEY = "_index"
"""
How the dashboard URL cache names the master index's own page.
"""

BLOCKER_OWNER_CONSTANT = "MAINTENANCE_BLOCKER_OWNER"
"""
The constant naming who the maintenance pass writes its blockers under, which the writer
and the clearer of one have to agree on exactly.
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

STALENESS_DOCUMENT_CONSTANT = "MANIFEST_STALENESS_DOCUMENT"
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


def currency_document() -> str:
    """
    The rule document itself, found where the shell configuration says it is.

    :return: Its markdown.
    """
    return (REPOSITORY_ROOT / shell_constant(STALENESS_DOCUMENT_CONSTANT)).read_text()


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
    document = Path(shell_constant(STALENESS_DOCUMENT_CONSTANT))

    assert document.name == "manifest-staleness.md"
    assert (REPOSITORY_ROOT / document).is_file()


@pytest.mark.parametrize(
    "skill", skills_writing_plan_data(), ids=lambda skill: skill.parent.name
)
def test_a_skill_that_writes_plan_data_cites_the_currency_rule(skill: Path):
    assert STALENESS_DOCUMENT_CONSTANT in skill.read_text()


def test_the_maintenance_pass_writes_the_manifest_its_own_moves_make_stale():
    """
    The pass concluding a branch is blocked is what makes the item blocked, so it is the
    one that records it - reporting instead leaves the manifest wrong for as long as
    nobody reads the summary.
    """
    maintenance = MAINTENANCE_SKILL.read_text()

    assert any(script in maintenance for script in PLAN_WRITING_SCRIPTS)


def test_the_maintenance_pass_can_reach_the_skill_that_publishes():
    """
    Republishing means invoking ``plan-dashboard``, which needs the ``Skill`` tool - a
    grant no amount of prose in the document can substitute for.
    """
    frontmatter = MAINTENANCE_SKILL.read_text().split("---")[1]
    granted = frontmatter.partition("allowed-tools:")[2].partition("\n")[0]

    assert "Skill" in {tool.strip() for tool in granted.split(",")}


def test_the_writer_and_the_clearer_of_a_blocker_name_the_same_owner():
    """
    A blocker written under one name and cleared under another would accumulate forever,
    so both sides cite the constant rather than spelling the name out.
    """
    assert shell_constant(BLOCKER_OWNER_CONSTANT)
    assert BLOCKER_OWNER_CONSTANT in currency_document()
    assert BLOCKER_OWNER_CONSTANT in MAINTENANCE_SKILL.read_text()


def test_creating_a_plan_republishes_the_index_the_new_plan_belongs_in():
    """
    The index lists every plan, so adding one is the single change that makes the index
    itself wrong - the one case where publishing only the plan's own page is not enough.
    """
    assert MASTER_INDEX_KEY in PLAN_CREATE_SKILL.read_text()


def test_the_rule_names_no_plan_of_its_own():
    document = currency_document()
    placeholders = set(re.findall(r"<([a-z-]+)>", document))

    assert "plan-id" in placeholders
    assert not re.search(r"plans/(?!<)[a-z][a-z0-9-]*/", document)
