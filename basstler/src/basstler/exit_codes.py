"""
The process statuses the plan-item tools exit with, each refusal its own.
"""

from __future__ import annotations

from enum import IntEnum

# %% plan item bootstrap


class PlanItemBootstrapExitCode(IntEnum):
    """
    The process statuses :mod:`basstler.plan_item_bootstrap` exits with.

    A distinct status per refusal lets a caller act on *which* failure happened without
    parsing stderr. ``argparse`` supplies 2 for a usage error.
    """

    SUCCESS = 0
    """
    The operation ran and printed its report.
    """

    UNKNOWN_PLAN = 3
    """
    No plan of that id is on the personal-notes branch.
    """

    UNKNOWN_ITEM = 4
    """
    The plan exists but tracks no item of that id, and too little was given to add one.
    """

    INCOMPLETE_NEW_ITEM = 5
    """
    Adding the item was asked for without every key a new entry must carry.
    """

    BRANCH_ALREADY_PUBLISHED = 6
    """
    The branch is already on the remote, so opening the work would adopt someone's.
    """

    PULL_REQUEST_DETAILS_MISSING = 7
    """
    Neither an existing pull request number nor the title and body to create one.
    """

    PULL_REQUEST_REFUSED = 8
    """
    GitHub rejected the creation; its own message says why.
    """

    @property
    def name_for_a_caller(self) -> str:
        """
        The status's own name, for a report a person or a script has to act on.

        Derived from the member rather than a table beside it, so a status can never
        carry a name belonging to a different one.
        """
        return self.name.lower()


# %% plan item mode


class PlanItemModeExitCode(IntEnum):
    """
    The process statuses :mod:`basstler.plan_item_mode` exits with.

    A distinct status per refusal lets a caller act on *which* failure happened without
    parsing stderr. The named refusals start at 3 because the two below them are already
    spoken for: 2 is the usage error ``argparse`` exits with, and 1 is what Python exits
    with on an uncaught exception, so leaving it free keeps a crash from reading as a
    refusal this tool chose to make.
    """

    SUCCESS = 0
    """
    The operation ran and printed its report.
    """

    USAGE = 2
    """
    No such subcommand, or the wrong arguments.

    Exited with by ``argparse`` itself, and named here so the value is reserved rather
    than merely unused.
    """

    UNKNOWN_MODE = 3
    """
    A mode was named that :class:`~basstler.plan_item_execution.ExecutionMode` does not
    define.
    """

    MALFORMED_MODE_SETTINGS = 4
    """
    A settings file exists but cannot be read as the modes it is supposed to hold.
    """

    SETTINGS_WRITE_REFUSED = 5
    """
    The personal settings file could not be pushed to the notes branch.
    """

    @property
    def name_for_a_caller(self) -> str:
        """
        The status as the lowercase name a report and a message both use.
        """
        return self.name.lower()
