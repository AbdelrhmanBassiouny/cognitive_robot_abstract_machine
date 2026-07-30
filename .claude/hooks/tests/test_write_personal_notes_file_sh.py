"""
Integration tests for write-personal-notes-file.sh: the one-file write it performs on
the personal-notes branch, and the guarantees it keeps while delegating the worktree
work to write-branch-files.sh.

Runs against a scratch project root with a local bare repository standing in for the
notes remote - no network access involved.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scratch_repository import NOTES_BRANCH, ScratchRepository

NOTES_PATH = ".claude/personal/cram-notes.md"


@pytest.fixture
def writer_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository with the wrapper, the primitive it delegates to, and a notes
    branch already published.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready for a write.
    """
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh",
        "write-branch-files.sh",
        "write-personal-notes-file.sh",
    )
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch({NOTES_PATH: "the notes\n"})
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def run_write_personal_notes_file(
    repository: ScratchRepository, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's write-personal-notes-file.sh.

    :param repository: A fixture-built scratch repository.
    :param arguments: The arguments to pass to the script.
    :return: The finished subprocess.
    """
    return subprocess.run(
        [
            "bash",
            str(
                repository.project_root
                / ".claude"
                / "hooks"
                / "write-personal-notes-file.sh"
            ),
            *arguments,
        ],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
    )


def test_writes_the_file_to_the_notes_branch(
    writer_repository: ScratchRepository, tmp_path: Path
):
    source = writer_repository.write("sources/notes.md", "rewritten notes\n")

    result = run_write_personal_notes_file(
        writer_repository,
        "--source",
        str(source),
        "--destination",
        NOTES_PATH,
        "--message",
        "Update the notes",
    )

    assert result.returncode == 0, result.stderr
    checkout = writer_repository.clone_notes_branch(tmp_path / "notes")
    assert (checkout / NOTES_PATH).read_text() == "rewritten notes\n"


def test_pushes_nothing_when_the_content_already_matches(
    writer_repository: ScratchRepository,
):
    source = writer_repository.write("sources/notes.md", "the notes\n")
    commit_before = writer_repository.notes_branch_commit()

    result = run_write_personal_notes_file(
        writer_repository,
        "--source",
        str(source),
        "--destination",
        NOTES_PATH,
        "--message",
        "Update the notes",
    )

    assert result.returncode == 0, result.stderr
    assert writer_repository.notes_branch_commit() == commit_before


def test_refuses_when_the_notes_branch_does_not_exist_yet(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh",
        "write-branch-files.sh",
        "write-personal-notes-file.sh",
    )
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.resolve_notes_remote_to()
    source = scratch_repository.write("sources/notes.md", "notes\n")

    result = run_write_personal_notes_file(
        scratch_repository,
        "--source",
        str(source),
        "--destination",
        NOTES_PATH,
        "--message",
        "Update the notes",
    )

    assert result.returncode != 0
    assert NOTES_BRANCH in result.stderr
    assert "create-personal-notes-branch.sh" in result.stderr


@pytest.mark.parametrize("destination", ["/etc/passwd", "../escape.md"])
def test_rejects_a_destination_outside_the_branch(
    writer_repository: ScratchRepository, destination: str
):
    source = writer_repository.write("sources/notes.md", "payload\n")

    result = run_write_personal_notes_file(
        writer_repository,
        "--source",
        str(source),
        "--destination",
        destination,
        "--message",
        "Update the notes",
    )

    assert result.returncode != 0
    assert destination in result.stderr


def test_requires_all_three_arguments(writer_repository: ScratchRepository):
    source = writer_repository.write("sources/notes.md", "notes\n")

    result = run_write_personal_notes_file(
        writer_repository, "--source", str(source), "--destination", NOTES_PATH
    )

    assert result.returncode != 0
    assert "--message" in result.stderr
