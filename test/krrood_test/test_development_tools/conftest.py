"""
Fixtures shared by the development tools tests.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typing_extensions import Callable

from krrood.development_tools.agent_instructions import (
    RepositoryInstructionsFile,
    RulesBlockMarker,
)

from .dataset_files import DatasetFile


@pytest.fixture
def copy_into_temporary_directory(
    tmp_path: Path,
) -> Callable[[DatasetFile, str], Path]:
    """
    :return: A function copying a dataset file into ``tmp_path`` under a given name.
    """

    def copy(dataset_file: DatasetFile, file_name: str) -> Path:
        destination = tmp_path / file_name
        shutil.copyfile(dataset_file, destination)
        return destination

    return copy


@pytest.fixture
def repository_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    :return: An empty directory, made the working directory, standing in for a
        repository root.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def instructions_with_empty_rules_block(repository_root: Path) -> Path:
    """
    :return: The ``AGENTS.md`` of :func:`repository_root`, holding hand-written text
        before and after an empty block of shared rules.
    """
    path = repository_root / RepositoryInstructionsFile.AGENTS
    path.write_text(
        f"{DatasetFile.INTRODUCTION.read_text()}\n"
        f"{RulesBlockMarker.BEGIN}\n{RulesBlockMarker.END}\n\n"
        f"{DatasetFile.PROJECT_RULES.read_text()}"
    )
    return path
