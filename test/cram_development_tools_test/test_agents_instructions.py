from __future__ import annotations

import shutil
from pathlib import Path

from cram_development_tools.agents_instructions import (
    AgentsInstructions,
    RepositoryInstructionsFile,
)
from cram_development_tools.command_line import (
    ExitStatus,
    Option,
    Subcommand,
    main,
)

from .dataset_files import DatasetFile

# %% composition


def test_composes_notice_generic_rules_and_project_rules(
    repository_root: Path,
) -> None:
    shutil.copyfile(
        DatasetFile.PROJECT_RULES.value,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )
    instructions = AgentsInstructions(repository_root)

    assert instructions.render() == (
        f"{instructions.notice}\n\n"
        f"{instructions.generic_rules.strip()}\n\n"
        f"{DatasetFile.PROJECT_RULES.value.read_text().strip()}\n"
    )


def test_composes_notice_and_generic_rules_without_project_rules(
    repository_root: Path,
) -> None:
    instructions = AgentsInstructions(repository_root)

    assert instructions.render() == (
        f"{instructions.notice}\n\n{instructions.generic_rules.strip()}\n"
    )


def test_generic_rules_name_no_cram_package() -> None:
    generic_rules = AgentsInstructions(Path.cwd()).generic_rules

    assert "cram" not in generic_rules.lower()


# %% command line


def test_agents_md_command_writes_the_composed_file(repository_root: Path) -> None:
    shutil.copyfile(
        DatasetFile.PROJECT_RULES.value,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )

    exit_status = main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.GENERATED).read_text() == (
        AgentsInstructions(repository_root).render()
    )


def test_agents_md_command_writes_without_project_rules(
    repository_root: Path,
) -> None:
    exit_status = main([Subcommand.AGENTS_MD])

    assert exit_status == ExitStatus.FAILURE
    assert (repository_root / RepositoryInstructionsFile.GENERATED).read_text() == (
        AgentsInstructions(repository_root).render()
    )


def test_agents_md_command_succeeds_when_the_file_is_current(
    repository_root: Path,
) -> None:
    main([Subcommand.AGENTS_MD])

    assert main([Subcommand.AGENTS_MD]) == ExitStatus.SUCCESS


def test_check_passes_on_a_freshly_written_file(repository_root: Path) -> None:
    shutil.copyfile(
        DatasetFile.PROJECT_RULES.value,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )
    main([Subcommand.AGENTS_MD])

    assert main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.SUCCESS


def test_check_fails_on_a_stale_file_without_rewriting_it(
    repository_root: Path,
) -> None:
    main([Subcommand.AGENTS_MD])
    shutil.copyfile(
        DatasetFile.PROJECT_RULES.value,
        repository_root / RepositoryInstructionsFile.PROJECT,
    )
    generated_path = repository_root / RepositoryInstructionsFile.GENERATED
    stale_content = generated_path.read_text()

    exit_status = main([Subcommand.AGENTS_MD, Option.CHECK])

    assert exit_status == ExitStatus.FAILURE
    assert generated_path.read_text() == stale_content


def test_check_fails_when_the_file_is_missing(repository_root: Path) -> None:
    assert main([Subcommand.AGENTS_MD, Option.CHECK]) == ExitStatus.FAILURE
