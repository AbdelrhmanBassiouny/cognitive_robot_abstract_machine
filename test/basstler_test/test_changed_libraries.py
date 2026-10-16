"""
Which libraries of CI's matrix a change needs tested: the libraries whose package or
test directory it touches, and every library depending on them.

The rule tests read a small workspace in the dataset; the repository tests read this
repository's own CI workflow and packages.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from basstler.changed_libraries import (
    CommandLineFlag,
    LibraryMatrix,
    SelectedTests,
    SelectionOutput,
    ChangedPathKind,
    main,
)
from basstler.exceptions import MissingMatrixAxis
from basstler.locations import PackageLocation, ProjectLocation

from .constants import DatasetLocation, RepositoryLibraryMatrix

# %% the dataset's workspace


@pytest.fixture
def matrix() -> LibraryMatrix:
    """
    :return: The library matrix of the dataset's CI workflow.
    """
    return LibraryMatrix.read(
        repository_root=DatasetLocation.CHANGED_LIBRARIES,
        workflow=DatasetLocation.CHANGED_LIBRARIES_WORKFLOW,
        job="test_each_lib",
        axis="lib",
    )


def test_the_libraries_are_read_off_the_matrix_axis_in_order(matrix: LibraryMatrix):
    assert [library.name for library in matrix.libraries] == [
        "core",
        "middle_library",
        "leaf",
        "lonely",
        "cycle_first",
        "cycle_second",
        "meta_package",
        "checks",
    ]


def test_a_job_without_the_axis_is_reported():
    with pytest.raises(MissingMatrixAxis):
        LibraryMatrix.read(
            repository_root=DatasetLocation.CHANGED_LIBRARIES,
            workflow=DatasetLocation.CHANGED_LIBRARIES_WORKFLOW,
            job="test_each_lib",
            axis="python",
        )


def test_a_job_the_workflow_does_not_have_is_reported():
    with pytest.raises(MissingMatrixAxis):
        LibraryMatrix.read(
            repository_root=DatasetLocation.CHANGED_LIBRARIES,
            workflow=DatasetLocation.CHANGED_LIBRARIES_WORKFLOW,
            job="test_everything",
            axis="lib",
        )


# %% selecting from a change


def test_a_changed_library_is_tested_with_every_library_depending_on_it(
    matrix: LibraryMatrix,
):
    """
    ``middle_library`` and ``leaf`` depend on ``core`` directly and through each other;
    the meta-package's declaration names every library, and ``checks`` has no package,
    so it depends on all of them.
    """
    selection = matrix.selection_for([Path("core/src/core/geometry.py")])

    assert selection.libraries == frozenset(
        {"core", "middle_library", "leaf", "meta_package", "checks"}
    )


def test_a_changed_test_directory_selects_its_library(matrix: LibraryMatrix):
    assert matrix.selection_for(
        [Path("test/leaf_test/test_leaf.py")]
    ) == matrix.selection_for([Path("leaf/src/leaf/leaf.py")])


def test_dependency_names_match_whatever_separators_case_and_extras_they_use(
    matrix: LibraryMatrix,
):
    """
    ``middle_library`` declares ``Core>=1.0`` and ``leaf`` declares
    ``middle_library[plotting]`` against the distribution ``middle-library``.
    """
    selection = matrix.selection_for([Path("core/pyproject.toml")])

    assert {"middle_library", "leaf"} <= selection.libraries


def test_libraries_depending_on_each_other_are_both_selected(matrix: LibraryMatrix):
    selection = matrix.selection_for([Path("cycle_first/cycle_first.py")])

    assert selection.libraries == frozenset(
        {"cycle_first", "cycle_second", "meta_package", "checks"}
    )


def test_a_library_change_does_not_test_the_tooling(matrix: LibraryMatrix):
    assert matrix.selection_for([Path("lonely/lonely.py")]).tests_tooling is False


def test_a_change_only_to_the_tooling_tests_the_tooling_alone(matrix: LibraryMatrix):
    selection = matrix.selection_for(
        [
            ProjectLocation.HOOKS / "session-start.sh",
            ProjectLocation.PACKAGE / "stack.py",
            ProjectLocation.PACKAGE_TESTS / "test_stack.py",
        ]
    )

    assert selection == SelectedTests(libraries=frozenset(), tests_tooling=True)


def test_a_change_only_to_documentation_tests_nothing(matrix: LibraryMatrix):
    selection = matrix.selection_for(
        [Path("README.md"), Path("core/doc/index.rst"), Path("doc/conf.py")]
    )

    assert selection == SelectedTests(libraries=frozenset(), tests_tooling=False)


def test_a_change_outside_every_library_and_the_tooling_tests_everything(
    matrix: LibraryMatrix,
):
    """
    A path no library or the tooling owns - here the workspace declaration - could
    affect any of them.
    """
    selection = matrix.selection_for([Path("lonely/lonely.py"), Path("pyproject.toml")])

    assert selection == matrix.everything


def test_everything_tests_every_library_and_the_tooling(matrix: LibraryMatrix):
    assert matrix.everything == SelectedTests(
        libraries=frozenset(library.name for library in matrix.libraries),
        tests_tooling=True,
    )


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        (Path("core/core.py"), ChangedPathKind.LIBRARY),
        (Path("test/core_test/test_core.py"), ChangedPathKind.LIBRARY),
        (
            ProjectLocation.CLAUDE_CODE_DIRECTORY / "settings.json",
            ChangedPathKind.TOOLING,
        ),
        (Path("core/doc/index.md"), ChangedPathKind.DOCUMENTATION),
        (Path("uv.lock"), ChangedPathKind.WORKSPACE),
    ],
)
def test_each_path_is_attributed_to_what_it_belongs_to(
    matrix: LibraryMatrix, path: Path, kind: ChangedPathKind
):
    assert matrix.kind_of(path) is kind


# %% what the workflow reads back


def test_the_unselected_libraries_are_excluded_from_the_matrix(matrix: LibraryMatrix):
    selection = matrix.selection_for([Path("lonely/lonely.py")])

    assert matrix.exclusions_for(selection) == [
        {"lib": name}
        for name in ("core", "middle_library", "leaf", "cycle_first", "cycle_second")
    ]


def test_the_step_outputs_name_the_exclusions_and_what_runs(matrix: LibraryMatrix):
    selection = matrix.selection_for([ProjectLocation.PACKAGE / "stack.py"])

    assert matrix.step_outputs_for(selection) == {
        SelectionOutput.EXCLUDED: json.dumps(matrix.exclusions_for(selection)),
        SelectionOutput.TESTS_LIBRARIES: "false",
        SelectionOutput.TESTS_TOOLING: "true",
    }


# %% this repository


@pytest.fixture
def repository_matrix() -> LibraryMatrix:
    """
    :return: The library matrix of this repository's CI workflow.
    """
    return LibraryMatrix.read(
        repository_root=PackageLocation.REPOSITORY_ROOT,
        workflow=PackageLocation.REPOSITORY_ROOT
        / ProjectLocation.WORKFLOWS
        / RepositoryLibraryMatrix.WORKFLOW,
        job=RepositoryLibraryMatrix.JOB,
        axis=RepositoryLibraryMatrix.AXIS,
    )


def test_every_repository_library_has_a_test_directory(
    repository_matrix: LibraryMatrix,
):
    missing = [
        library.name
        for library in repository_matrix.libraries
        if not (PackageLocation.REPOSITORY_ROOT / library.test_directory).is_dir()
    ]

    assert missing == []


def test_every_repository_library_has_a_package_or_tests_everything(
    repository_matrix: LibraryMatrix,
):
    """
    A library the matrix names with no declaration of its own is tested on every library
    change; only one that is genuinely not a package may be.
    """
    without_declaration = [
        library.name
        for library in repository_matrix.libraries
        if library.distribution is None
    ]

    assert without_declaration == ["version"]


def test_a_repository_library_change_selects_its_declared_dependents(
    repository_matrix: LibraryMatrix,
):
    """
    ``cramera`` is the one package declaring ``segmind``, besides the meta-package
    declaring every library; ``version`` has no package, so it depends on all of them.
    """
    selection = repository_matrix.selection_for([Path("segmind/src/segmind/x.py")])

    assert selection.libraries == frozenset(
        {"segmind", "cramera", "cognitive_robot_abstract_machine", "version"}
    )


def test_the_command_prints_the_step_outputs_of_the_changed_paths_it_reads(
    repository_matrix: LibraryMatrix,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    changed = [ProjectLocation.PACKAGE / "stack.py"]
    monkeypatch.setattr(
        "sys.stdin", io.StringIO("".join(f"{path}\n" for path in changed))
    )

    main(
        [
            CommandLineFlag.WORKFLOW,
            RepositoryLibraryMatrix.WORKFLOW,
            CommandLineFlag.JOB,
            RepositoryLibraryMatrix.JOB,
            CommandLineFlag.AXIS,
            RepositoryLibraryMatrix.AXIS,
        ]
    )

    outputs = repository_matrix.step_outputs_for(
        repository_matrix.selection_for(changed)
    )
    assert capsys.readouterr().out.splitlines() == [
        f"{output}={value}" for output, value in outputs.items()
    ]
