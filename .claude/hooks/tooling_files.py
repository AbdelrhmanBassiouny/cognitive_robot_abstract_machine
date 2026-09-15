"""
The names this repository's own tooling is written in, stated once: where its files live,
and the fixed tokens their contents are addressed by.

The Python half of ``resolve-personal-notes-config.sh``: the shell scripts resolve their
paths from that file, and everything written in Python - the hooks' own modules and the
tests that drive them - resolves the same names from here, so no caller spells one
itself.
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

    SETUP_STEPS = "setup_steps.py"
    """
    Prints the setup steps that live outside the clone - labels, access, environment
    variables - filled in for the fork the clone points at.
    """

    WRITE_BRANCH_FILES = "write-branch-files.sh"
    """
    Pushes several files to a branch in one commit, through a scratch worktree.
    """

    CHECK_STACK_SETUP = "check-stack-setup.sh"
    """
    Reports, read-only, whether a clone is set up for the stacked-pull-request workflow.
    """

    SETUP_STACKED_PRS = "setup-stacked-prs.sh"
    """
    Runs that workflow's whole first-time setup non-interactively.
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


class StackToolingFile(StrEnum):
    """
    The files check-stack-setup.sh's ``stack_tooling_files`` check requires, relative to
    the project root - and, being the canonical set, what a fork-overlay install writes.

    Stated here rather than read from ``resolve-personal-notes-config.sh``, for the same
    reason :class:`SetupPrerequisiteFile` is: a rename that breaks the check has to be
    made deliberately in both places rather than the two following each other silently.
    """

    STACK = ".claude/stack/stack.py"
    """
    The read-only tool the maintenance pass shells out to.
    """

    STACK_CONFIGURATION = ".claude/stack/stack.toml"
    """
    The committed configuration defaults a personal copy overrides.
    """

    STACK_README = ".claude/stack/README.md"
    """
    What the tooling is and how its pieces fit together.
    """

    MAINTENANCE_SKILL = ".claude/skills/stacked-pr-maintenance/SKILL.md"
    """
    The maintenance pass itself, invocable from any session.
    """

    MAINTENANCE_ROUTINE_PROMPT = (
        ".claude/skills/stacked-pr-maintenance/routine-prompt.md"
    )
    """
    The block registered as a scheduled Routine, which runs that skill.
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

    STACK_BOARD = ".claude/stack/board.json"
    """
    The maintenance pass's scratch snapshot of the open pull requests, which is
    gitignored rather than committed.
    """

    PERSONAL_STACK_CONFIGURATION = ".claude/personal/stack.toml"
    """
    Where the stack settings a contributor overrides live on the notes branch.
    """


# %% the prompt a scheduled maintenance run is registered as


MAINTENANCE_SKILL_INVOCATION = "/stacked-pr-maintenance"
"""
How the registered prompt names the maintenance skill it runs.

Mirrors the directory :attr:`StackToolingFile.MAINTENANCE_SKILL` sits in, which is what
a skill is invoked by.
"""


class RoutinePromptPlaceholder(StrEnum):
    """
    The tokens :attr:`StackToolingFile.MAINTENANCE_ROUTINE_PROMPT` carries for a setup
    run to substitute before the block is registered.

    One reaching a registered prompt unsubstituted becomes an instruction a live run
    cannot resolve, which is why what they are is stated rather than spelled at each
    site that checks for them.
    """

    FORK_REPOSITORY = "<FORK_REPOSITORY>"
    """
    The fork the stack is staged in.
    """

    UPSTREAM_REPOSITORY = "<UPSTREAM_REPOSITORY>"
    """
    The repository the stack is ultimately reviewed in.
    """
