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

    STARTER_NOTES = DIRECTORY / "starter-notes.md"
    """
    The template ``setup-personal-notes.sh --starter-notes`` seeds a notes file from.
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


class RepositoryLabel(StrEnum):
    """
    Every label this repository's tooling applies to a pull request, named once for every
    suite that puts one on a pull request or checks that a repository carries it.

    Wider than :class:`basstler.build_dashboard.PullRequestLabel`, which is the subset the
    dashboard *interprets*; these are the ones something *applies*, and a fork wants each to
    exist with a description rather than turning up unexplained.

    Held equal to ``PULL_REQUEST_LABELS`` in ``resolve-personal-notes-config.sh``, which is
    where the shell reads them from, by
    :func:`test_github_api_sh.test_the_labels_match_the_ones_the_shell_declares`.
    """

    MERGED = "merged"
    """
    The changes landed even though GitHub never recorded a merge.
    """

    BUG = "bug"
    """
    Carried by a fix, and never acted on by the stack workflow - a label it reads past.
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

    PROMOTION_LINK_SENT = "cram2-link-sent"
    """
    Carries the link that opens its upstream pull request.

    The one member whose *value* names a particular upstream rather than what the label
    means - it mirrors :data:`basstler.maintenance_constants.PROMOTION_LINK_LABEL`, a plain
    constant where the three above it are configurable in ``basstler/stack.toml``.
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

    SETUP_PERSONAL_NOTES = (
        ProjectLocation.CLAUDE_CODE_DIRECTORY / "skills" / "setup-personal-notes"
    )
    """
    The first-time setup skill, which also ships the starter notes template.
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

    STARTER_NOTES = SkillDirectory.SETUP_PERSONAL_NOTES / "starter-notes.md"
    """
    The template a new notes file can be seeded from.
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


class GitHubCredentialVariable(StrEnum):
    """
    The GitHub credential variables a scratch run must not inherit.

    Whoever runs the tests may well have real ones set, and a test that reached GitHub with
    them would be neither reproducible nor safe.
    """

    GH_TOKEN = "GH_TOKEN"
    """
    The token ``gh`` reads first, and the fallback backend's own preference.
    """

    GITHUB_TOKEN = "GITHUB_TOKEN"
    """
    The token both fall back to.
    """

    GH_HOST = "GH_HOST"
    """
    The host ``gh`` would talk to, which a real value could redirect.
    """


SCRUBBED_VARIABLE_PREFIXES = (*ScrubbedEnvironmentPrefix, *GitHubCredentialVariable)
"""
Everything stripped from a hook's environment before a test runs it.

A whole variable name is its own prefix, so the credentials belong in the same tuple as
the families.
"""
