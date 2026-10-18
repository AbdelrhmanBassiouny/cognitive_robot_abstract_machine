"""
Fail when a package with a version of its own changed since a base revision without
raising that version.

Such a package is published only when its version is new on PyPI, so a change that
leaves the version alone would never be released.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path

from packaging.version import Version

# %% package layout


class PackageFile(StrEnum):
    """
    The paths inside a package directory that make up what the package ships.
    """

    METADATA = "pyproject.toml"
    """
    The package's metadata, which holds its version.
    """

    SOURCE = "src"
    """
    The package's source tree.
    """


class MetadataKey(StrEnum):
    """
    The keys of a ``pyproject.toml`` leading to the package's version.
    """

    PROJECT = "project"
    VERSION = "version"


# %% check


class GitRevision(StrEnum):
    """
    The git revisions the check refers to by name.
    """

    HEAD = "HEAD"
    """
    The checked-out commit.
    """


class VersionCheckOutcome(Enum):
    """
    What comparing a package against the base revision found.
    """

    UNCHANGED = "{package} is unchanged."
    NEW_PACKAGE = "{package} is new; its first version is released as it is."
    RAISED = "{package} version raised from {base} to {head}."
    NOT_RAISED = (
        "{package} changed but its version is still {head} (base: {base}); raise "
        "version in {metadata}."
    )

    @property
    def is_failure(self) -> bool:
        """
        Whether this outcome fails the check.
        """
        return self is VersionCheckOutcome.NOT_RAISED


@dataclass
class VersionRaiseCheck:
    """
    Compares a package at ``HEAD`` with the same package at a base revision.
    """

    package_directory: Path
    """
    The package's directory, relative to the repository root.
    """

    base_revision: str
    """
    The revision the package's current state is compared with.
    """

    repository_root: Path
    """
    The root of the git repository holding the package.
    """

    @property
    def metadata_path(self) -> Path:
        """
        The package's ``pyproject.toml``, relative to the repository root.
        """
        return self.package_directory / PackageFile.METADATA

    def evaluate(self) -> VersionCheckOutcome:
        """
        :return: Whether the package is unchanged, new, or changed with or without a
            raised version.
        """
        if not self.package_changed():
            return VersionCheckOutcome.UNCHANGED
        base_version = self.version_at(self.base_revision)
        if base_version is None:
            return VersionCheckOutcome.NEW_PACKAGE
        if self.version_at(GitRevision.HEAD) > base_version:
            return VersionCheckOutcome.RAISED
        return VersionCheckOutcome.NOT_RAISED

    def describe(self, outcome: VersionCheckOutcome) -> str:
        """
        :param outcome: An outcome of :meth:`evaluate`.
        :return: The outcome's message, filled in for this package.
        """
        return outcome.value.format(
            package=self.package_directory.as_posix(),
            base=self.version_at(self.base_revision),
            head=self.version_at(GitRevision.HEAD),
            metadata=self.metadata_path.as_posix(),
        )

    def package_changed(self) -> bool:
        """
        :return: Whether the package's source or metadata differ between the base
            revision and ``HEAD``.
        """
        difference = self.run_git(
            "diff",
            "--quiet",
            self.base_revision,
            GitRevision.HEAD,
            "--",
            (self.package_directory / PackageFile.SOURCE).as_posix(),
            self.metadata_path.as_posix(),
        )
        return difference.returncode != 0

    def version_at(self, revision: str) -> Version | None:
        """
        :param revision: A git revision.
        :return: The package's version at ``revision``, or ``None`` when the package
            does not exist there.
        """
        metadata = self.run_git("show", f"{revision}:{self.metadata_path.as_posix()}")
        if metadata.returncode != 0:
            return None
        project = tomllib.loads(metadata.stdout)[MetadataKey.PROJECT]
        return Version(project[MetadataKey.VERSION])

    def run_git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """
        :param arguments: The git subcommand and its arguments.
        :return: The finished git process, its output captured.
        """
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repository_root,
            capture_output=True,
            text=True,
        )


# %% command line


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_directory", type=Path)
    parser.add_argument("base_revision")
    arguments = parser.parse_args()
    check = VersionRaiseCheck(
        arguments.package_directory, arguments.base_revision, Path.cwd()
    )
    outcome = check.evaluate()
    print(check.describe(outcome))
    sys.exit(1 if outcome.is_failure else 0)


if __name__ == "__main__":
    main()
