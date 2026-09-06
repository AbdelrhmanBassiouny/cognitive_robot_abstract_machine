"""
Tests for reading a pull request's tooling label off the files it changes.

The classification is pure and is tested as such, against paths this suite names rather
than against the ones this repository happens to use - what it has to get right is the
rule, not the layout. One test does read the committed configuration, so a layout that
stopped naming the tooling is caught too.

The labelling is tested against a stand-in fork, because what it has to get right is
which writes it makes and which it declines to make, and the returned report alone
cannot show a write that never happened.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from dataclasses import field as dataclasses_field
from pathlib import Path
from typing import Any

import pytest

from changed_paths import ChangedPaths, PathSubject
from maintenance_github import (
    ChangedFileField,
    ChangedFileRecord,
    GitHubRepository,
    PullRequestFiles,
)
from maintenance_tooling_label import label_tooling_changes
from stack import Configuration, LabelWrite, Repository, load_configuration

from test_maintenance import (
    A_LABEL_THIS_TOOL_NEVER_WRITES,
    RecordingPullRequests,
    make_configuration,
)

A_TOOLING_DIRECTORY = "tools/"
"""
Stands for wherever a fork keeps the tooling this label is about.
"""

A_SOFTWARE_PATH = "a_package/a_module.py"
"""
Stands for the software a repository exists to build, which is the rest of it.
"""

A_SHARED_PATH = "a-shared-configuration.toml"
"""
Stands for the repository-wide configuration both sides change.
"""

REPOSITORY_ROOT = Path(__file__).parents[3]
"""
This checkout's root, which the committed configuration names paths from.
"""


@pytest.fixture
def configuration() -> Configuration:
    """:return: A configuration whose tooling lives at paths this suite names."""
    return replace(
        make_configuration(),
        tooling_paths=(A_TOOLING_DIRECTORY,),
        shared_paths=(A_SHARED_PATH,),
    )


# %% the fork, asked what each pull request changes


@dataclass(frozen=True)
class PullRequestsWithChangedFiles(RecordingPullRequests, PullRequestFiles):
    """
    Stands in for the fork on both halves of the labelling: the pull requests it reads
    and writes, and the files each one changes.
    """

    files: dict[int, list[str]] = dataclasses_field(default_factory=dict)
    """What paths to report each pull request number as changing."""

    def changed_paths(self, number: int) -> list[str]:
        """:param number: The pull request to read.
        :return: The paths it was given as changing."""
        return list(self.files.get(number, []))


@dataclass(frozen=True)
class RepositoryAnsweringInPages(GitHubRepository):
    """
    Stands in for the API, answering a fixed set of changed files a page at a time.

    The client pages until a short page arrives, which only a stand-in answering more
    than one page can exercise at all.
    """

    answers: tuple[ChangedFileRecord, ...] = ()
    """Every changed file the API would answer with, across all its pages."""

    paths_asked_for: list[str] = dataclasses_field(default_factory=list)
    """Every path the client called, in order."""

    def _call(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Any:
        """:param method: The HTTP method, unused - only reads are answered here.
        :param path: The path called, recorded so the paging can be asserted on.
        :param payload: The body, which a read never carries.
        :return: The page of changed files the call asked for."""
        self.paths_asked_for.append(path)
        page = len(self.paths_asked_for) - 1
        return list(self.answers[page * self.page_size : (page + 1) * self.page_size])


# %% what one path is part of


def test_a_path_under_a_tooling_directory_is_the_tooling(
    configuration: Configuration,
) -> None:
    changed = ChangedPaths.of([], configuration)
    assert changed.subject_of(f"{A_TOOLING_DIRECTORY}a_tool.py") is PathSubject.TOOLING


def test_a_path_under_no_named_directory_is_the_software(
    configuration: Configuration,
) -> None:
    changed = ChangedPaths.of([], configuration)
    assert changed.subject_of(A_SOFTWARE_PATH) is PathSubject.SOFTWARE


def test_a_shared_path_settles_neither_way(configuration: Configuration) -> None:
    changed = ChangedPaths.of([], configuration)
    assert changed.subject_of(A_SHARED_PATH) is PathSubject.SHARED


def test_a_directory_prefix_claims_no_file_merely_starting_with_its_name(
    configuration: Configuration,
) -> None:
    """The trailing separator is what keeps ``tools/`` from claiming ``toolset.py``."""
    changed = ChangedPaths.of([], configuration)
    outside = f"{A_TOOLING_DIRECTORY.rstrip('/')}set.py"
    assert changed.subject_of(outside) is PathSubject.SOFTWARE


# %% what a whole change is


def test_changing_only_the_tooling_is_a_tooling_change(
    configuration: Configuration,
) -> None:
    changed = ChangedPaths.of([f"{A_TOOLING_DIRECTORY}a_tool.py"], configuration)
    assert changed.is_a_tooling_change


def test_changing_the_software_as_well_is_not_a_tooling_change(
    configuration: Configuration,
) -> None:
    changed = ChangedPaths.of(
        [f"{A_TOOLING_DIRECTORY}a_tool.py", A_SOFTWARE_PATH], configuration
    )
    assert not changed.is_a_tooling_change


def test_a_shared_path_alongside_the_tooling_leaves_it_a_tooling_change(
    configuration: Configuration,
) -> None:
    changed = ChangedPaths.of(
        [f"{A_TOOLING_DIRECTORY}a_tool.py", A_SHARED_PATH], configuration
    )
    assert changed.is_a_tooling_change


def test_changing_shared_configuration_alone_is_not_a_tooling_change(
    configuration: Configuration,
) -> None:
    assert not ChangedPaths.of([A_SHARED_PATH], configuration).is_a_tooling_change


def test_a_pull_request_changing_nothing_is_not_a_tooling_change(
    configuration: Configuration,
) -> None:
    assert not ChangedPaths.of([], configuration).is_a_tooling_change


def test_the_committed_configuration_reads_this_suite_as_the_tooling() -> None:
    """This module is part of the tooling, so the committed paths have to claim it."""
    changed = ChangedPaths.of(
        [str(Path(__file__).relative_to(REPOSITORY_ROOT))], load_configuration()
    )
    assert changed.is_a_tooling_change


# %% what the labelling writes


def test_the_label_is_added_to_a_pull_request_that_changes_only_the_tooling(
    configuration: Configuration,
) -> None:
    fork = PullRequestsWithChangedFiles(
        labels={7: [A_LABEL_THIS_TOOL_NEVER_WRITES]},
        files={7: [f"{A_TOOLING_DIRECTORY}a_tool.py"]},
    )

    labelled = label_tooling_changes(fork, fork, configuration)

    assert [write.labels for write in fork.label_writes] == [
        (A_LABEL_THIS_TOOL_NEVER_WRITES, configuration.tooling_label)
    ]
    assert [entry.is_a_tooling_change for entry in labelled] == [True]


def test_the_label_is_removed_once_a_pull_request_changes_the_software_too(
    configuration: Configuration,
) -> None:
    fork = PullRequestsWithChangedFiles(
        labels={7: [configuration.tooling_label, A_LABEL_THIS_TOOL_NEVER_WRITES]},
        files={7: [f"{A_TOOLING_DIRECTORY}a_tool.py", A_SOFTWARE_PATH]},
    )

    labelled = label_tooling_changes(fork, fork, configuration)

    assert [write.labels for write in fork.label_writes] == [
        (A_LABEL_THIS_TOOL_NEVER_WRITES,)
    ]
    assert [entry.is_a_tooling_change for entry in labelled] == [False]


def test_a_pull_request_already_labelled_correctly_is_not_written(
    configuration: Configuration,
) -> None:
    fork = PullRequestsWithChangedFiles(
        labels={7: [configuration.tooling_label]},
        files={7: [f"{A_TOOLING_DIRECTORY}a_tool.py"]},
    )

    labelled = label_tooling_changes(fork, fork, configuration)

    assert fork.label_writes == []
    assert [entry.label_was_written for entry in labelled] == [False]


def test_naming_a_pull_request_leaves_every_other_one_alone(
    configuration: Configuration,
) -> None:
    fork = PullRequestsWithChangedFiles(
        labels={7: [], 8: []},
        files={
            7: [f"{A_TOOLING_DIRECTORY}a_tool.py"],
            8: [f"{A_TOOLING_DIRECTORY}another_tool.py"],
        },
    )

    labelled = label_tooling_changes(fork, fork, configuration, [8])

    assert [entry.pull_request_number for entry in labelled] == [8]
    assert [write.pull_request_number for write in fork.label_writes] == [8]


def test_the_write_keeps_every_label_the_tool_knows_nothing_about(
    configuration: Configuration,
) -> None:
    """The whole set is replaced by the API, so the rest has to be sent back with it."""
    carried = [A_LABEL_THIS_TOOL_NEVER_WRITES, configuration.bug_label]
    fork = PullRequestsWithChangedFiles(
        labels={7: list(carried)}, files={7: [f"{A_TOOLING_DIRECTORY}a_tool.py"]}
    )

    label_tooling_changes(fork, fork, configuration)

    assert (
        fork.label_writes[0].labels
        == LabelWrite.replacing(carried, added=[configuration.tooling_label]).labels
    )


# %% how the fork's own answer is read


def _answered_files(paths: Sequence[str]) -> tuple[ChangedFileRecord, ...]:
    """:param paths: The paths the API would report as changed.
    :return: Those paths, shaped the way the API answers them."""
    return tuple({ChangedFileField.PATH: path} for path in paths)


def test_every_page_of_changed_files_is_read() -> None:
    """A pull request over one page long is the case a single call silently truncates."""
    paths = [f"{A_TOOLING_DIRECTORY}tool_{index}.py" for index in range(5)]
    fork = RepositoryAnsweringInPages(
        repository=Repository("an-owner", "a-repository"),
        token="a-token",
        page_size=2,
        answers=_answered_files(paths),
    )

    assert fork.changed_paths(7) == paths
    assert len(fork.paths_asked_for) == 3
