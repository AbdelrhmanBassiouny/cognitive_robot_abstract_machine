"""
Reading check-setup.sh's report back in a test.

The script's tab-separated rows are its whole interface, and more than one test module
asserts against them - check-setup.sh's own, and setup-personal-notes.sh's, which
finishes by printing the same report. Both the vocabulary and the parsing live here so
neither is written out twice.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import StrEnum

REPORT_FIELD_SEPARATOR = "\t"
"""
What separates a report row's check, status and detail.
"""

REPORT_FIELD_COUNT = 3
"""
How many fields a report row carries, which is also what distinguishes one from the
ordinary output a caller may print around it.
"""


class SetupCheck(StrEnum):
    """
    The checks check-setup.sh reports on, in the order it prints them.
    """

    TOOLING_FILES = "tooling_files"
    SESSION_START_HOOK = "session_start_hook"
    CLAUDE_LOCAL_MD_IGNORED = "claude_local_md_ignored"
    NOTES_REMOTE = "notes_remote"
    NOTES_REMOTE_URL = "notes_remote_url"
    NOTES_BRANCH_NAME = "notes_branch_name"
    NOTES_PATH = "notes_path"
    NOTES_BRANCH = "notes_branch"
    NOTES_FILE = "notes_file"
    GIT_IDENTITY = "git_identity"
    DASHBOARD_DEPENDENCIES = "dashboard_dependencies"
    CLAUDE_LOCAL_MD = "claude_local_md"


class CheckStatus(StrEnum):
    """
    The status check-setup.sh reports for a single check.
    """

    OK = "ok"
    NEEDS_SETUP = "needs-setup"
    INFORMATIONAL = "info"


@dataclass
class CheckResult:
    """
    What check-setup.sh reported for one check.
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
    One parsed run of check-setup.sh: what it reported, and how it exited.
    """

    exit_code: int
    """
    The script's exit code: 0 when nothing needs setup, 1 otherwise.
    """

    results: dict[SetupCheck, CheckResult]
    """
    Every reported check, keyed by the check it reports on.
    """

    @classmethod
    def from_completed_process(
        cls, process: subprocess.CompletedProcess[str]
    ) -> SetupReport:
        """
        Parse the report rows out of a finished run.

        Rows are picked out of the output rather than assumed to be all of it, since
        setup-personal-notes.sh prints its own progress around the report it ends with.
        A row naming a check this module doesn't know about raises, so a new check has
        to be declared here rather than silently going unasserted.

        :param process: The finished subprocess, whose output carries the report.
        :return: The parsed report.
        """
        results = {}
        for line in process.stdout.splitlines():
            fields = line.split(REPORT_FIELD_SEPARATOR)
            if len(fields) != REPORT_FIELD_COUNT:
                continue
            check, status, detail = fields
            results[SetupCheck(check)] = CheckResult(CheckStatus(status), detail)
        return cls(process.returncode, results)
