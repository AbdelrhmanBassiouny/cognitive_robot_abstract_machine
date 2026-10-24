from __future__ import annotations

from pathlib import Path

import pytest
from typing_extensions import Callable

from krrood.development_tools.agent_instructions import (
    AgentsInstructions,
    ProjectRulesModule,
    RuleSet,
    RulesBlockMarker,
    SectionContent,
)
from krrood.development_tools.agent_rule import CodeReference, Section
from krrood.development_tools.command_line import (
    CommandLine,
    ExitStatus,
    Option,
    Subcommand,
)
from krrood.development_tools.exceptions import (
    CatalogueWithoutSection,
    MalformedRulesBlock,
    SectionWithoutTitle,
)
from krrood.development_tools.repository_files import RepositoryInstructionsFile
from krrood.development_tools.rules.sections import (
    CodeQualityRules,
    DesignPrinciples,
    Errors,
    RunningTests,
    StructuredData,
)
from krrood.exceptions import DataclassException
from krrood.patterns import path_enumeration

from .dataset.rule_catalogues import (
    DatasetErrors,
    DatasetStructuredData,
    OtherDatasetErrors,
    SectionlessRules,
    UntitledSection,
)
from .dataset_files import DatasetFile

# %% block of shared rules


def test_a_new_file_holds_only_the_rules_block(repository_root: Path) -> None:
    instructions = AgentsInstructions.of_repository(repository_root)

    assert instructions.render() == f"{instructions.rules_block}\n"


def test_the_rules_block_is_enclosed_by_its_markers() -> None:
    instructions = AgentsInstructions.of_repository(Path.cwd())

    assert instructions.rules_block == (
        f"{RulesBlockMarker.BEGIN}\n\n{instructions.rules_text}{RulesBlockMarker.END}"
    )


def test_text_around_the_block_is_kept(
    instructions_with_empty_rules_block: Path,
) -> None:
    instructions = AgentsInstructions.of_repository(
        instructions_with_empty_rules_block.parent
    )

    assert instructions.render() == (
        f"{DatasetFile.INTRODUCTION.read_text()}\n"
        f"{instructions.rules_block}\n\n"
        f"{DatasetFile.HAND_WRITTEN_RULES.read_text()}"
    )


def test_a_file_without_the_block_gets_it_above_its_text(
    repository_root: Path,
) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        DatasetFile.HAND_WRITTEN_RULES.read_text()
    )
    instructions = AgentsInstructions.of_repository(repository_root)

    assert instructions.render() == (
        f"{instructions.rules_block}\n\n{DatasetFile.HAND_WRITTEN_RULES.read_text()}"
    )


def test_a_file_with_only_one_marker_is_rejected(repository_root: Path) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        f"{RulesBlockMarker.BEGIN}\n{DatasetFile.HAND_WRITTEN_RULES.read_text()}"
    )

    with pytest.raises(MalformedRulesBlock):
        AgentsInstructions.of_repository(repository_root).render()


def test_a_file_with_two_blocks_is_rejected(
    instructions_with_empty_rules_block: Path,
) -> None:
    content = instructions_with_empty_rules_block.read_text()
    instructions_with_empty_rules_block.write_text(content + content)

    with pytest.raises(MalformedRulesBlock):
        AgentsInstructions.of_repository(
            instructions_with_empty_rules_block.parent
        ).render()


def test_a_block_closed_before_it_opens_is_rejected(repository_root: Path) -> None:
    (repository_root / RepositoryInstructionsFile.AGENTS).write_text(
        f"{RulesBlockMarker.END}\n{RulesBlockMarker.BEGIN}\n"
    )

    with pytest.raises(MalformedRulesBlock):
        AgentsInstructions.of_repository(repository_root).render()


# %% sections and catalogues


def test_a_catalogue_belongs_to_the_section_it_subclasses() -> None:
    assert DatasetErrors.section is Errors


def test_a_catalogue_without_a_section_is_rejected() -> None:
    with pytest.raises(CatalogueWithoutSection):
        SectionlessRules.section


def test_a_section_without_a_title_is_rejected() -> None:
    with pytest.raises(SectionWithoutTitle):
        UntitledSection.heading


def test_a_section_lists_its_catalogues_in_the_chosen_order() -> None:
    instructions = AgentsInstructions(
        Path.cwd(), [OtherDatasetErrors, DatasetStructuredData, DatasetErrors]
    )

    assert instructions.contents_of([Errors]) == [
        SectionContent(Errors, [OtherDatasetErrors, DatasetErrors], [])
    ]


def test_sections_without_rules_are_left_out() -> None:
    instructions = AgentsInstructions(Path.cwd(), [DatasetStructuredData])

    assert instructions.contents_of(Section.subsections) == [
        SectionContent(
            CodeQualityRules,
            [],
            [
                SectionContent(
                    DesignPrinciples,
                    [],
                    [SectionContent(StructuredData, [DatasetStructuredData], [])],
                )
            ],
        )
    ]


def test_every_shipped_catalogue_has_a_titled_section() -> None:
    sections = [
        catalogue.section for rule_set in RuleSet for catalogue in rule_set.catalogues
    ]

    assert all(section.heading for section in sections)


def test_python_rules_name_no_krrood_api(repository_root: Path) -> None:
    rules_text = AgentsInstructions.of_repository(
        repository_root, (RuleSet.PYTHON,)
    ).rules_text
    rules = "\n".join(
        line for line in rules_text.splitlines() if not line.startswith("<!--")
    )

    assert "krrood" not in rules.lower()


def test_shipped_rules_name_no_cram_package(repository_root: Path) -> None:
    rules_text = AgentsInstructions.of_repository(repository_root).rules_text

    assert "cram" not in rules_text.lower()


# %% code named by rules


def test_a_class_is_named_by_its_import_path() -> None:
    assert CodeReference(DataclassException).path == (
        f"`{DataclassException.__module__}.{DataclassException.__qualname__}`"
    )


def test_a_module_is_named_by_its_import_path() -> None:
    assert CodeReference(path_enumeration).path == f"`{path_enumeration.__name__}`"


def test_an_object_is_named_by_the_module_it_is_imported_from() -> None:
    assert CodeReference(pytest.raises, pytest).path == (
        f"`{pytest.__name__}.{pytest.raises.__qualname__}`"
    )


def test_a_method_is_named_by_its_own_name() -> None:
    assert CodeReference(DataclassException.error_message).name == (
        f"`{DataclassException.error_message.__name__}`"
    )


# %% project rules


@pytest.fixture
def project_rules_module(
    repository_root: Path,
    copy_into_temporary_directory: Callable[[DatasetFile, str], Path],
) -> ProjectRulesModule:
    """
    :return: The repository's own rules module.
    """
    copy_into_temporary_directory(
        DatasetFile.PROJECT_RULES_MODULE, RepositoryInstructionsFile.PROJECT_RULES
    )
    return ProjectRulesModule(repository_root)


def test_the_project_rules_module_declares_its_catalogues(
    project_rules_module: ProjectRulesModule,
) -> None:
    module = project_rules_module.module

    assert project_rules_module.catalogues == [
        module.OwnRunningTests,
        module.DeploymentRules,
    ]


def test_the_project_rules_module_is_loaded_once(
    project_rules_module: ProjectRulesModule,
) -> None:
    assert (
        ProjectRulesModule(project_rules_module.repository_root).catalogues
        == project_rules_module.catalogues
    )


def test_a_repository_without_a_project_rules_module_has_no_own_rules(
    repository_root: Path,
) -> None:
    assert ProjectRulesModule(repository_root).catalogues == []


def test_project_rules_are_listed_under_their_sections(
    project_rules_module: ProjectRulesModule,
) -> None:
    instructions = AgentsInstructions(
        project_rules_module.repository_root, project_rules_module.catalogues
    )

    assert instructions.rules_text == DatasetFile.PROJECT_RULES_TEXT.read_text()


def test_own_sections_follow_the_shared_sections(
    project_rules_module: ProjectRulesModule,
) -> None:
    instructions = AgentsInstructions.of_repository(
        project_rules_module.repository_root
    )

    assert [
        content.section for content in instructions.contents_of(Section.subsections)
    ] == [CodeQualityRules, project_rules_module.module.OwnRules]


def test_a_project_rule_in_a_shared_section_follows_the_shared_rules(
    project_rules_module: ProjectRulesModule,
) -> None:
    instructions = AgentsInstructions.of_repository(
        project_rules_module.repository_root
    )

    assert instructions.contents_of([RunningTests])[0].catalogues == [
        *(
            catalogue
            for rule_set in RuleSet
            for catalogue in rule_set.catalogues
            if catalogue.section is RunningTests
        ),
        project_rules_module.module.OwnRunningTests,
    ]


# %% command line


def test_agents_md_command_writes_a_new_file(repository_root: Path) -> None:
    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        f"{AgentsInstructions.of_repository(repository_root).rules_block}\n"
    )


def test_agents_md_command_fills_the_block_and_keeps_the_text_around_it(
    instructions_with_empty_rules_block: Path,
) -> None:
    expected_content = AgentsInstructions.of_repository(
        instructions_with_empty_rules_block.parent
    ).render()

    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert instructions_with_empty_rules_block.read_text() == expected_content


def test_agents_md_command_adds_the_block_to_a_file_without_one(
    repository_root: Path,
) -> None:
    path = repository_root / RepositoryInstructionsFile.AGENTS
    path.write_text(DatasetFile.HAND_WRITTEN_RULES.read_text())
    expected_content = AgentsInstructions.of_repository(repository_root).render()

    CommandLine.main([Subcommand.AGENTS_MD])

    assert path.read_text() == expected_content


def test_agents_md_command_writes_only_the_chosen_rule_sets(
    repository_root: Path,
) -> None:
    CommandLine.main(
        [Subcommand.AGENTS_MD, Option.RULE_SETS, RuleSet.PYTHON.command_line_name]
    )

    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions.of_repository(repository_root, (RuleSet.PYTHON,)).render()
    )


def test_agents_md_command_keeps_rule_set_order_whatever_the_order_given(
    repository_root: Path,
) -> None:
    CommandLine.main(
        [
            Subcommand.AGENTS_MD,
            Option.RULE_SETS,
            RuleSet.KRROOD.command_line_name,
            RuleSet.PYTHON.command_line_name,
        ]
    )

    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions.of_repository(repository_root).render()
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
        instructions_file.write(DatasetFile.HAND_WRITTEN_RULES.read_text())

    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.SUCCESS


def test_check_fails_on_an_edited_block_without_rewriting_it(
    instructions_with_empty_rules_block: Path,
) -> None:
    edited_content = instructions_with_empty_rules_block.read_text()

    exit_status = CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK])

    assert exit_status == ExitStatus.FAILURE
    assert instructions_with_empty_rules_block.read_text() == edited_content


def test_agents_md_command_adds_the_project_rules(
    project_rules_module: ProjectRulesModule,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])

    assert (
        project_rules_module.repository_root / RepositoryInstructionsFile.AGENTS
    ).read_text() == (
        AgentsInstructions.of_repository(project_rules_module.repository_root).render()
    )


def test_check_fails_when_the_file_is_missing(repository_root: Path) -> None:
    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.FAILURE
