"""
Integration tests for save-pr-progress.sh's size gate, run against a local bare
repository standing in for the personal-notes remote.
"""

from __future__ import annotations

import subprocess

import pytest

from basstler.locations import ProjectLocation
from basstler.maintenance_constants import CREDENTIAL_VARIABLES
from basstler.plan_item_bootstrap import HookScript
from basstler.plan_size_limits import Measure
from basstler.progress_notes import ProgressNotesFile

from .constants import (
    ClaudeLocalSection,
    HookFile,
    PersonalNotesPath,
    ProgressBranch,
    ScratchBranch,
)
from .scratch_repository import ScratchRepository


@pytest.fixture
def progress_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository on a pull request branch, carrying the real save-pr-progress.sh
    and the package it checks the notes with.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready to run save-pr-progress.sh against.
    """
    scratch_repository.install_hook_scripts(
        HookScript.CONFIGURATION, HookFile.SAVE_PULL_REQUEST_PROGRESS
    )
    scratch_repository.install_package()
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {ProjectLocation.PERSONAL_NOTES / "placeholder.md": "notes\n"}
    )
    scratch_repository.resolve_notes_remote_to()
    return scratch_repository


def save_progress(
    repository: ScratchRepository, progress: str, **environment: str
) -> subprocess.CompletedProcess[str]:
    """
    Write *progress* between CLAUDE.local.md's progress markers, then run the hook.

    :param repository: A fixture-built scratch repository.
    :param progress: The progress notes to save.
    :param environment: Variables to set for the hook.
    :return: The finished hook.
    """
    repository.write(
        PersonalNotesPath.CLAUDE_LOCAL,
        ClaudeLocalSection.PULL_REQUEST_PROGRESS.around(progress),
    )
    return repository.run_hook_script(
        HookFile.SAVE_PULL_REQUEST_PROGRESS, **environment
    )


def saved_progress(repository: ScratchRepository) -> str:
    """
    :return: The work branch's progress notes as the notes branch now holds them.
    """
    checkout = repository.clone_notes_branch(repository.project_root.parent / "verify")
    return (
        checkout
        / PersonalNotesPath.PULL_REQUEST_PROGRESS
        / f"{ScratchBranch.WORK}{ProgressNotesFile.SUFFIX}"
    ).read_text()


def test_progress_within_the_limit_is_saved(progress_repository: ScratchRepository):
    progress = "- Next: write the tests.\n"
    result = save_progress(progress_repository, progress)
    assert result.returncode == 0, result.stderr
    assert saved_progress(progress_repository) == progress


def test_progress_over_the_limit_is_refused_and_not_pushed(
    progress_repository: ScratchRepository,
):
    result = save_progress(
        progress_repository, "x" * (Measure.PROGRESS_LENGTH.maximum + 1) + "\n"
    )
    assert result.returncode == 1
    assert Measure.PROGRESS_LENGTH.description in result.stderr
    checkout = progress_repository.clone_notes_branch(
        progress_repository.project_root.parent / "verify"
    )
    assert not (checkout / PersonalNotesPath.PULL_REQUEST_PROGRESS).exists()


# %% pruning finished branches' notes


def test_without_a_credential_the_save_goes_ahead_unpruned(
    progress_repository: ScratchRepository,
):
    other_notes = (
        PersonalNotesPath.PULL_REQUEST_PROGRESS
        / f"{ProgressBranch.MERGED}{ProgressNotesFile.SUFFIX}"
    )
    progress_repository.update_notes_branch_file(other_notes, "- Done.\n")

    result = save_progress(
        progress_repository,
        "- Next: a step.\n",
        **{variable: "" for variable in CREDENTIAL_VARIABLES},
    )

    assert result.returncode == 0, result.stderr
    checkout = progress_repository.clone_notes_branch(
        progress_repository.project_root.parent / "verify"
    )
    assert (checkout / other_notes).exists()
