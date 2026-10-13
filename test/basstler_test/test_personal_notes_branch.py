"""
Tests for personal_notes_branch.py: finding, fetching and writing the personal-notes
branch.
"""

from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from basstler.exceptions import NotesBranchMissingError, UnsafeNotesPathError
from basstler.maintenance_git_commands import GitCommandRunner
from basstler.personal_notes_branch import (
    NotesBranchWriter,
    NotesWriteOutcome,
    PersonalNotesBranch,
    PersonalNotesLocation,
)
from basstler.setup_steps import PersonalNotesSetting

from .constants import ScratchBranch
from .scratch_repository import ScratchRepository, initialize_bare_repository

NOTES_FILE = PurePosixPath(".claude/personal/cram-notes.md")
"""
The notes file the published notes branch carries.
"""


@pytest.fixture
def notes_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository on a work branch, whose configured notes remote carries a
    published notes branch.
    """
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch({NOTES_FILE: "- a rule\n"})
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def notes_branch(repository: ScratchRepository) -> PersonalNotesBranch:
    """
    :return: The notes branch as *repository*'s own configuration resolves it.
    """
    return PersonalNotesBranch(
        location=PersonalNotesLocation.resolve(repository.project_root, {}),
        git=GitCommandRunner(repository.project_root),
    )


def published_file(repository: ScratchRepository, path: PurePosixPath) -> str | None:
    """
    :return: *path*'s content on the notes remote's branch, if it exists there.
    """
    checkout = repository.clone_notes_branch(repository.project_root.parent / "verify")
    file = checkout / path
    return file.read_text() if file.exists() else None


def notes_commit_count(repository: ScratchRepository) -> int:
    """
    :return: How many commits the notes remote's branch holds.
    """
    return int(
        GitCommandRunner(repository.notes_remote_path).run(
            "rev-list", "--count", ScratchBranch.PERSONAL_NOTES
        )
    )


# %% where the notes live


def test_the_location_reads_the_configured_remote(notes_repository):
    location = PersonalNotesLocation.resolve(notes_repository.project_root, {})
    assert location == PersonalNotesLocation(
        remote=str(notes_repository.notes_remote_path),
        branch=PersonalNotesSetting.BRANCH.default,
        notes_path=PersonalNotesSetting.PATH.default,
    )


# %% fetching


def test_fetching_reports_the_configured_remote(notes_repository):
    assert notes_branch(notes_repository).fetch() == str(
        notes_repository.notes_remote_path
    )


def test_fetching_falls_back_to_the_current_branchs_upstream(notes_repository):
    empty_remote = initialize_bare_repository(
        notes_repository.project_root.parent / "empty.git"
    )
    notes_repository.resolve_notes_remote_to(empty_remote)
    notes_repository.run_git(
        "remote", "add", "fork", str(notes_repository.notes_remote_path)
    )
    notes_repository.run_git("push", "--quiet", "fork", ScratchBranch.WORK)
    notes_repository.run_git(
        "branch", "--quiet", "--set-upstream-to", f"fork/{ScratchBranch.WORK}"
    )

    assert notes_branch(notes_repository).fetch() == "fork"


def test_fetching_a_missing_branch_names_every_remote_tried(notes_repository):
    empty_remote = initialize_bare_repository(
        notes_repository.project_root.parent / "empty.git"
    )
    notes_repository.resolve_notes_remote_to(empty_remote)
    with pytest.raises(NotesBranchMissingError) as raised:
        notes_branch(notes_repository).fetch()
    assert raised.value.attempted_remotes == (str(empty_remote),)


# %% writing


def test_writing_pushes_the_file(notes_repository):
    path = PurePosixPath(".claude/personal/pr-progress/work.md")
    writer = NotesBranchWriter(notes_branch(notes_repository))
    outcome = writer.write({path: "- Next: a step.\n"}, "Save progress")
    assert outcome == NotesWriteOutcome.PUSHED
    assert published_file(notes_repository, path) == "- Next: a step.\n"


def test_writing_unchanged_content_pushes_nothing(notes_repository):
    commits_before = notes_commit_count(notes_repository)
    writer = NotesBranchWriter(notes_branch(notes_repository))
    outcome = writer.write({NOTES_FILE: "- a rule\n"}, "Save notes")
    assert outcome == NotesWriteOutcome.UNCHANGED
    assert notes_commit_count(notes_repository) == commits_before


def test_writing_none_removes_the_path(notes_repository):
    writer = NotesBranchWriter(notes_branch(notes_repository))
    outcome = writer.write({NOTES_FILE: None}, "Remove notes")
    assert outcome == NotesWriteOutcome.PUSHED
    assert published_file(notes_repository, NOTES_FILE) is None


def test_writing_leaves_no_worktree_behind(notes_repository):
    worktrees_before = notes_repository.run_git("worktree", "list").stdout
    NotesBranchWriter(notes_branch(notes_repository)).write(
        {NOTES_FILE: "- another rule\n"}, "Save notes"
    )
    assert notes_repository.run_git("worktree", "list").stdout == worktrees_before


@pytest.mark.parametrize(
    "path", [PurePosixPath("/etc/passwd"), PurePosixPath(".claude/../outside.md")]
)
def test_writing_outside_the_branch_is_refused(notes_repository, path):
    commits_before = notes_commit_count(notes_repository)
    writer = NotesBranchWriter(notes_branch(notes_repository))
    with pytest.raises(UnsafeNotesPathError):
        writer.write({path: "x\n"}, "Escape")
    assert notes_commit_count(notes_repository) == commits_before
