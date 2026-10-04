"""
The paths and names more than one suite in this directory needs.

Anything :mod:`basstler` already names - a module, or a location in
:mod:`basstler.locations` - is not written down here: a suite imports it, so a rename
moves with the code instead of leaving a literal behind. What remains has no import to
derive it from: this directory's own dataset, the skill directories, the notes-branch
paths only the shell hooks name, and the names a scratch repository is built with.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from basstler.locations import PathEnumeration, ProjectLocation
from basstler.maintenance_constants import CREDENTIAL_VARIABLES


class DatasetLocation(PathEnumeration):
    """
    This suite's own test data, next to the tests that read it.
    """

    DIRECTORY = Path(__file__).parent / "dataset"
    """
    The dataset directory itself.
    """

    STUBS = DIRECTORY / "stubs"
    """
    Executables copied onto a scratch ``PATH`` to stand in for a real ``gh``, ``curl`` or
    hook script.
    """

    SHELL_PROGRAMS = DIRECTORY / "scripts"
    """
    Shell programs a test runs to observe what the hooks' own shell knows, each in a file
    of its own rather than built as a string.
    """

    UPSTREAM_REVIEW_RESPONSES = DIRECTORY / "upstream-review-responses"
    """
    The recorded GraphQL responses the upstream review reader is replayed against.
    """

    INSTALLED_DISTRIBUTIONS = DIRECTORY / "installed-distributions"
    """
    A directory that reads as installed distributions once it is on ``sys.path``, holding one
    whose name is spelled with every separator a distribution name may use.
    """

    SET_UP_CLONE = DIRECTORY / "set-up-clone"
    """
    A committed tree of everything ``check-setup.sh`` requires of a set-up clone, copied over
    a scratch project root rather than written out file by file.

    Its ``basstler/`` stands in for the real package: the ``tooling_files`` check tests only
    that each path exists, so nothing there is ever imported or run.
    """


class StackBranch(StrEnum):
    """
    The branches a stack under test is built from, named once for every suite that
    builds one.

    A suite names several of them per test, in a board entry, a git command and an
    assertion at once, so a spelling that differs anywhere is a test quietly about a
    branch its stack does not contain.
    """

    PARENT = "a-parent"
    """
    The bottom of the chain, cut from the base.
    """

    CHILD = "a-child"
    """
    Stacked directly on the parent.
    """


class SkillDirectory(PathEnumeration):
    """
    The skills the suites read, relative to the project root.

    Claude Code finds a skill by its path, so the path *is* the interface, and the package
    does not name it.
    """

    PLAN_DASHBOARD = ProjectLocation.CLAUDE_CODE_DIRECTORY / "skills" / "plan-dashboard"
    """
    The dashboard skill: its instructions, its worked example and its shell entry point.
    """

    STACKED_PULL_REQUEST_MAINTENANCE = (
        ProjectLocation.CLAUDE_CODE_DIRECTORY / "skills" / "stacked-pr-maintenance"
    )
    """
    The maintenance pass's own instructions.
    """


class ScratchBranch(StrEnum):
    """
    The branches a scratch repository is given besides a stack's own.
    """

    PERSONAL_NOTES = "claude/personal-notes"
    """
    The personal-notes branch name the hooks resolve to by default.
    """

    WORK = "some-work-branch"
    """
    The throwaway branch a scratch repository is left checked out on.
    """


class PersonalNotesPath(PathEnumeration):
    """
    The files the shell hooks read from the personal-notes branch or write into a clone,
    relative to the project root, that the package itself does not name.
    """

    GIT_IDENTITY = ProjectLocation.PERSONAL_NOTES / "git-identity"
    """
    The recorded git identity a clone with none of its own is given.
    """

    SETTINGS_ON_NOTES_BRANCH = ProjectLocation.PERSONAL_NOTES / "settings.local.json"
    """
    The Claude Code settings the branch carries.
    """

    LOCAL_SETTINGS = ProjectLocation.CLAUDE_CODE_DIRECTORY / "settings.local.json"
    """
    Where those settings are synced to in the clone - the file Claude Code itself reads,
    and writes its own permission grants into.
    """

    BRANCH_INDEX = ProjectLocation.PLANS / "_generated" / "branch-index.tsv"
    """
    The generated reverse index mapping an item's branch to the plan tracking it.
    """


class ProjectFile(PathEnumeration):
    """
    The files in a clone that the hooks read, write or check by fixed convention, relative
    to the project root.

    Anything a contributor can redirect - the notes path among them - is resolved from
    ``resolve-personal-notes-config.sh`` at run time instead.
    """

    CLAUDE_LOCAL_MD = Path("CLAUDE.local.md")
    """
    What session-start.sh writes the personal notes and plan state into.
    """

    GIT_IGNORE = Path(".gitignore")
    """
    Where ``CLAUDE.local.md`` is excluded, so notes can never be committed.
    """

    CLAUDE_SETTINGS = ProjectLocation.CLAUDE_CODE_DIRECTORY / "settings.json"
    """
    The committed settings registering the SessionStart hook.
    """


class ScrubbedEnvironmentPrefix(StrEnum):
    """
    Variables a scratch run must not inherit, by the prefix of their name.

    The session running this suite legitimately has all of them set, and every one of them
    changes what a hook resolves - so a test asserting the default resolution has to be run
    without them rather than around them.
    """

    PERSONAL_NOTES = "CLAUDE_PERSONAL_NOTES_"
    """
    The personal-notes remote, branch and path overrides.
    """

    GIT_AUTHOR = "GIT_AUTHOR_"
    """
    The commit author git would otherwise take from the configuration.
    """

    GIT_COMMITTER = "GIT_COMMITTER_"
    """
    The committer git would otherwise take from the configuration.
    """

    GITHUB_CLI_HOST = "GH_HOST"
    """
    The host the ``gh`` CLI lends a stored token for, which a real value could redirect.
    """


SCRUBBED_VARIABLE_PREFIXES = (*ScrubbedEnvironmentPrefix, *CREDENTIAL_VARIABLES)
"""
Everything stripped from a hook's environment before a test runs it: the families above,
and the GitHub credential variables the package reads, so a test never reaches GitHub with
whatever its caller has set. A whole variable name is its own prefix.
"""
