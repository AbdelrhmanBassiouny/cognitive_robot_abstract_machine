"""
Reading check-setup.sh's report.

The script's tab-separated rows are its whole interface, so they are read back into the
check each row is about and the status it reports.
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
    """
    The package and the skill files a set-up clone carries.
    """

    SESSION_START_HOOK = "session_start_hook"
    """
    The SessionStart hook registered in the committed settings.
    """

    CLAUDE_LOCAL_MD_IGNORED = "claude_local_md_ignored"
    """
    ``CLAUDE.local.md`` excluded from commits.
    """

    NOTES_REMOTE = "notes_remote"
    """
    The remote the notes branch resolves to, and where that came from.
    """

    NOTES_REMOTE_URL = "notes_remote_url"
    """
    That remote's URL.
    """

    NOTES_BRANCH_NAME = "notes_branch_name"
    """
    The notes branch name, and where that came from.
    """

    NOTES_PATH = "notes_path"
    """
    The notes file's path on that branch, and where that came from.
    """

    NOTES_BRANCH = "notes_branch"
    """
    The notes branch existing on its remote.
    """

    NOTES_FILE = "notes_file"
    """
    The notes file existing on that branch.
    """

    GIT_IDENTITY = "git_identity"
    """
    The identity commits are authored with, against the recorded one.
    """

    DASHBOARD_DEPENDENCIES = "dashboard_dependencies"
    """
    Every dependency the package declares being installed.
    """

    CLAUDE_LOCAL_MD = "claude_local_md"
    """
    ``CLAUDE.local.md`` written by the SessionStart hook.
    """


class CheckStatus(StrEnum):
    """
    The status check-setup.sh reports for a single check.
    """

    OK = "ok"
    """
    Nothing to do.
    """

    NEEDS_SETUP = "needs-setup"
    """
    Something still has to be set up.
    """

    INFORMATIONAL = "info"
    """
    Context rather than a verdict.
    """


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
