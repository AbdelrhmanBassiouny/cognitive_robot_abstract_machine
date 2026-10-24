from __future__ import annotations

import shutil
from pathlib import Path

from krrood.development_tools.agent_instructions import (
    AgentsInstructions,
    RepositoryInstructionsFile,
    RuleSection,
    RuleSet,
)
from krrood.development_tools.command_line import (
    CommandLine,
    ExitStatus,
    Option,
    Subcommand,
)

from .dataset_files import DatasetFile

# %% composition


def test_composes_notice_shared_rules_and_project_rules(
    repository_root: Path,
) -> None:
    shutil.copyfile(
        DatasetFile.PROJECT_RULES,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )
    instructions = AgentsInstructions(repository_root)

    assert instructions.render() == (
        f"{instructions.notice}\n\n"
        f"{instructions.shared_rules.strip()}\n\n"
        f"{DatasetFile.PROJECT_RULES.read_text().strip()}\n"
    )


def test_composes_notice_and_shared_rules_without_project_rules(
    repository_root: Path,
) -> None:
    instructions = AgentsInstructions(repository_root)

    assert instructions.render() == (
        f"{instructions.notice}\n\n{instructions.shared_rules.strip()}\n"
    )


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


def test_a_section_lists_the_rules_of_each_chosen_rule_set_in_order() -> None:
    instructions = AgentsInstructions(Path.cwd(), rules_directory=DatasetFile.RULES)

    assert instructions.rules_of(RuleSection.ERRORS) == (
        f"{(DatasetFile.RULES / RuleSet.PYTHON / RuleSection.ERRORS.file_name).read_text().strip()}\n"
        f"{(DatasetFile.RULES / RuleSet.KRROOD / RuleSection.ERRORS.file_name).read_text().strip()}"
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
    python_rules = AgentsInstructions(Path.cwd(), (RuleSet.PYTHON,)).shared_rules

    assert "krrood" not in python_rules.lower()


def test_shared_rules_name_no_cram_package() -> None:
    shared_rules = AgentsInstructions(Path.cwd()).shared_rules

    assert "cram" not in shared_rules.lower()


# %% command line


def test_agents_md_command_writes_the_composed_file(repository_root: Path) -> None:
    shutil.copyfile(
        DatasetFile.PROJECT_RULES,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )

    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.GENERATED).read_text() == (
        AgentsInstructions(repository_root).render()
    )


def test_agents_md_command_writes_without_project_rules(
    repository_root: Path,
) -> None:
    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.GENERATED).read_text() == (
        AgentsInstructions(repository_root).render()
    )


def test_agents_md_command_writes_only_the_chosen_rule_sets(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.PYTHON])

    assert (repository_root / RepositoryInstructionsFile.GENERATED).read_text() == (
        AgentsInstructions(repository_root, (RuleSet.PYTHON,)).render()
    )


def test_agents_md_command_keeps_rule_set_order_whatever_the_order_given(
    repository_root: Path,
) -> None:
    CommandLine.main(
        [Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.KRROOD, RuleSet.PYTHON]
    )

    assert (repository_root / RepositoryInstructionsFile.GENERATED).read_text() == (
        AgentsInstructions(repository_root, tuple(RuleSet)).render()
    )


def test_agents_md_command_succeeds_when_the_file_is_current(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])

    assert CommandLine.main([Subcommand.AGENTS_MD]) == ExitStatus.SUCCESS


def test_check_passes_on_a_freshly_written_file(repository_root: Path) -> None:
    shutil.copyfile(
        DatasetFile.PROJECT_RULES,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )
    CommandLine.main([Subcommand.AGENTS_MD])

    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.SUCCESS


def test_check_fails_on_a_stale_file_without_rewriting_it(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])
    shutil.copyfile(
        DatasetFile.PROJECT_RULES,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )
    generated_path = repository_root / RepositoryInstructionsFile.GENERATED
    stale_content = generated_path.read_text()

    exit_status = CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK])

    assert exit_status == ExitStatus.FAILURE
    assert generated_path.read_text() == stale_content


def test_check_fails_when_the_file_is_missing(repository_root: Path) -> None:
    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.FAILURE
