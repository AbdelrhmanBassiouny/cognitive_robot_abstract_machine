"""
Integration tests for create-personal-notes-branch.sh on a clone whose current branch
has no upstream.

That is the ordinary state of a branch created locally and not yet pushed, and of the
scratch repositories these tests build - so the branch creation has to work there rather
than only on a branch that already tracks a remote.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from scratch_repository import NOTES_BRANCH, ScratchRepository
from stub_executables import StubExecutableDirectory

NOTES_PATH = ".claude/personal/cram-notes.md"


def has_upstream(repository: ScratchRepository) -> bool:
    """
    Report whether the scratch repository's current branch tracks a remote.

    :param repository: The scratch repository to inspect.
    :return: Whether an upstream is configured.
    """
    return (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            cwd=repository.project_root,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def test_creates_the_branch_when_the_current_branch_has_no_upstream(
    scratch_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh", "create-personal-notes-branch.sh"
    )
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.resolve_notes_remote_to()
    assert not has_upstream(scratch_repository)

    result = subprocess.run(
        [
            "bash",
            str(
                scratch_repository.project_root
                / ".claude"
                / "hooks"
                / "create-personal-notes-branch.sh"
            ),
        ],
        cwd=scratch_repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(),
    )

    assert result.returncode == 0, result.stderr
    assert scratch_repository.notes_branch_commit() is not None
    checkout = scratch_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert (checkout / NOTES_PATH).read_text() == ""


def test_reports_no_upstream_remote_without_failing(
    scratch_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    scratch_repository.install_hook_scripts("resolve-personal-notes-config.sh")
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    assert not has_upstream(scratch_repository)

    # The strict-mode caller is the point: create-personal-notes-branch.sh assigns this
    # helper's output at top level under `set -euo pipefail`, so a non-zero status here
    # aborts the whole script rather than reading as "there is no upstream".
    result = subprocess.run(
        [
            "bash",
            "-c",
            'set -euo pipefail; source "$1"; '
            'upstream="$(current_branch_upstream_remote)"; '
            'printf "upstream=[%s]\\n" "${upstream}"',
            "upstream-remote-test",
            str(
                scratch_repository.project_root
                / ".claude"
                / "hooks"
                / "resolve-personal-notes-config.sh"
            ),
        ],
        cwd=scratch_repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "upstream=[]"


def test_still_refuses_when_the_branch_already_exists_on_the_remote(
    scratch_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    scratch_repository.install_hook_scripts(
        "resolve-personal-notes-config.sh", "create-personal-notes-branch.sh"
    )
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch({NOTES_PATH: "already mine\n"})
    scratch_repository.resolve_notes_remote_to()
    existing_commit = scratch_repository.notes_branch_commit()

    result = subprocess.run(
        [
            "bash",
            str(
                scratch_repository.project_root
                / ".claude"
                / "hooks"
                / "create-personal-notes-branch.sh"
            ),
        ],
        cwd=scratch_repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(),
    )

    assert result.returncode != 0
    assert NOTES_BRANCH in result.stderr
    assert scratch_repository.notes_branch_commit() == existing_commit
