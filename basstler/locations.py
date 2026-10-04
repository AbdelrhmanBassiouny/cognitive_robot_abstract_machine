"""
Every file and directory this package names, each written once.

..note:: Imports nothing outside the standard library, since :mod:`basstler.dependencies`
    reads its declaration's location from here before anything is installed.
"""

from __future__ import annotations

import os
from enum import Enum, StrEnum
from pathlib import Path


class PathEnumeration(Enum):
    """
    An enumeration whose members are paths.

    A member is accepted wherever a path is - joined onto another with ``/``, opened, or
    passed to a subprocess - and formats as its path's text.
    """

    _value_: Path

    def __fspath__(self) -> str:
        """
        :return: The path's text, for anything that accepts a path-like object.
        """
        return os.fspath(self.value)

    def __str__(self) -> str:
        """
        :return: The path's text, so a member formats as its path rather than its name.
        """
        return str(self.value)

    def __truediv__(self, child: str | os.PathLike[str]) -> Path:
        """
        :param child: What to join beneath this path.
        :return: The joined path.
        """
        return self.value / child


class PackageLocation(PathEnumeration):
    """
    The package's own directory and the files shipped in it, as absolute paths.
    """

    DIRECTORY = Path(__file__).parent
    """
    This package's own directory, which is also the directory it *is* rather than lives
    under.
    """

    REPOSITORY_ROOT = DIRECTORY.parent
    """
    The repository root, which is the directory ``basstler`` imports from with no install.
    """

    STACK_CONFIGURATION = DIRECTORY / "stack.toml"
    """
    The checked-in stack configuration every run starts from, before any per-user override.
    """

    BOARD = DIRECTORY / "board.json"
    """
    The exported snapshot of the fork's open pull requests - scratch state, never committed.
    """

    DEPENDENCY_DECLARATION = DIRECTORY / "pyproject.toml"
    """
    The package metadata, whose ``[project] dependencies`` this package installs.
    """

    TEMPLATES = DIRECTORY / "templates"
    """
    The page templates dashboards are rendered from.
    """

    QUERIES = DIRECTORY / "queries"
    """
    The GraphQL documents the upstream review reader sends.
    """


class HookScript(StrEnum):
    """
    The shell entry points under :attr:`ProjectLocation.HOOKS`, named once so a caller - a
    test installing one into a scratch layout, or a module invoking one - never spells a
    file name itself.
    """

    CONFIGURATION = "resolve-personal-notes-config.sh"
    """
    Resolves the personal-notes remote and branch, and fetches it.
    """

    CHECK_SETUP = "check-setup.sh"
    """
    Reports, read-only, whether a clone is set up.
    """

    CREATE_NOTES_BRANCH = "create-personal-notes-branch.sh"
    """
    Creates the personal-notes branch on the resolved remote.
    """

    WRITE_NOTES_FILE = "write-personal-notes-file.sh"
    """
    Commits one file to that branch and pushes it.
    """

    GITHUB_API = "github-api.sh"
    """
    Reaches GitHub through ``gh`` or a token and ``curl``.
    """

    SETUP = "setup-personal-notes.sh"
    """
    Runs the whole first-time setup non-interactively.
    """

    SESSION_START = "session-start.sh"
    """
    The SessionStart hook, which writes ``CLAUDE.local.md`` and prints its summary.
    """

    SESSION_START_MESSAGES = "session-start-messages.sh"
    """
    The wording of every line of that summary.
    """

    SAVE_GIT_IDENTITY = "save-git-identity.sh"
    """
    Records this clone's git identity onto the notes branch.
    """

    SAVE_PERSONAL_SETTINGS = "save-personal-settings.sh"
    """
    Pushes this clone's Claude Code settings back to the notes branch.
    """

    SAVE_PLAN = "save-plan.sh"
    """
    Pushes an edited manifest and roadmap to the personal-notes branch.
    """

    PLAN_UPDATES_SINCE = "plan-updates-since.sh"
    """
    Reports what changed on a plan since a recorded commit.
    """

    @property
    def path(self) -> Path:
        """
        The script's path from the project root.
        """
        return ProjectLocation.HOOKS / self.value


class ProjectLocation(PathEnumeration):
    """
    The files this package reads, runs or writes in a project, relative to its root.

    Those on the personal-notes branch are relative to that branch's root, which is the
    same tree.
    """

    CLAUDE_CODE_DIRECTORY = Path(".claude")
    """
    The directory Claude Code reads a project's settings, hooks and skills from.
    """

    HOOKS = CLAUDE_CODE_DIRECTORY / "hooks"
    """
    The shell entry points that read and write personal-notes data.
    """

    PERSONAL_NOTES = CLAUDE_CODE_DIRECTORY / "personal"
    """
    Where the personal-notes branch keeps everything it holds.
    """

    PACKAGE = Path(PackageLocation.DIRECTORY.value.name)
    """
    This package's own directory.
    """

    PERSONAL_NOTES_CONFIGURATION_SCRIPT = HOOKS / HookScript.CONFIGURATION
    """
    The shell configuration that resolves the personal-notes remote and branch, and
    fetches it.
    """

    PERSONAL_NOTES_WRITER_SCRIPT = HOOKS / HookScript.WRITE_NOTES_FILE
    """
    The helper that commits one file to the personal-notes branch and pushes it.
    """

    PERSONAL_NOTES_BRANCH_CREATION_SCRIPT = HOOKS / HookScript.CREATE_NOTES_BRANCH
    """
    The helper that creates the personal-notes branch where it does not exist yet.
    """

    PERSONAL_NOTES_DOCUMENT = PERSONAL_NOTES / "cram-notes.md"
    """
    The notes file itself, unless a clone's settings put it elsewhere.
    """

    PLANS = PERSONAL_NOTES / "plans"
    """
    Where plans live on the personal-notes branch.

    Mirrors ``PLANS_DIR`` in ``resolve-personal-notes-config.sh``, which is the shell half
    of the same tooling; a test holds the two equal so the mirror cannot drift.
    """

    PERSONAL_STACK_CONFIGURATION = PERSONAL_NOTES / "stack.toml"
    """
    The per-user override of :attr:`PackageLocation.STACK_CONFIGURATION`.
    """

    PLAN_ITEM_MODE_DEFAULTS = PACKAGE / "plan-item-modes.toml"
    """
    The shipped plan-item execution modes.
    """

    PERSONAL_PLAN_ITEM_MODES = PERSONAL_NOTES / "plan-item-modes.toml"
    """
    The per-user override of :attr:`PLAN_ITEM_MODE_DEFAULTS`.
    """
