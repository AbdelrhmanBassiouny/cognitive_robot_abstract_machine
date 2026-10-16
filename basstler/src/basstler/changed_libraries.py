"""
Which libraries of a CI library matrix a change needs tested.

A library is one value of a matrix axis whose job tests ``test/<library>_test``. A
change to a library's package or test directory tests it and every library depending on
it, as each package's ``[project] dependencies`` declares. A change to the tooling tests
the tooling alone, a change to documentation tests nothing, and a change anywhere else
tests everything.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import NormalizedName, canonicalize_name

from basstler.exceptions import MissingMatrixAxis
from basstler.locations import PackageLocation, ProjectLocation
from basstler.standard_streams import StandardStreamHandler
from basstler.workflows import Workflow

logger = StandardStreamHandler.logger_for(__name__)
"""
This module's logger, which is also what its command prints through.
"""

# %% vocabulary


class ChangedPathKind(StrEnum):
    """
    What a changed path belongs to, which decides what it needs tested.
    """

    LIBRARY = "library"
    """
    A library's package or test directory.
    """

    TOOLING = "tooling"
    """
    The tooling this package is, its tests, or the Claude Code configuration it runs.
    """

    DOCUMENTATION = "documentation"
    """
    Documentation, which no test reads.
    """

    WORKSPACE = "workspace"
    """
    Anything else, such as the workspace's declaration or the workflows, which any test
    may depend on.
    """


class DocumentationLocation(StrEnum):
    """
    The names that mark a path as documentation.
    """

    DIRECTORY = "doc"
    """
    A documentation directory, at the root or in a library.
    """

    SUFFIX = ".md"
    """
    A Markdown file.
    """


class WorkspaceFile(StrEnum):
    """
    The files a workspace declares its packages in.
    """

    DECLARATION = "pyproject.toml"
    """
    A package's declaration.
    """


class DeclarationKey(StrEnum):
    """
    The keys of a package declaration this module reads.
    """

    PROJECT = "project"
    """
    The table holding the package's metadata.
    """

    NAME = "name"
    """
    The distribution name.
    """

    DEPENDENCIES = "dependencies"
    """
    The requirements the package is installed with.
    """


class LibraryTestDirectory(StrEnum):
    """
    Where the tests of a library live.
    """

    PARENT = "test"
    """
    The directory holding every library's tests.
    """

    SUFFIX = "_test"
    """
    What a library's test directory appends to its name.
    """


class SelectionOutput(StrEnum):
    """
    The step outputs a selection is written as, for the jobs after it to read.
    """

    EXCLUDED = "excluded"
    """
    The matrix combinations to leave out, as the JSON list a matrix ``exclude`` takes.
    """

    TESTS_LIBRARIES = "tests-libraries"
    """
    Whether any library is left to test.
    """

    TESTS_TOOLING = "tests-tooling"
    """
    Whether the tooling is to be tested.
    """


# %% a library of the matrix


@dataclass(frozen=True)
class MatrixLibrary:
    """
    One library of the matrix: where its code and tests are, and what it depends on.
    """

    name: str
    """
    The library's value on the matrix axis.
    """

    package_directory: Path | None
    """
    The package's directory, relative to the repository root, or none when the library
    is only tests.
    """

    distribution: NormalizedName | None
    """
    The normalized distribution name its declaration gives, or none when it has none.
    """

    requirements: frozenset[NormalizedName]
    """
    The normalized names of the distributions its declaration depends on.
    """

    @property
    def test_directory(self) -> Path:
        """
        :return: The library's test directory, relative to the repository root.
        """
        return (
            Path(LibraryTestDirectory.PARENT)
            / f"{self.name}{LibraryTestDirectory.SUFFIX}"
        )

    def holds(self, path: Path) -> bool:
        """
        :param path: A path relative to the repository root.
        :return: Whether the path is in the library's package or test directory.
        """
        directories = (self.test_directory, self.package_directory)
        return any(
            directory is not None and path.is_relative_to(directory)
            for directory in directories
        )

    def depends_on(self, other: MatrixLibrary) -> bool:
        """
        :param other: Another library of the matrix.
        :return: Whether this library's tests depend on the other's code. A library
            with no declaration of its own depends on every other.
        """
        if self.distribution is None:
            return other is not self
        return other.distribution in self.requirements

    @classmethod
    def in_repository(cls, name: str, repository_root: Path) -> MatrixLibrary:
        """
        :param name: The library's value on the matrix axis.
        :param repository_root: The repository's root.
        :return: The library, declared by its directory's ``pyproject.toml``, or by the
            root's when its directory is the root package's. A library with no directory,
            or with one no declaration names, is only tests.
        """
        tests_only = cls(
            name=name,
            package_directory=None,
            distribution=None,
            requirements=frozenset(),
        )
        directory = repository_root / name
        if not directory.is_dir():
            return tests_only
        declaration = directory / WorkspaceFile.DECLARATION
        if not declaration.exists():
            declaration = repository_root / WorkspaceFile.DECLARATION
        project = tomllib.loads(declaration.read_text())[DeclarationKey.PROJECT]
        if canonicalize_name(project[DeclarationKey.NAME]) != canonicalize_name(name):
            return tests_only
        return cls(
            name=name,
            package_directory=Path(name),
            distribution=canonicalize_name(name),
            requirements=frozenset(
                canonicalize_name(Requirement(requirement).name)
                for requirement in project.get(DeclarationKey.DEPENDENCIES, ())
            ),
        )


# %% what a change needs tested


@dataclass(frozen=True)
class SelectedTests:
    """
    What a change needs tested.
    """

    libraries: frozenset[str]
    """
    The libraries to test, by their value on the matrix axis.
    """

    tests_tooling: bool
    """
    Whether the tooling is to be tested.
    """


@dataclass(frozen=True)
class LibraryMatrix:
    """
    The libraries one CI job is run over, one per value of a matrix axis.
    """

    axis: str
    """
    The matrix axis whose values are the libraries.
    """

    libraries: tuple[MatrixLibrary, ...]
    """
    The libraries, in the order the axis lists them.
    """

    @classmethod
    def read(
        cls, repository_root: Path, workflow: Path, job: str, axis: str
    ) -> LibraryMatrix:
        """
        :param repository_root: The repository's root.
        :param workflow: The workflow file holding the job.
        :param job: The key of the job running the matrix.
        :param axis: The matrix axis listing the libraries.
        :return: The matrix.
        """
        axes = {
            declared.identifier: declared.matrix_axes
            for declared in Workflow.at(workflow).jobs
        }.get(job, {})
        if axis not in axes:
            raise MissingMatrixAxis(workflow=workflow, job=job, axis=axis)
        return cls(
            axis=axis,
            libraries=tuple(
                MatrixLibrary.in_repository(str(name), repository_root)
                for name in axes[axis]
            ),
        )

    @property
    def everything(self) -> SelectedTests:
        """
        :return: Every library and the tooling.
        """
        return SelectedTests(
            libraries=frozenset(library.name for library in self.libraries),
            tests_tooling=True,
        )

    def kind_of(self, path: Path) -> ChangedPathKind:
        """
        :param path: A changed path, relative to the repository root.
        :return: What it belongs to.
        """
        if path.suffix == DocumentationLocation.SUFFIX or (
            DocumentationLocation.DIRECTORY in path.parts
        ):
            return ChangedPathKind.DOCUMENTATION
        tooling = (
            ProjectLocation.CLAUDE_CODE_DIRECTORY,
            ProjectLocation.PACKAGE_SOURCE_TREE,
            ProjectLocation.PACKAGE_TESTS,
        )
        if any(path.is_relative_to(directory) for directory in tooling):
            return ChangedPathKind.TOOLING
        if any(library.holds(path) for library in self.libraries):
            return ChangedPathKind.LIBRARY
        return ChangedPathKind.WORKSPACE

    def selection_for(self, changed: Iterable[Path]) -> SelectedTests:
        """
        :param changed: The changed paths, relative to the repository root.
        :return: What the change needs tested.
        """
        kinds = {path: self.kind_of(path) for path in changed}
        if ChangedPathKind.WORKSPACE in kinds.values():
            return self.everything
        library_paths = [
            path for path, kind in kinds.items() if kind is ChangedPathKind.LIBRARY
        ]
        touched = {
            library
            for library in self.libraries
            if any(library.holds(path) for path in library_paths)
        }
        return SelectedTests(
            libraries=frozenset(
                library.name for library in self.with_dependents(touched)
            ),
            tests_tooling=ChangedPathKind.TOOLING in kinds.values(),
        )

    def with_dependents(self, libraries: set[MatrixLibrary]) -> set[MatrixLibrary]:
        """
        :param libraries: Libraries of this matrix.
        :return: Them and every library depending on them, directly or through others.
        """
        selected = set(libraries)
        added = selected
        while added:
            added = {
                library
                for library in self.libraries
                if library not in selected
                and any(library.depends_on(dependency) for dependency in added)
            }
            selected |= added
        return selected

    def exclusions_for(self, selection: SelectedTests) -> list[dict[str, str]]:
        """
        :param selection: What a change needs tested.
        :return: The combinations leaving out every library it does not select, in the
            order the axis lists them.
        """
        return [
            {self.axis: library.name}
            for library in self.libraries
            if library.name not in selection.libraries
        ]

    def step_outputs_for(self, selection: SelectedTests) -> dict[SelectionOutput, str]:
        """
        :param selection: What a change needs tested.
        :return: The step outputs that hand it to the jobs after the step.
        """
        return {
            SelectionOutput.EXCLUDED: json.dumps(self.exclusions_for(selection)),
            SelectionOutput.TESTS_LIBRARIES: json.dumps(bool(selection.libraries)),
            SelectionOutput.TESTS_TOOLING: json.dumps(selection.tests_tooling),
        }


# %% command line


class CommandLineFlag(StrEnum):
    """
    The flags this module's command line takes.
    """

    WORKFLOW = "--workflow"
    """
    The file name of the workflow running the matrix.
    """

    JOB = "--job"
    """
    The key of the job running the matrix.
    """

    AXIS = "--axis"
    """
    The matrix axis listing the libraries.
    """

    EVERYTHING = "--everything"
    """
    Test everything, without reading a change.
    """


def main(arguments: list[str] | None = None) -> None:
    """
    Print the step outputs of what a change needs tested, as ``name=value`` lines for
    ``$GITHUB_OUTPUT``, reading the changed paths one per line from standard input.

    :param arguments: The command line, or none to read the process's own.
    """
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument(CommandLineFlag.WORKFLOW, required=True)
    parser.add_argument(CommandLineFlag.JOB, required=True)
    parser.add_argument(CommandLineFlag.AXIS, required=True)
    parser.add_argument(CommandLineFlag.EVERYTHING, action="store_true")
    parsed = parser.parse_args(arguments)
    repository_root = PackageLocation.REPOSITORY_ROOT.value
    matrix = LibraryMatrix.read(
        repository_root=repository_root,
        workflow=repository_root / ProjectLocation.WORKFLOWS / parsed.workflow,
        job=parsed.job,
        axis=parsed.axis,
    )
    selection = (
        matrix.everything
        if parsed.everything
        else matrix.selection_for(
            Path(line) for line in sys.stdin.read().splitlines() if line
        )
    )
    for output, value in matrix.step_outputs_for(selection).items():
        logger.info(f"{output}={value}")


if __name__ == "__main__":
    main()
