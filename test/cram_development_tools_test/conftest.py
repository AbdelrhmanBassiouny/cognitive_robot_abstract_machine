"""
Fixtures shared by the cram-development-tools tests.

This suite runs in the lightweight test_cram_development_tools CI job with --confcutdir
pointed here, so the repository-root test/conftest.py - which imports the robotics stack
that job does not install - is never loaded for it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .dataset_files import DatasetFile


@pytest.fixture
def copy_into_temporary_directory(tmp_path: Path):
    """
    :return: A function copying a dataset file into ``tmp_path`` under a given name.
    """

    def copy(dataset_file: DatasetFile, file_name: str) -> Path:
        destination = tmp_path / file_name
        shutil.copyfile(dataset_file.value, destination)
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
