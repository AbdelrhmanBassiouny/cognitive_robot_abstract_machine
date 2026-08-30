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
from enum import IntEnum, StrEnum

REPORT_FIELD_SEPARATOR = "\t"
"""
What separates a report row's check, status and detail.
"""

REPORT_FIELD_COUNT = 3
"""
How many fields a report row carries, which is also what distinguishes one from the
ordinary output a caller may print around it.
"""


# %% the vocabulary a report is written in


class SetupCheck(StrEnum):
    """
    The checks check-setup.sh reports on, in the order it prints them.
    """

    TOOLING_FILES = "tooling_files"
    """
    Whether the files the dashboard skill runs are all present.
    """

    SESSION_START_HOOK = "session_start_hook"
    """
    Whether the committed settings register the SessionStart hook.
    """

    CLAUDE_LOCAL_MD_IGNORED = "claude_local_md_ignored"
    """
    Whether the notes file is excluded, so notes can never be committed.
    """

    NOTES_REMOTE = "notes_remote"
    """
    Which remote the notes resolve to, and what named it.
    """

    NOTES_REMOTE_URL = "notes_remote_url"
    """
    The URL that remote points at.
    """

    NOTES_BRANCH_NAME = "notes_branch_name"
    """
    Which branch the notes resolve to, and what named it.
    """

    NOTES_PATH = "notes_path"
    """
    Where on that branch the notes file is expected.
    """

    NOTES_BRANCH = "notes_branch"
    """
    Whether that branch exists on that remote.
    """

    NOTES_FILE = "notes_file"
    """
    Whether the notes file exists on it.
    """

    GIT_IDENTITY = "git_identity"
    """
    Whether this clone's commits are authored as the identity the notes branch records.
    """

    DASHBOARD_DEPENDENCIES = "dashboard_dependencies"
    """
    Whether the packages the dashboard builder imports are installed.
    """

    CLAUDE_LOCAL_MD = "claude_local_md"
    """
    Whether the SessionStart hook has written the notes into this clone.
    """


class CheckStatus(StrEnum):
    """
    The status a setup checker reports for a single check.
    """

    OK = "ok"
    """
    The check passed and there is nothing to do.
    """

    NEEDS_SETUP = "needs-setup"
    """
    Something is missing, and the row's detail says what fixes it.
    """

    INFORMATIONAL = "info"
    """
    Context rather than a verdict, so it never makes a run need setup.
    """


class ExitCode(IntEnum):
    """
    The status a setup checker exits with: its verdict on the clone as a whole.

    Both checkers set it by the same rule, so a run needs setup exactly when one of its
    rows does.
    """

    SET_UP = 0
    """
    Every check passed.
    """

    NEEDS_SETUP = 1
    """
    At least one check needs setup.
    """


# %% one parsed run


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

    exit_code: ExitCode
    """
    The script's verdict on the clone as a whole.
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

        Rows are picked out of the output rather than assumed to be all of it, since a
        setup script prints its own progress around the report it ends with. A row
        naming a check *checks* doesn't declare raises, so a newly added check has to be
        declared by the calling module rather than silently going unasserted.

        :param process: The finished subprocess, whose output carries the report.
        :param checks: The enum of checks the script under test reports on.
        :return: The parsed report.
        """
        results = {}
        for line in process.stdout.splitlines():
            fields = line.split(REPORT_FIELD_SEPARATOR)
            if len(fields) != REPORT_FIELD_COUNT:
                continue
            check, status, detail = fields
            results[checks(check)] = CheckResult(CheckStatus(status), detail)
        return cls(ExitCode(process.returncode), results)
