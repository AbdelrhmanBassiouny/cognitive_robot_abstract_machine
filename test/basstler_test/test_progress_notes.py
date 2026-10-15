"""
Tests for progress_notes.py: deleting the progress notes of finished pull requests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from basstler.maintenance_constants import CREDENTIAL_VARIABLES
from basstler.maintenance_git_commands import GitCommandRunner
from basstler.maintenance_github import GitHubRepository
from basstler.progress_notes import (
    BranchPullRequests,
    EmptyRemoteBranchListError,
    ProgressNotesDirectory,
    ProgressNotesFile,
    ProgressNotesPruning,
    PruningSkipped,
)
from basstler.repository import Repository

from .constants import DatasetLocation, ProgressBranch
from .scratch_repository import ScratchRepository, initialize_bare_repository

PULL_REQUESTS = json.loads(DatasetLocation.PULL_REQUESTS_BY_BRANCH.read_text())
"""
Pull requests of ``owner/repo``: one branch open, one merged, one reopened after a
closed attempt, and two from elsewhere.
"""

REPOSITORY = Repository.parse("owner/repo")
"""
The repository the recorded pull requests belong to.
"""


def branch_pull_requests() -> BranchPullRequests:
    """
    :return: The recorded pull requests, grouped by branch.
    """
    return BranchPullRequests.from_pull_requests(PULL_REQUESTS, REPOSITORY)


def progress_directory(tmp_path: Path, *branches: str) -> ProgressNotesDirectory:
    """
    :return: A directory holding one progress-notes file per branch.
    """
    for branch in branches:
        file = tmp_path / f"{branch}{ProgressNotesFile.SUFFIX}"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("- Next: a step.\n")
    return ProgressNotesDirectory(tmp_path)


# %% grouping pull requests by branch


def test_a_branch_with_any_open_pull_request_is_open():
    assert branch_pull_requests().open_branches == {
        ProgressBranch.OPEN,
        ProgressBranch.REOPENED,
    }


def test_a_branch_whose_pull_requests_all_closed_is_finished():
    assert branch_pull_requests().finished_branches == {ProgressBranch.MERGED}


# %% pruning


def test_the_notes_of_a_finished_branch_are_removed(tmp_path):
    directory = progress_directory(tmp_path, ProgressBranch.MERGED, ProgressBranch.OPEN)
    removed = directory.remove_finished(
        branch_pull_requests(),
        frozenset({ProgressBranch.MERGED, ProgressBranch.OPEN}),
        "other",
    )
    assert removed == [ProgressBranch.MERGED]
    assert directory.branches() == [ProgressBranch.OPEN]


def test_the_notes_of_a_branch_gone_from_the_remote_are_removed(tmp_path):
    directory = progress_directory(
        tmp_path, ProgressBranch.DELETED, ProgressBranch.OPEN
    )
    removed = directory.remove_finished(
        branch_pull_requests(), frozenset({ProgressBranch.OPEN}), "other"
    )
    assert removed == [ProgressBranch.DELETED]


def test_the_notes_of_a_branch_with_no_pull_request_yet_stay(tmp_path):
    directory = progress_directory(tmp_path, ProgressBranch.UNOPENED)
    removed = directory.remove_finished(
        branch_pull_requests(), frozenset({ProgressBranch.UNOPENED}), "other"
    )
    assert removed == []


def test_the_branch_being_saved_keeps_its_notes(tmp_path):
    directory = progress_directory(tmp_path, ProgressBranch.MERGED)
    removed = directory.remove_finished(
        branch_pull_requests(),
        frozenset({ProgressBranch.MERGED}),
        ProgressBranch.MERGED,
    )
    assert removed == []


def test_an_empty_remote_branch_list_prunes_nothing(tmp_path):
    directory = progress_directory(tmp_path, ProgressBranch.OPEN)
    with pytest.raises(EmptyRemoteBranchListError):
        directory.remove_finished(branch_pull_requests(), frozenset(), "other")
    assert directory.branches() == [ProgressBranch.OPEN]


# %% pruning against the remote


@pytest.fixture
def checkout_with_remote(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A checkout whose ``origin`` names :data:`REPOSITORY` and holds the open, merged and
    reopened branches.
    """
    remote = initialize_bare_repository(
        scratch_repository.project_root.parent
        / REPOSITORY.owner
        / f"{REPOSITORY.name}.git"
    )
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.run_git("remote", "add", "origin", remote.as_uri())
    for branch in (ProgressBranch.OPEN, ProgressBranch.MERGED, ProgressBranch.REOPENED):
        scratch_repository.run_git("push", "--quiet", "origin", f"HEAD:{branch}")
    return scratch_repository


def pruning(
    checkout: ScratchRepository, directory: ProgressNotesDirectory
) -> ProgressNotesPruning:
    """
    :return: A prune of *directory* against *checkout*'s ``origin``, keeping the open
        branch.
    """
    return ProgressNotesPruning(
        directory=directory,
        git=GitCommandRunner(checkout.project_root),
        remote="origin",
        kept_branch=ProgressBranch.OPEN,
    )


def without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Remove every GitHub credential from the environment.
    """
    for variable in CREDENTIAL_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_pruning_without_a_credential_removes_nothing(
    checkout_with_remote, tmp_path, monkeypatch
):
    without_credentials(monkeypatch)
    directory = progress_directory(tmp_path / "notes", ProgressBranch.MERGED)
    outcome = pruning(checkout_with_remote, directory).run()
    assert outcome == PruningSkipped.NO_CREDENTIAL
    assert directory.branches() == [ProgressBranch.MERGED]


def test_pruning_against_an_unreadable_remote_removes_nothing(
    checkout_with_remote, tmp_path, monkeypatch
):
    monkeypatch.setenv(CREDENTIAL_VARIABLES[0], "token")
    checkout_with_remote.run_git("remote", "set-url", "origin", str(tmp_path / "gone"))
    directory = progress_directory(tmp_path / "notes", ProgressBranch.MERGED)
    outcome = pruning(checkout_with_remote, directory).run()
    assert outcome == PruningSkipped.REMOTE_UNREADABLE
    assert directory.branches() == [ProgressBranch.MERGED]


def test_pruning_removes_the_finished_and_deleted_branches_notes(
    checkout_with_remote, tmp_path, monkeypatch
):
    without_credentials(monkeypatch)
    monkeypatch.setenv(CREDENTIAL_VARIABLES[0], "token")
    monkeypatch.setattr(
        GitHubRepository, "pull_requests", lambda self, state: PULL_REQUESTS
    )
    directory = progress_directory(
        tmp_path / "notes",
        ProgressBranch.OPEN,
        ProgressBranch.MERGED,
        ProgressBranch.REOPENED,
        ProgressBranch.DELETED,
    )
    outcome = pruning(checkout_with_remote, directory).run()
    assert outcome == sorted([ProgressBranch.DELETED, ProgressBranch.MERGED])
    assert directory.branches() == sorted(
        [ProgressBranch.OPEN, ProgressBranch.REOPENED]
    )
