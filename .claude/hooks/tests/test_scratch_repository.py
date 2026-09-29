"""
Tests for the scratch layout the hook tests run against.

The subject here is installation completeness: a hook script that shells out to a
sibling is only runnable in the scratch layout if that sibling is there too, and a
module that names only the script it is testing must still get a layout the script can
run in.
"""

from __future__ import annotations

from scratch_repository import ScratchRepository
from tooling_files import HOOKS_DIRECTORY, HookScript


def installed_hook_scripts(repository: ScratchRepository) -> set[HookScript]:
    """
    Read back which hook scripts the scratch layout actually holds.

    :param repository: The scratch repository to inspect.
    :return: The scripts present in its hooks directory.
    """
    hooks_directory = repository.project_root / HOOKS_DIRECTORY
    return {HookScript(path.name) for path in hooks_directory.iterdir()}


# %% a script arrives with what it runs


def test_installs_the_configuration_every_script_sources(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts(HookScript.CHECK_SETUP)
    assert installed_hook_scripts(scratch_repository) == {
        HookScript.CHECK_SETUP,
        HookScript.CONFIGURATION,
    }


def test_installs_a_sibling_reached_through_a_configuration_constant(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts(HookScript.WRITE_NOTES_FILE)
    assert installed_hook_scripts(scratch_repository) == {
        HookScript.WRITE_NOTES_FILE,
        HookScript.WRITE_BRANCH_FILES,
        HookScript.CONFIGURATION,
    }


def test_installs_a_sibling_reached_through_the_script_directory(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts(HookScript.SESSION_START)
    assert installed_hook_scripts(scratch_repository) == {
        HookScript.SESSION_START,
        HookScript.SESSION_START_MESSAGES,
        HookScript.CHECK_SETUP,
        HookScript.CONFIGURATION,
    }


def test_installs_what_a_sibling_itself_runs(scratch_repository: ScratchRepository):
    scratch_repository.install_hook_scripts(HookScript.SAVE_GIT_IDENTITY)
    assert installed_hook_scripts(scratch_repository) == {
        HookScript.SAVE_GIT_IDENTITY,
        HookScript.WRITE_NOTES_FILE,
        HookScript.WRITE_BRANCH_FILES,
        HookScript.CONFIGURATION,
    }


def test_installs_only_the_script_when_it_runs_no_other(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts(HookScript.SESSION_START_MESSAGES)
    assert installed_hook_scripts(scratch_repository) == {
        HookScript.SESSION_START_MESSAGES
    }
