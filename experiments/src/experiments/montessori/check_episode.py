"""
Check recorded episodes: whether each one's rows and files are there and read back,
whether what its trials recorded makes sense, and how its answers scored.

Which episodes are checked is chosen on the command line: named by identifier, the
newest few, or every one recorded on the robot. The report of each is printed, and the
process exits non-zero if any check failed.
"""

from __future__ import annotations

import argparse
import sys
from enum import StrEnum

from typing_extensions import List, Optional, Sequence

from experiments.episodes.audit import EpisodeAudit, EpisodeAuditReport, Verdict
from experiments.montessori.results_database import (
    ResultsDatabase,
    configured_database_uri,
)

# %% what the command line offers


class CheckOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    EPISODE = "--episode"
    LATEST = "--latest"
    REAL = "--real"
    DATABASE_URI = "--database-uri"


SOUND_EXIT_CODE = 0
"""
What the process exits with when no check failed.
"""

FAILED_EXIT_CODE = 1
"""
What the process exits with when a check of any episode failed.
"""


def parse_arguments(
    argument_list: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
    """
    Read which episodes are to be checked off the command line.

    :param argument_list: Arguments to read; the process's own when omitted.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        CheckOption.EPISODE,
        nargs="+",
        default=[],
        help="identifiers of the episodes to check",
    )
    parser.add_argument(
        CheckOption.LATEST,
        type=int,
        default=None,
        help="check the newest episodes, this many of them",
    )
    parser.add_argument(
        CheckOption.REAL,
        action="store_true",
        help="check only episodes recorded on the robot; alone, all of them",
    )
    parser.add_argument(CheckOption.DATABASE_URI, default=None)
    return parser.parse_args(argument_list)


def chosen_identifiers(audit: EpisodeAudit, parsed: argparse.Namespace) -> List[str]:
    """
    The episodes the command line picks out.

    :param audit: What knows which episodes are recorded.
    :param parsed: The command line as read.
    """
    if parsed.episode:
        return list(parsed.episode)
    if parsed.latest is None and not parsed.real:
        return audit.recorded_identifiers(newest=1)
    return audit.recorded_identifiers(real_only=parsed.real, newest=parsed.latest)


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Check the chosen episodes and print a report of each.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 when no check failed, 1 otherwise.
    """
    parsed = parse_arguments(argument_list)
    uri = (
        configured_database_uri()
        if parsed.database_uri is None
        else parsed.database_uri
    )
    audit = EpisodeAudit(results_database=ResultsDatabase(uri=uri))
    reports: List[EpisodeAuditReport] = []
    for identifier in chosen_identifiers(audit, parsed):
        report = audit.audit(identifier)
        print(report.render(), flush=True)
        reports.append(report)
    if any(report.verdict is Verdict.FAILED for report in reports):
        return FAILED_EXIT_CODE
    return SOUND_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
