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

from scratch_repository import (
    HOOKS_SOURCE_DIRECTORY,
    NOTES_BRANCH,
    NOTES_PATH,
    ScratchRepository,
    ShellProgram,
)
from stub_executables import StubExecutableDirectory
from tooling_files import HookScript

NO_UPSTREAM_REPORT = "upstream=[]"
"""
What print_upstream_remote.sh prints when the current branch tracks nothing.
"""


def run_create_notes_branch(
    repository: ScratchRepository, stub_executables: StubExecutableDirectory
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's create-personal-notes-branch.sh.

    :param repository: A fixture-built scratch repository.
    :param stub_executables: The stub directory the run resolves its executables from.
    :return: The finished subprocess.
    """
    return subprocess.run(
        ["bash", str(repository.hook_script_path(HookScript.CREATE_NOTES_BRANCH))],
        cwd=repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(),
    )


def test_creates_the_branch_when_the_current_branch_has_no_upstream(
    scratch_repository: ScratchRepository,
    stub_executables: StubExecutableDirectory,
    tmp_path: Path,
):
    scratch_repository.install_hook_scripts(HookScript.CREATE_NOTES_BRANCH)
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.resolve_notes_remote_to()
    assert not scratch_repository.has_upstream()

    result = run_create_notes_branch(scratch_repository, stub_executables)

    assert result.returncode == 0, result.stderr
    assert scratch_repository.notes_branch_commit() is not None
    checkout = scratch_repository.clone_notes_branch(tmp_path / "notes-checkout")
    assert (checkout / NOTES_PATH).read_text() == ""


def test_reports_no_upstream_remote_without_failing(
    scratch_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    scratch_repository.install_hook_scripts(HookScript.CONFIGURATION)
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    assert not scratch_repository.has_upstream()

    # The strict-mode caller is the point: create-personal-notes-branch.sh assigns this
    # helper's output at top level under `set -euo pipefail`, so a non-zero status here
    # aborts the whole script rather than reading as "there is no upstream".
    result = subprocess.run(
        [
            "bash",
            str(ShellProgram.PRINT_UPSTREAM_REMOTE.path),
            str(scratch_repository.hook_script_path(HookScript.CONFIGURATION)),
        ],
        cwd=scratch_repository.project_root,
        capture_output=True,
        text=True,
        env=stub_executables.subprocess_environment(),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == NO_UPSTREAM_REPORT


def test_still_refuses_when_the_branch_already_exists_on_the_remote(
    scratch_repository: ScratchRepository, stub_executables: StubExecutableDirectory
):
    scratch_repository.install_hook_scripts(HookScript.CREATE_NOTES_BRANCH)
    scratch_repository.write("README.md", "scratch\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch({NOTES_PATH: "already mine\n"})
    scratch_repository.resolve_notes_remote_to()
    existing_commit = scratch_repository.notes_branch_commit()

    result = run_create_notes_branch(scratch_repository, stub_executables)

    assert result.returncode != 0
    assert NOTES_BRANCH in result.stderr
    assert scratch_repository.notes_branch_commit() == existing_commit


def test_installing_a_script_installs_what_it_sources(
    scratch_repository: ScratchRepository,
):
    # create-personal-notes-branch.sh sources resolve-personal-notes-config.sh, which no
    # caller names: a script's own dependencies are stated in the script, and following
    # them is what stops a hook that grows one from breaking every test that installs it.
    scratch_repository.install_hook_scripts(HookScript.CREATE_NOTES_BRANCH)

    assert scratch_repository.hook_script_path(
        HookScript.CONFIGURATION
    ).read_text() == (
        (HOOKS_SOURCE_DIRECTORY / HookScript.CONFIGURATION.value).read_text()
    )
