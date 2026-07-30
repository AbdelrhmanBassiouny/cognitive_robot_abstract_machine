"""
The tab-separated report both setup checkers print, parsed back into objects.

``check-setup.sh`` and ``check-stack-setup.sh`` share one output contract - a
``<check>\\t<status>\\t<detail>`` row per check, and an exit code that is 0 only when no
row needs setup - so their test modules share the parsing of it rather than each
carrying a copy. Which checks exist stays with each module: a report is keyed by
whatever check enum its own module declares.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import StrEnum


class CheckStatus(StrEnum):
    """
    The status a setup checker reports for a single check.
    """

    OK = "ok"
    NEEDS_SETUP = "needs-setup"
    INFORMATIONAL = "info"


@dataclass
class CheckResult:
    """
    What a setup checker reported for one check.
    """

    status: CheckStatus
    """
    Whether the check passed, needs setup, or is context rather than a verdict.
    """

    detail: str
    """
    The human-readable explanation printed alongside the status.
    """


@dataclass
class SetupReport:
    """
    One parsed run of a setup checker: what it reported, and how it exited.
    """

    exit_code: int
    """
    The script's exit code: 0 when nothing needs setup, 1 otherwise.
    """

    results: dict[StrEnum, CheckResult]
    """
    Every reported check, keyed by the check it reports on.
    """

    @classmethod
    def from_completed_process(
        cls, process: subprocess.CompletedProcess[str], checks: type[StrEnum]
    ) -> SetupReport:
        """
        Parse a finished checker run.

        Raises if a row names a check *checks* doesn't declare, so a newly added check
        has to be declared by the calling module rather than silently going unasserted.

        :param process: The finished subprocess.
        :param checks: The enum of checks the script under test reports on.
        :return: The parsed report.
        """
        results = {}
        for line in process.stdout.splitlines():
            check, status, detail = line.split("\t")
            results[checks(check)] = CheckResult(CheckStatus(status), detail)
        return cls(process.returncode, results)
