"""
Tests for the scratch layout the hook tests run against.

The subject here is installation completeness: a hook script that shells out to a
sibling is only runnable in the scratch layout if that sibling is there too, and a
module that names only the script it is testing must still get a layout the script can
run in.
"""

from __future__ import annotations

from scratch_repository import ScratchRepository


def installed_hook_scripts(repository: ScratchRepository) -> set[str]:
    """
    Read back which hook scripts the scratch layout actually holds.

    :param repository: The scratch repository to inspect.
    :return: The file names present in its hooks directory.
    """
    hooks_directory = repository.project_root / ".claude" / "hooks"
    return {path.name for path in hooks_directory.iterdir()}


# %% a script arrives with what it runs


def test_installs_the_configuration_every_script_sources(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts("check-setup.sh")
    assert installed_hook_scripts(scratch_repository) == {
        "check-setup.sh",
        "resolve-personal-notes-config.sh",
    }


def test_installs_a_sibling_reached_through_a_configuration_constant(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts("write-personal-notes-file.sh")
    assert installed_hook_scripts(scratch_repository) == {
        "write-personal-notes-file.sh",
        "write-branch-files.sh",
        "resolve-personal-notes-config.sh",
    }


def test_installs_a_sibling_reached_through_the_script_directory(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts("session-start.sh")
    assert installed_hook_scripts(scratch_repository) == {
        "session-start.sh",
        "session-start-messages.sh",
        "check-setup.sh",
        "resolve-personal-notes-config.sh",
    }


def test_installs_what_a_sibling_itself_runs(scratch_repository: ScratchRepository):
    scratch_repository.install_hook_scripts("save-git-identity.sh")
    assert installed_hook_scripts(scratch_repository) == {
        "save-git-identity.sh",
        "write-personal-notes-file.sh",
        "write-branch-files.sh",
        "resolve-personal-notes-config.sh",
    }


def test_installs_only_the_script_when_it_runs_no_other(
    scratch_repository: ScratchRepository,
):
    scratch_repository.install_hook_scripts("session-start-messages.sh")
    assert installed_hook_scripts(scratch_repository) == {"session-start-messages.sh"}
