from __future__ import annotations

from pathlib import Path

import pytest

from krrood.development_tools.agent_instructions import (
    AgentsInstructions,
    RepositoryInstructionsFile,
    RuleSet,
    RulesBlockMarker,
)
from krrood.development_tools.agent_rule import (
    KrroodRule,
    PythonRule,
    RuleSection,
)
from krrood.development_tools.command_line import (
    CommandLine,
    ExitStatus,
    Option,
    Subcommand,
)
from krrood.development_tools.exceptions import MalformedRulesBlock
from krrood.development_tools.rules.krrood_rules import KrroodRules
from krrood.development_tools.rules.python_rules import PythonRules

from .dataset.rule_catalogues import ErrorAndStructuredDataRules, ErrorRules
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


def test_a_file_without_the_block_gets_it_above_its_text(
    repository_root: Path,
) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        DatasetFile.PROJECT_RULES.read_text()
    )
    instructions = AgentsInstructions(repository_root)

    assert instructions.render() == (
        f"{instructions.rules_block}\n\n{DatasetFile.PROJECT_RULES.read_text()}"
    )


def test_a_file_with_only_one_marker_is_rejected(repository_root: Path) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        f"{RulesBlockMarker.BEGIN}\n{DatasetFile.PROJECT_RULES.read_text()}"
    )

    with pytest.raises(MalformedRulesBlock):
        AgentsInstructions(repository_root).render()


def test_a_file_with_two_blocks_is_rejected(
    instructions_with_empty_rules_block: Path,
) -> None:
    content = instructions_with_empty_rules_block.read_text()
    instructions_with_empty_rules_block.write_text(content + content)

    with pytest.raises(MalformedRulesBlock):
        AgentsInstructions(instructions_with_empty_rules_block.parent).render()


def test_a_block_closed_before_it_opens_is_rejected(repository_root: Path) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        f"{RulesBlockMarker.END}\n{RulesBlockMarker.BEGIN}\n"
    )

    with pytest.raises(MalformedRulesBlock):
        AgentsInstructions(repository_root).render()


# %% rules and catalogues


def test_a_rule_lists_its_details_below_it() -> None:
    rule = ErrorRules.RAISE_ERRORS.value

    assert rule.markdown == "\n".join(
        [f"- {rule.statement}", *(f"  - {detail}" for detail in rule.details)]
    )


def test_a_catalogue_lists_its_rules_of_a_section_in_declaration_order() -> None:
    assert ErrorAndStructuredDataRules.rules_in(RuleSection.ERRORS) == [
        ErrorAndStructuredDataRules.NAME_ERRORS.value,
        ErrorAndStructuredDataRules.DOCUMENT_ERRORS.value,
    ]


@pytest.mark.parametrize(
    "catalogue, rule_class",
    [(PythonRules, PythonRule), (KrroodRules, KrroodRule)],
)
def test_a_shipped_catalogue_holds_only_rules_of_its_rule_set(
    catalogue: type, rule_class: type
) -> None:
    assert {type(member.value) for member in catalogue} == {rule_class}


def test_every_rule_set_names_a_catalogue() -> None:
    assert [rule_set.catalogue for rule_set in RuleSet] == [PythonRules, KrroodRules]


def test_python_rules_name_no_krrood_api() -> None:
    python_rules = "\n".join(rule.value.markdown for rule in PythonRules)

    assert "krrood" not in python_rules.lower()


def test_shared_rules_name_no_cram_package() -> None:
    shared_rules = AgentsInstructions(Path.cwd()).shared_rules

    assert "cram" not in shared_rules.lower()


# %% sections of the block


def test_a_section_lists_the_rules_of_each_chosen_catalogue_under_their_source() -> (
    None
):
    instructions = AgentsInstructions(
        Path.cwd(), (ErrorRules, ErrorAndStructuredDataRules)
    )
    catalogue_module = Path(*ErrorRules.__module__.split(".")).with_suffix(".py")

    assert instructions.rules_of(RuleSection.ERRORS) == "\n".join(
        [
            f"<!-- from {ErrorRules.__qualname__} in {catalogue_module} -->",
            ErrorRules.RAISE_ERRORS.value.markdown,
            f"<!-- from {ErrorAndStructuredDataRules.__qualname__} in "
            f"{catalogue_module} -->",
            ErrorAndStructuredDataRules.NAME_ERRORS.value.markdown,
            ErrorAndStructuredDataRules.DOCUMENT_ERRORS.value.markdown,
        ]
    )


def test_a_catalogue_left_out_contributes_no_rules() -> None:
    instructions = AgentsInstructions(Path.cwd(), (ErrorRules,))

    assert instructions.rules_of(RuleSection.STRUCTURED_DATA) == ""


def test_headings_of_sections_without_rules_are_left_out() -> None:
    instructions = AgentsInstructions(Path.cwd(), (ErrorAndStructuredDataRules,))

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


def test_agents_md_command_adds_the_block_to_a_file_without_one(
    repository_root: Path,
) -> None:
    path = repository_root / RepositoryInstructionsFile.AGENTS
    path.write_text(DatasetFile.PROJECT_RULES.read_text())
    expected_content = AgentsInstructions(repository_root).render()

    CommandLine.main([Subcommand.AGENTS_MD])

    assert path.read_text() == expected_content


def test_agents_md_command_writes_only_the_chosen_rule_sets(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.PYTHON])

    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions(repository_root, (RuleSet.PYTHON.catalogue,)).render()
    )


def test_agents_md_command_keeps_rule_set_order_whatever_the_order_given(
    repository_root: Path,
) -> None:
    CommandLine.main(
        [Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.KRROOD, RuleSet.PYTHON]
    )

    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions(repository_root).render()
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
