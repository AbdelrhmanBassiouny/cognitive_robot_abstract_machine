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

from .constants import DatasetLocation
from .scratch_repository import ScratchRepository, initialize_bare_repository

PULL_REQUESTS = json.loads(
    (DatasetLocation.DIRECTORY / "pull-requests-by-branch.json").read_text()
)
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
    assert branch_pull_requests().open_branches == {"open-work", "reopened-work"}


def test_a_branch_whose_pull_requests_all_closed_is_finished():
    assert branch_pull_requests().finished_branches == {"merged-work"}


# %% pruning


def test_the_notes_of_a_finished_branch_are_removed(tmp_path):
    directory = progress_directory(tmp_path, "merged-work", "open-work")
    removed = directory.remove_finished(
        branch_pull_requests(), frozenset({"merged-work", "open-work"}), "other"
    )
    assert removed == ["merged-work"]
    assert directory.branches() == ["open-work"]


def test_the_notes_of_a_branch_gone_from_the_remote_are_removed(tmp_path):
    directory = progress_directory(tmp_path, "claude/deleted-work", "open-work")
    removed = directory.remove_finished(
        branch_pull_requests(), frozenset({"open-work"}), "other"
    )
    assert removed == ["claude/deleted-work"]


def test_the_notes_of_a_branch_with_no_pull_request_yet_stay(tmp_path):
    directory = progress_directory(tmp_path, "unopened-work")
    removed = directory.remove_finished(
        branch_pull_requests(), frozenset({"unopened-work"}), "other"
    )
    assert removed == []


def test_the_branch_being_saved_keeps_its_notes(tmp_path):
    directory = progress_directory(tmp_path, "merged-work")
    removed = directory.remove_finished(
        branch_pull_requests(), frozenset({"merged-work"}), "merged-work"
    )
    assert removed == []


def test_an_empty_remote_branch_list_prunes_nothing(tmp_path):
    directory = progress_directory(tmp_path, "open-work")
    with pytest.raises(EmptyRemoteBranchListError):
        directory.remove_finished(branch_pull_requests(), frozenset(), "other")
    assert directory.branches() == ["open-work"]


# %% pruning against the remote


@pytest.fixture
def checkout_with_remote(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A checkout whose ``origin`` names ``owner/repo`` and holds the branches ``open-
    work``, ``merged-work`` and ``reopened-work``.
    """
    remote = initialize_bare_repository(
        scratch_repository.project_root.parent / "owner" / "repo.git"
    )
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.run_git("remote", "add", "origin", remote.as_uri())
    for branch in ("open-work", "merged-work", "reopened-work"):
        scratch_repository.run_git("push", "--quiet", "origin", f"HEAD:{branch}")
    return scratch_repository


def pruning(
    checkout: ScratchRepository, directory: ProgressNotesDirectory
) -> ProgressNotesPruning:
    """
    :return: A prune of *directory* against *checkout*'s ``origin``, keeping
        ``open-work``.
    """
    return ProgressNotesPruning(
        directory=directory,
        git=GitCommandRunner(checkout.project_root),
        remote="origin",
        kept_branch="open-work",
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
    directory = progress_directory(tmp_path / "notes", "merged-work")
    outcome = pruning(checkout_with_remote, directory).run()
    assert outcome == PruningSkipped.NO_CREDENTIAL
    assert directory.branches() == ["merged-work"]


def test_pruning_against_an_unreadable_remote_removes_nothing(
    checkout_with_remote, tmp_path, monkeypatch
):
    monkeypatch.setenv(CREDENTIAL_VARIABLES[0], "token")
    checkout_with_remote.run_git("remote", "set-url", "origin", str(tmp_path / "gone"))
    directory = progress_directory(tmp_path / "notes", "merged-work")
    outcome = pruning(checkout_with_remote, directory).run()
    assert outcome == PruningSkipped.REMOTE_UNREADABLE
    assert directory.branches() == ["merged-work"]


def test_pruning_removes_the_finished_and_deleted_branches_notes(
    checkout_with_remote, tmp_path, monkeypatch
):
    without_credentials(monkeypatch)
    monkeypatch.setenv(CREDENTIAL_VARIABLES[0], "token")
    monkeypatch.setattr(
        GitHubRepository, "pull_requests", lambda self, state: PULL_REQUESTS
    )
    directory = progress_directory(
        tmp_path / "notes", "open-work", "merged-work", "reopened-work", "deleted-work"
    )
    outcome = pruning(checkout_with_remote, directory).run()
    assert outcome == ["deleted-work", "merged-work"]
    assert directory.branches() == ["open-work", "reopened-work"]
