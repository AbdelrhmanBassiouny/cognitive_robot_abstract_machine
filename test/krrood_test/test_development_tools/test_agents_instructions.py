from __future__ import annotations

from pathlib import Path

import pytest
from typing_extensions import Callable

from krrood.development_tools.agent_instructions import AgentsInstructions
from krrood.development_tools.agent_rule import CodeReference, Section
from krrood.development_tools.command_line import (
    CommandLine,
    ExitStatus,
    Option,
    Subcommand,
)
from krrood.development_tools import shipped_rules
from krrood.development_tools.repository_files import RepositoryInstructionsFile
from krrood.exceptions import DataclassException
from krrood.patterns import path_enumeration

from .dataset.rule_sections import (
    DesignPrinciplesRules,
    ErrorsRules,
    ReleasesThroughCIRules,
    VerificationRules,
)
from .dataset_files import DatasetFile

# %% sections


@pytest.fixture
def shipped_sections() -> list[type[Section]]:
    """
    :return: The top-level sections krrood ships.
    """
    return [
        section
        for section in Section.top_level
        if section.__module__ == shipped_rules.__name__
    ]


def test_the_file_lists_the_rules_of_its_sections_under_their_headings(
    repository_root: Path,
) -> None:
    instructions = AgentsInstructions(
        repository_root, [DesignPrinciplesRules, VerificationRules]
    )

    assert instructions.text == DatasetFile.RULE_SECTIONS_TEXT.read_text().format(
        source_path=DesignPrinciplesRules.source_path
    )


def test_a_section_is_nested_in_the_section_its_parent_returns() -> None:
    assert ErrorsRules.parent is DesignPrinciplesRules


def test_the_subsections_of_a_section_are_the_sections_nested_in_it() -> None:
    assert DesignPrinciplesRules.subsections == [ErrorsRules]


def test_a_title_names_the_topic_keeping_acronyms_in_capitals() -> None:
    assert ReleasesThroughCIRules.title == "Releases through CI"


def test_no_two_shipped_sibling_sections_share_a_title(
    shipped_sections: list[type[Section]],
) -> None:
    sibling_titles = [[section.title for section in shipped_sections]]
    unvisited = list(shipped_sections)
    while unvisited:
        section = unvisited.pop()
        sibling_titles.append([subsection.title for subsection in section.subsections])
        unvisited.extend(section.subsections)

    assert all(len(titles) == len(set(titles)) for titles in sibling_titles)


def test_shipped_rules_name_no_cram_package(
    repository_root: Path, shipped_sections: list[type[Section]]
) -> None:
    text = AgentsInstructions(repository_root, shipped_sections).text

    assert "cram" not in text.lower()


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
def project_rules_repository(
    repository_root: Path,
    copy_into_temporary_directory: Callable[[DatasetFile, str], Path],
) -> Path:
    """
    :return: :func:`repository_root`, holding the repository's own rules module.
    """
    copy_into_temporary_directory(
        DatasetFile.PROJECT_RULES_MODULE, RepositoryInstructionsFile.PROJECT_RULES
    )
    return repository_root


def test_the_file_of_a_repository_lists_its_project_sections(
    project_rules_repository: Path,
) -> None:
    instructions = AgentsInstructions.from_repository(project_rules_repository)

    assert (
        AgentsInstructions.import_project_rules(
            project_rules_repository
        ).DeploymentRules
        in instructions.sections
    )


def test_the_project_rules_module_is_imported_once(
    project_rules_repository: Path,
) -> None:
    assert AgentsInstructions.import_project_rules(
        project_rules_repository
    ) is AgentsInstructions.import_project_rules(project_rules_repository)


def test_a_repository_without_a_project_rules_module_has_none(
    repository_root: Path,
) -> None:
    assert AgentsInstructions.import_project_rules(repository_root) is None


# %% command line


def test_agents_md_command_writes_a_new_file(repository_root: Path) -> None:
    exit_status = CommandLine.main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.AGENTS).read_text() == (
        AgentsInstructions.from_repository(repository_root).text
    )


def test_agents_md_command_replaces_a_hand_written_file(
    repository_root: Path,
) -> None:
    path = repository_root / RepositoryInstructionsFile.AGENTS
    path.write_text(DatasetFile.HAND_WRITTEN_RULES.read_text())

    CommandLine.main([Subcommand.AGENTS_MD])

    assert path.read_text() == (
        AgentsInstructions.from_repository(repository_root).text
    )


def test_agents_md_command_succeeds_when_the_file_is_current(
    repository_root: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])

    assert CommandLine.main([Subcommand.AGENTS_MD]) == ExitStatus.SUCCESS


def test_check_fails_on_an_edited_file_without_rewriting_it(
    repository_root: Path,
) -> None:
    path = repository_root / RepositoryInstructionsFile.AGENTS
    path.write_text(DatasetFile.HAND_WRITTEN_RULES.read_text())

    exit_status = CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK])

    assert exit_status == ExitStatus.FAILURE
    assert path.read_text() == DatasetFile.HAND_WRITTEN_RULES.read_text()


def test_agents_md_command_adds_the_project_rules(
    project_rules_repository: Path,
) -> None:
    CommandLine.main([Subcommand.AGENTS_MD])

    text = (project_rules_repository / RepositoryInstructionsFile.AGENTS).read_text()
    assert AgentsInstructions.import_project_rules(
        project_rules_repository
    ).DeploymentRules.heading in (text.splitlines())


def test_check_fails_when_the_file_is_missing(repository_root: Path) -> None:
    assert CommandLine.main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.FAILURE
