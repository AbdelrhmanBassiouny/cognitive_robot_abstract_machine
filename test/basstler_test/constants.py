"""
The paths and names more than one suite in this directory needs.

Anything :mod:`basstler` already names - a module, or a location in
:mod:`basstler.locations` - is not written down here: a suite imports it, so a rename
moves with the code instead of leaving a literal behind. What remains has no import to
derive it from: this directory's own dataset, the skill directories, the notes-branch
paths only the shell hooks name, and the names a scratch repository is built with.
"""

from __future__ import annotations

import re
from enum import IntEnum, StrEnum
from pathlib import Path

from basstler.locations import PathEnumeration, ProjectLocation
from basstler.setup_steps import PersonalNotesSetting


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

    UPSTREAM_REVIEW_RESPONSES = DIRECTORY / "upstream-review-responses"
    """
    The recorded GraphQL responses the upstream review reader is replayed against.
    """

    INSTALLED_DISTRIBUTIONS = DIRECTORY / "installed-distributions"
    """
    A directory that reads as installed distributions once it is on ``sys.path``, holding one
    whose name is spelled with every separator a distribution name may use.
    """

    UNINSTALLED_PROJECT = DIRECTORY / "uninstalled-project" / "pyproject.toml"
    """
    The metadata of a project no environment has installed, declaring no dependencies.
    """

    PARTLY_INSTALLED_PROJECT = DIRECTORY / "partly-installed-project" / "pyproject.toml"
    """
    A project declaring one dependency that is installed, then one that cannot be.
    """

    PLAN_WITH_LANDED_ITEMS = DIRECTORY / "plan-with-landed-items.yaml"
    """
    A plan with a tracking issue and three items: one landed, one in progress that
    depends on it, and one not started that depends on both.
    """

    PLAN_ALL_LANDED = DIRECTORY / "plan-all-landed.yaml"
    """
    A plan every item of which has landed.
    """

    ROADMAP_OF_STANDING_RULES = DIRECTORY / "roadmap-of-standing-rules.md"
    """
    A roadmap in the shape the limits accept, whose last entry wraps onto a second line.
    """

    ROADMAP_WITH_DATED_SECTION = DIRECTORY / "roadmap-with-dated-section.md"
    """
    A roadmap a session appended a dated section to.
    """

    PULL_REQUESTS_BY_BRANCH = DIRECTORY / "pull-requests-by-branch.json"
    """
    A recorded pull request listing, one pull request for each
    :class:`ProgressBranch` that has one.
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


class StackLabel(StrEnum):
    """
    The labels the workflow under test reads and writes, named once for every suite that
    puts one on a pull request.

    A label is written into a board entry, handed to a command and read back in an
    assertion, so a suite that spells it is holding the code to a name nothing else in
    the suite has to agree with.
    """

    IN_REVIEW = "in-review"
    """
    Carried by a branch that has reached the upstream review queue.
    """

    REBASE = "rebase"
    """
    Authorises rewriting a branch's published history rather than merging into it.
    """

    NEEDS_RESOLUTION = "needs-resolution"
    """
    Put on a branch whose owner has been asked to resolve a conflict.
    """

    BUG = "bug"
    """
    Carried by a fix, and never acted on by this tooling - a label it reads past.
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

    PERSONAL_NOTES = PersonalNotesSetting.BRANCH.default
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

    CLAUDE_LOCAL = Path("CLAUDE.local.md")
    """
    The private instructions the session-start hook writes into the clone.
    """

    GIT_IDENTITY = ProjectLocation.PERSONAL_NOTES / "git-identity"
    """
    The recorded git identity a clone with none of its own is given.
    """

    PULL_REQUEST_PROGRESS = ProjectLocation.PERSONAL_NOTES / "pr-progress"
    """
    The directory holding each pull request branch's progress notes, by branch name.
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


class ProjectTableKey(StrEnum):
    """
    The ``[project]`` keys the suites read that :class:`basstler.dependencies.PyprojectKey`
    does not name, since the package itself never reads them.
    """

    REQUIRES_PYTHON = "requires-python"
    """
    The version specifier an interpreter has to satisfy.
    """

    DYNAMIC = "dynamic"
    """
    The keys the build backend resolves rather than the table stating them.
    """


class ConfigurationVariable(StrEnum):
    """
    The variables of the shell configuration the tests read back, named once.
    """

    ENVIRONMENT_DIRECTORY = "BASSTLER_ENVIRONMENT_DIRECTORY"
    """
    The package's own environment.
    """

    PYTHON_REQUIREMENT = "BASSTLER_PYTHON_REQUIREMENT"
    """
    The interpreters the package supports.
    """

    INTERPRETER_CANDIDATES = "BASSTLER_INTERPRETER_CANDIDATES"
    """
    The supported interpreters looked for by name, separated by spaces.
    """

    UV_DIRECTORY = "BASSTLER_UV_DIRECTORY"
    """
    Where a session start installs ``uv`` when it finds neither ``uv`` nor a supported
    interpreter.
    """


class EnvironmentVariable(StrEnum):
    """
    The standard environment variables a test sets or reads for a subprocess.
    """

    EXECUTABLE_SEARCH_PATH = "PATH"
    """
    The directories a shell searches for a command.
    """

    IMPORT_PATH = "PYTHONPATH"
    """
    The directories an interpreter searches for imports ahead of its installed packages.
    """


class StubVariable(StrEnum):
    """
    The environment variables the stubs under ``dataset/stubs`` read.
    """

    PIP_CALL_LOG = "STUB_PIP_CALL_LOG"
    """
    The file the ``pip`` stub appends each invocation to.
    """

    PIP_STATUS = "STUB_PIP_STATUS"
    """
    The exit status the ``pip`` stub reports.
    """

    PIP_INSTALLED_UV = "STUB_PIP_INSTALLED_UV"
    """
    The script a ``uv`` installed by the ``pip`` stub runs.
    """

    UV_CALL_LOG = "STUB_UV_CALL_LOG"
    """
    The file the ``uv`` stub appends each invocation to.
    """

    UV_STATUS = "STUB_UV_STATUS"
    """
    The exit status the ``uv`` stub reports.
    """

    UV_PYTHON = "STUB_UV_PYTHON"
    """
    The interpreter an environment the ``uv`` stub creates runs.
    """


class PackageManager(StrEnum):
    """
    The executables the session start installs packages with, each named as it is on
    ``PATH`` and as its stub is under ``dataset/stubs``.
    """

    PIP = "pip"
    """
    The package installer every interpreter ships, used where there is no ``uv``.
    """

    UV = "uv"
    """
    The package manager that also creates environments and fetches interpreters.
    """


class FileMode(IntEnum):
    """
    The permission bits a test gives a file it writes.
    """

    EXECUTABLE = 0o755
    """
    Readable and runnable by everyone, writable by its owner.
    """


class ClaudeLocalSection(StrEnum):
    """
    The marked sections the shell hooks write into, and read back out of,
    :attr:`PersonalNotesPath.CLAUDE_LOCAL`.
    """

    PULL_REQUEST_PROGRESS = "PR-PROGRESS"
    """
    The current branch's pull request progress notes.
    """

    PLAN_ITEM = "PLAN-ITEM"
    """
    The plan item the current branch is tracked by.
    """

    PLAN_MANIFEST = "PLAN-MANIFEST"
    """
    A plan's manifest, as edited for :file:`save-plan.sh`.
    """

    PLAN_ROADMAP = "PLAN-ROADMAP"
    """
    A plan's roadmap, as edited for :file:`save-plan.sh`.
    """

    def around(self, content: str, label: str | None = None) -> str:
        """
        :param content: The section's content, ending in a newline.
        :param label: What the opening marker names after its colon, if anything.
        :return: *content* between this section's markers.
        """
        opening = self if label is None else f"{self}: {label}"
        return f"<!-- BEGIN-{opening} -->\n{content}<!-- END-{self} -->\n"

    def within(self, text: str) -> str:
        """
        :param text: A document holding this section once.
        :return: The section's content, without its markers.
        """
        pattern = rf"<!-- BEGIN-{self}(?:: [^>]*)? -->\n(.*?)<!-- END-{self} -->"
        return re.search(pattern, text, re.DOTALL).group(1)


class HookFile(StrEnum):
    """
    The hook scripts a suite runs that the package does not name.
    """

    SAVE_PULL_REQUEST_PROGRESS = "save-pr-progress.sh"
    """
    Saves the current branch's progress notes to the personal-notes branch.
    """


class SavePlanOption(StrEnum):
    """
    The options :file:`save-plan.sh` takes, which only the hook defines.
    """

    MANIFEST = "--manifest"
    """
    A file to read the manifest from, in place of CLAUDE.local.md's section.
    """

    ROADMAP = "--roadmap"
    """
    A file to read the roadmap from, in place of CLAUDE.local.md's section.
    """


class ProgressBranch(StrEnum):
    """
    The branches progress notes are kept for in the pruning suites, each standing for
    one state its pull request can be in. The ones with a pull request are those
    :attr:`DatasetLocation.PULL_REQUESTS_BY_BRANCH` records.
    """

    OPEN = "open-work"
    """
    Its pull request is open.
    """

    REOPENED = "reopened-work"
    """
    One pull request of it was closed, and a later one is open.
    """

    MERGED = "merged-work"
    """
    Its pull request merged.
    """

    DELETED = "claude/deleted-work"
    """
    Its pull request merged and the branch was deleted.
    """

    UNOPENED = "unopened-work"
    """
    It has no pull request yet.
    """
