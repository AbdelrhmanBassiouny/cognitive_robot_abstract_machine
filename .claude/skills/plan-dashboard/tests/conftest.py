"""
Makes the plan-dashboard scripts importable as plain modules, and hands the tests the
scratch git repositories they read plan data out of.

The scripts are single-file scripts run via ``python3 build_dashboard.py ...``, not an
installed package - so their directory is added to ``sys.path`` here rather than
requiring an ``__init__.py``/packaging setup just for tests.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from git_commands import GitCommandRunner
from personal_notes import NOTES_BRANCH_SETTING, NOTES_REMOTE_SETTING
from scratch_repositories import GIT_ENVIRONMENT, ScratchNotesRemote


@pytest.fixture(autouse=True)
def without_inherited_notes_configuration(monkeypatch):
    """
    Strip the caller's own personal-notes settings, so a real remote can never leak into
    a test - and from there onto the network.
    """
    monkeypatch.delenv(NOTES_REMOTE_SETTING.environment_variable, raising=False)
    monkeypatch.delenv(NOTES_BRANCH_SETTING.environment_variable, raising=False)


@pytest.fixture
def scratch_git(tmp_path: Path) -> GitCommandRunner:
    """
    Run git in a scratch repository under a fixed identity.

    The same runner the scripts themselves use, so a test builds its fixtures through
    the code under test rather than through a second way of calling git.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The runner, rooted there and pointed at any other scratch repository with
        :meth:`GitCommandRunner.in_directory`.
    """
    return GitCommandRunner(working_directory=tmp_path, environment=GIT_ENVIRONMENT)


@pytest.fixture
def notes_clone(tmp_path: Path, scratch_git: GitCommandRunner) -> ScratchNotesRemote:
    """
    :param tmp_path: pytest's per-test temporary directory.
    :param scratch_git: The scratch git runner.
    :return: The remote to seed with the plans a test needs.
    """
    return ScratchNotesRemote(root=tmp_path, git=scratch_git)
