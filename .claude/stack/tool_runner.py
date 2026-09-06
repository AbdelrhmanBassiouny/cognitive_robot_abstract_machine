"""
Running one of this repository's commands, and what a rebuild names them by.

Each command answers one question and exits, so a procedure composing them is a
procedure deciding on exit statuses - which is what this gives it a seam for, so the
deciding can be exercised without a fork, a runner or an hour of waiting.
"""

from __future__ import annotations

import json
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

STACK_DIRECTORY = Path(__file__).parent
"""
Where this repository's tooling lives, from this module's own location.
"""


class ToolingScript(StrEnum):
    """
    The entry points a rebuild drives.
    """

    INTEGRATION = "integration.py"
    """
    Builds, publishes and judges the integration branch.
    """

    MAINTENANCE = "maintenance.py"
    """
    Maintains the stack the build is assembled from.
    """

    @property
    def path(self) -> Path:
        """:return: The script itself."""
        return STACK_DIRECTORY / str(self)


class IntegrationSubcommand(StrEnum):
    """
    The commands a rebuild runs, in the order it runs them.

    Held to the commands that exist by a test rather than trusted, since a name here that
    names nothing would be a usage error at the far end of a runner.
    """

    TAKE_DOWN_UNREFERENCED_BUILDS = "take-down-unreferenced-builds"
    """
    Delete the build branches earlier rebuilds left with nothing judging them.
    """

    BUILD = "build"
    """
    Restack every stale tip and assemble the branch.
    """

    BLOCK_BRANCH = "block-branch"
    """
    Name the tip whose arrival turned the local suite, and block it.
    """

    PUBLISH_RECORDED_PASS = "publish-recorded-pass"
    """
    Publish a build whose tree has already been seen to pass, with no candidate at all.
    """

    OPEN_CANDIDATE = "open-candidate"
    """
    Publish the build and open the pull request that gets it checked.
    """

    FIND_CANDIDATE = "find-candidate"
    """
    Report the build already being judged, if one is.
    """

    SETTLE_CANDIDATE = "settle-candidate"
    """
    Read the candidate's checks and act on what they say.
    """

    CLOSE_CANDIDATE = "close-candidate"
    """
    Close a candidate nothing is ever going to report a check against, so the rebuild
    has something to replace rather than something to stop on.
    """

    LOCATE_CANDIDATE_FAILURE = "locate-candidate-failure"
    """
    Take one step of the search for the branch a red candidate is about.
    """


class MaintenanceSubcommand(StrEnum):
    """
    The maintenance commands a rebuild runs before assembling anything.
    """

    FAST_FORWARD = "fast-forward"
    """
    Bring the fork's base onto the upstream the build is measured against.
    """


class CommandLineFlag(StrEnum):
    """
    The flags a rebuild passes, spelled where they are passed rather than at each site.
    """

    JSON = "--json"
    """
    Ask for the machine-readable document rather than the rendered report.
    """

    RESTACK = "--restack"
    """
    Bring every stale tip forward before assembling.
    """

    REPORT_LEFT_OUT = "--report-left-out"
    """
    Comment on every branch a build leaves out, saying why.
    """

    BUILD = "--build"
    """
    Name the assembled branch a command is about.
    """

    CANDIDATE = "--candidate"
    """
    Name the pull request collecting the checks.
    """

    HEAD = "--head"
    """
    Name the commit the checks are reported against.
    """

    PLAN = "--plan"
    """
    Carry only the tips belonging to one plan.
    """

    STATE = "--state"
    """
    Where a repeatable search reads and rewrites what it has established.
    """

    DISPATCH_ON = "--dispatch-on"
    """
    The reference carrying the pipeline, which is what a probe is dispatched on.
    """


# %% running one command


@dataclass(frozen=True)
class CommandOutcome:
    """
    What one invocation of the tooling answered.
    """

    status: int
    """
    Its exit status, which is the decision it reached.
    """

    output: str
    """
    What it printed, which is its document when one was asked for.
    """

    def document(self) -> Mapping[str, Any]:
        """:return: The document it printed."""
        return json.loads(self.output)


class ToolRunner(ABC):
    """
    Runs one of this repository's commands and reports what it answered.

    A seam rather than a call, so the procedure above can be exercised without a fork, a
    runner or an hour of waiting.
    """

    @abstractmethod
    def run(
        self, script: ToolingScript, subcommand: str, *arguments: str
    ) -> CommandOutcome:
        """:param script: The entry point to run.
        :param subcommand: Which of its commands.
        :param arguments: What to pass it.
        :return: What it answered."""


@dataclass(frozen=True)
class SubprocessToolRunner(ToolRunner):
    """
    Runs each command as its own process, which is what makes every step's exit status
    the thing the next step decides on.

    Standard error is left to the caller's own, so what a command diagnoses reaches the
    run's log rather than being swallowed into a string nobody prints.
    """

    def run(
        self, script: ToolingScript, subcommand: str, *arguments: str
    ) -> CommandOutcome:
        """:param script: The entry point to run.
        :param subcommand: Which of its commands.
        :param arguments: What to pass it.
        :return: What it answered."""
        finished = subprocess.run(
            [sys.executable, str(script.path), subcommand, *arguments],
            stdout=subprocess.PIPE,
            text=True,
        )
        return CommandOutcome(status=finished.returncode, output=finished.stdout)


@dataclass(frozen=True)
class PollingSchedule:
    """
    How long a rebuild keeps asking a question whose answer is not ready.
    """

    attempts: int
    """
    How many times to ask before giving up on it ever answering.
    """

    interval_seconds: float
    """
    How long to wait between asking.
    """


LOCALISATION_SCHEDULE = PollingSchedule(attempts=180, interval_seconds=60)
"""
Three hours: a search is two rounds of probes, each a matrix run of its own, and every
probe of one round runs at once.
"""
