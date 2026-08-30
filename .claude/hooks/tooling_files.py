"""
The names and locations of this repository's own tooling files, stated once.

The Python half of ``resolve-personal-notes-config.sh``: the shell scripts resolve their
paths from that file, and everything written in Python - the hooks' own modules and the
tests that drive them - resolves the same paths from here, so no caller spells a file
name itself.
"""

from __future__ import annotations

from enum import StrEnum

HOOKS_DIRECTORY = ".claude/hooks"
"""
Where this repository keeps the scripts that read and write personal-notes data.
"""

PLANS_DIRECTORY = ".claude/personal/plans"
"""
Where plans live on the personal-notes branch.

Mirrors ``PLANS_DIR`` in ``resolve-personal-notes-config.sh``, which is the shell half of
the same tooling; a test holds the two equal so the mirror cannot drift.
"""


# %% the scripts


class HookScript(StrEnum):
    """
    The scripts under ``.claude/hooks``, named once so a caller - a test installing one
    into a scratch layout, or a module invoking one - never spells a filename itself.
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
    Pushes a notes file's contents to that branch.
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

    PLAN_UPDATES_SINCE_SUPPORT = "plan_updates_since_support.py"
    """
    The Python that script calls for its tracking-issue half.
    """

    PLAN_MANIFEST_TOOLS = "plan_manifest_tools.py"
    """
    Reads manifests and regenerates the branch index.
    """

    PLAN_ITEM_BOOTSTRAP = "plan_item_bootstrap.py"
    """
    Records an item's manifest state and opens its branch and pull request.
    """

    PLAN_ITEM_MODE = "plan_item_mode.py"
    """
    Resolves and pins how the plan-item skills start work.
    """

    TOOLING_FILES = "tooling_files.py"
    """
    This module: the names and locations every other one resolves its paths from.
    """

    @property
    def path(self) -> str:
        """
        The script's path from the project root.
        """
        return f"{HOOKS_DIRECTORY}/{self.value}"


# %% the files a set up clone holds


class SetupPrerequisiteFile(StrEnum):
    """
    The files check-setup.sh's ``tooling_files`` check requires, relative to the project
    root.

    Stated here as well as in the fixture tree deliberately. A rename that breaks the
    check then has to be made in both places, rather than the fixture and the tests
    following each other silently and asserting nothing.
    """

    BUILD_DASHBOARD = ".claude/skills/plan-dashboard/build_dashboard.py"
    """
    The dashboard builder the plan-dashboard skill runs.
    """

    REFRESH_DASHBOARD = ".claude/skills/plan-dashboard/refresh_dashboard.sh"
    """
    The refresh entry point the same skill runs.
    """

    DASHBOARD_REQUIREMENTS = ".claude/skills/plan-dashboard/requirements.txt"
    """
    The requirements file check-setup.sh also derives the dependency check from.
    """

    PLAN_SCHEMA = ".claude/skills/plan-dashboard/plan-schema.md"
    """
    The manifest field reference.
    """


class ProjectFile(StrEnum):
    """
    The files in a clone that the hooks read, write or check, relative to the project
    root.

    Only the paths that are fixed conventions. Anything a contributor can redirect -
    the notes path among them - is resolved from
    ``resolve-personal-notes-config.sh`` at run time instead.
    """

    CLAUDE_LOCAL_MD = "CLAUDE.local.md"
    """
    What session-start.sh writes the personal notes and plan state into.
    """

    GIT_IGNORE = ".gitignore"
    """
    Where ``CLAUDE.local.md`` is excluded, so notes can never be committed.
    """

    CLAUDE_SETTINGS = ".claude/settings.json"
    """
    The committed settings registering the SessionStart hook.
    """

    PERSONAL_GIT_IDENTITY = ".claude/personal/git-identity"
    """
    The git identity recorded on the notes branch, in git-config format.
    """

    STARTER_NOTES = ".claude/skills/setup-personal-notes/starter-notes.md"
    """
    The template a new notes file can be seeded from.
    """
