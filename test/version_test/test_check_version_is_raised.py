"""
When ``scripts/check_version_is_raised.py`` passes and fails a package that carries a
version of its own.

The script is a standalone file rather than part of an importable package, so it is
loaded from its path.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

CHECK_SCRIPT = Path(__file__).parents[2] / "scripts" / "check_version_is_raised.py"
"""
The script under test.
"""

METADATA_TEMPLATE = Path(__file__).parent / "dataset" / "package_metadata_template.toml"
"""
A package's ``pyproject.toml``, with its version left to fill in.
"""


def load_check_script() -> ModuleType:
    """
    Registered under its name before it runs, as an import would be, since a dataclass
    looks its own module up while it is defined.

    :return: The script, imported from its file.
    """
    specification = importlib.util.spec_from_file_location(
        CHECK_SCRIPT.stem, CHECK_SCRIPT
    )
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


check_script = load_check_script()


# %% repository under test


@dataclass
class PackageRepository:
    """
    A git repository holding one package with a version of its own.
    """

    root: Path
    """
    The repository's root directory.
    """

    package_directory: Path = Path("example_package")
    """
    The package's directory, relative to :attr:`root`.
    """

    def git(self, *arguments: str) -> str:
        """
        :param arguments: The git subcommand and its arguments.
        :return: What git printed.
        """
        return subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com"]
            + list(arguments),
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit_package(self, version: str, source: str) -> str:
        """
        :param version: The version the package's metadata declares.
        :param source: The content of the package's one source file.
        :return: The new commit.
        """
        source_directory = self.root / self.package_directory / "src"
        source_directory.mkdir(parents=True, exist_ok=True)
        (source_directory / "module.py").write_text(source)
        (self.root / self.package_directory / "pyproject.toml").write_text(
            METADATA_TEMPLATE.read_text().format(version=version)
        )
        return self.commit()

    def commit(self) -> str:
        """
        :return: The new commit, holding everything in the working tree.
        """
        self.git("add", "--all")
        self.git("commit", "--allow-empty", "--message", "change")
        return self.git("rev-parse", "HEAD")

    def outcome_since(self, base_revision: str) -> check_script.VersionCheckOutcome:
        """
        :param base_revision: The revision ``HEAD`` is compared with.
        :return: The check's outcome.
        """
        return check_script.VersionRaiseCheck(
            self.package_directory, base_revision, self.root
        ).evaluate()


@pytest.fixture
def repository(tmp_path: Path) -> PackageRepository:
    """
    :return: An empty git repository.
    """
    package_repository = PackageRepository(tmp_path)
    package_repository.git("init", "--quiet")
    return package_repository


# %% outcomes


def test_passes_an_unchanged_package(repository: PackageRepository) -> None:
    base = repository.commit_package("0.1.0", "first = 1\n")
    (repository.root / "unrelated.txt").write_text("unrelated change\n")
    repository.commit()

    assert repository.outcome_since(base) is check_script.VersionCheckOutcome.UNCHANGED


def test_passes_a_package_the_base_does_not_have(
    repository: PackageRepository,
) -> None:
    base = repository.commit()
    repository.commit_package("0.1.0", "first = 1\n")

    assert (
        repository.outcome_since(base) is check_script.VersionCheckOutcome.NEW_PACKAGE
    )


def test_passes_a_change_that_raises_the_version(
    repository: PackageRepository,
) -> None:
    base = repository.commit_package("0.1.0", "first = 1\n")
    repository.commit_package("0.2.0", "second = 2\n")

    assert repository.outcome_since(base) is check_script.VersionCheckOutcome.RAISED


def test_fails_a_change_that_keeps_the_version(repository: PackageRepository) -> None:
    base = repository.commit_package("0.1.0", "first = 1\n")
    repository.commit_package("0.1.0", "second = 2\n")

    outcome = repository.outcome_since(base)

    assert outcome is check_script.VersionCheckOutcome.NOT_RAISED
    assert outcome.is_failure


def test_fails_a_change_that_lowers_the_version(repository: PackageRepository) -> None:
    base = repository.commit_package("0.2.0", "first = 1\n")
    repository.commit_package("0.1.0", "second = 2\n")

    assert repository.outcome_since(base) is check_script.VersionCheckOutcome.NOT_RAISED
