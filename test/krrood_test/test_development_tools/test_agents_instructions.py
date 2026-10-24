from __future__ import annotations

from pathlib import Path

import pytest

from krrood.development_tools.agent_instructions import (
    AgentsInstructions,
    RepositoryInstructionsFile,
    RuleSection,
    RuleSet,
    RulesBlockMarker,
)
from krrood.development_tools.command_line import (
    CommandLine,
    ExitStatus,
    Option,
    Subcommand,
)
from krrood.development_tools.exceptions import RulesBlockNotFound

from .dataset_files import DatasetFile

# %% block of shared rules


def test_a_new_file_holds_only_the_rules_block(repository_root: Path) -> None:
    instructions = AgentsInstructions(repository_root)

    assert instructions.render() == f"{instructions.rules_block}\n"


def test_the_rules_block_is_enclosed_by_its_markers() -> None:
    instructions = AgentsInstructions(Path.cwd())

    assert instructions.rules_block == (
        f"{RulesBlockMarker.BEGIN}\n\n{instructions.shared_rules}\n\n"
        f"{RulesBlockMarker.END}"
    )


def test_text_around_the_block_is_kept(
    instructions_with_empty_rules_block: Path,
) -> None:
    instructions = AgentsInstructions(instructions_with_empty_rules_block.parent)

    assert instructions.render() == (
        f"{DatasetFile.INTRODUCTION.read_text()}\n"
        f"{instructions.rules_block}\n\n"
        f"{DatasetFile.PROJECT_RULES.read_text()}"
    )


def test_a_file_without_the_block_is_rejected(repository_root: Path) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        DatasetFile.PROJECT_RULES.read_text()
    )

    with pytest.raises(RulesBlockNotFound):
        AgentsInstructions(repository_root).render()


def test_a_file_with_two_blocks_is_rejected(
    instructions_with_empty_rules_block: Path,
) -> None:
    content = instructions_with_empty_rules_block.read_text()
    instructions_with_empty_rules_block.write_text(content + content)

    with pytest.raises(RulesBlockNotFound):
        AgentsInstructions(instructions_with_empty_rules_block.parent).render()


def test_a_block_closed_before_it_opens_is_rejected(repository_root: Path) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        f"{RulesBlockMarker.END}\n{RulesBlockMarker.BEGIN}\n"
    )

    with pytest.raises(RulesBlockNotFound):
        AgentsInstructions(repository_root).render()


# %% rule sets


def test_every_rule_file_belongs_to_a_section() -> None:
    rules_directory = AgentsInstructions(Path.cwd()).rules_directory
    section_file_names = {section.file_name for section in RuleSection}

    rule_file_names = {
        rule_file.name
        for rule_set in RuleSet
        for rule_file in (rules_directory / rule_set).iterdir()
    }

    assert rule_file_names <= section_file_names


def test_a_section_lists_the_rules_of_each_chosen_rule_set_under_their_source() -> None:
    instructions = AgentsInstructions(Path.cwd(), rules_directory=DatasetFile.RULES)
    file_name = RuleSection.ERRORS.file_name

    assert instructions.rules_of(RuleSection.ERRORS) == (
        f"<!-- from {instructions.rules_directory_name / RuleSet.PYTHON / file_name} -->\n"
        f"{(DatasetFile.RULES / RuleSet.PYTHON / file_name).read_text().strip()}\n"
        f"<!-- from {instructions.rules_directory_name / RuleSet.KRROOD / file_name} -->\n"
        f"{(DatasetFile.RULES / RuleSet.KRROOD / file_name).read_text().strip()}"
    )


def test_a_rule_set_left_out_contributes_no_rules() -> None:
    instructions = AgentsInstructions(
        Path.cwd(), (RuleSet.PYTHON,), rules_directory=DatasetFile.RULES
    )

    assert instructions.rules_of(RuleSection.STRUCTURED_DATA) == ""


def test_headings_of_sections_without_rules_are_left_out() -> None:
    instructions = AgentsInstructions(
        Path.cwd(), (RuleSet.KRROOD,), rules_directory=DatasetFile.RULES
    )

    assert instructions.shared_rules == "\n\n".join(
        [
            RuleSection.CODE_QUALITY_RULES.value.markdown,
            RuleSection.DESIGN_PRINCIPLES.value.markdown,
            f"{RuleSection.ERRORS.value.markdown}\n"
            + instructions.rules_of(RuleSection.ERRORS),
            f"{RuleSection.STRUCTURED_DATA.value.markdown}\n"
            + instructions.rules_of(RuleSection.STRUCTURED_DATA),
        ]
    )


def test_python_rules_name_no_krrood_api() -> None:
    instructions = AgentsInstructions(Path.cwd(), (RuleSet.PYTHON,))
    python_rules = "\n".join(
        (instructions.rules_directory / RuleSet.PYTHON / section.file_name).read_text()
        for section in RuleSection
        if (instructions.rules_directory / RuleSet.PYTHON / section.file_name).is_file()
    )

    assert "krrood" not in python_rules.lower()


def test_shared_rules_name_no_cram_package() -> None:
    shared_rules = AgentsInstructions(Path.cwd()).shared_rules

    assert "cram" not in shared_rules.lower()


# %% command line


def test_agents_md_command_writes_a_new_file(repository_root: Path) -> None:
    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        f"{AgentsInstructions(repository_root).rules_block}\n"
    )


def test_agents_md_command_fills_the_block_and_keeps_the_text_around_it(
    instructions_with_empty_rules_block: Path,
) -> None:
    expected_content = AgentsInstructions(
        instructions_with_empty_rules_block.parent
    ).render()

    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert instructions_with_empty_rules_block.read_text() == expected_content


def test_agents_md_command_writes_only_the_chosen_rule_sets(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.PYTHON])

    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions(repository_root, (RuleSet.PYTHON,)).render()
    )


def test_agents_md_command_keeps_rule_set_order_whatever_the_order_given(
    repository_root: Path,
) -> None:
    CommandLine.main(
        [Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.KRROOD, RuleSet.PYTHON]
    )

    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions(repository_root, tuple(RuleSet)).render()
    )


def test_agents_md_command_succeeds_when_the_block_is_current(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])

    assert CommandLine.main([Subcommand.AGENTS_MD]) == ExitStatus.SUCCESS


def test_check_passes_after_text_outside_the_block_changes(
    instructions_with_empty_rules_block: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])
    with instructions_with_empty_rules_block.open("a") as instructions_file:
        instructions_file.write(DatasetFile.PROJECT_RULES.read_text())

    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.SUCCESS


def test_check_fails_on_an_edited_block_without_rewriting_it(
    instructions_with_empty_rules_block: Path,
) -> None:
    edited_content = instructions_with_empty_rules_block.read_text()

    exit_status = CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK])

    assert exit_status == ExitStatus.FAILURE
    assert instructions_with_empty_rules_block.read_text() == edited_content


def test_check_fails_when_the_file_is_missing(repository_root: Path) -> None:
    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.FAILURE
