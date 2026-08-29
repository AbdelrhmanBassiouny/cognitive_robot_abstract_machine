"""
The candidate a build is judged as, and the branch a green one becomes.

A build is regenerated from scratch, so it shares no history with the branch it replaces
and there is nothing to merge: the pointer is moved to it, or it is thrown away. What
decides which is the repository's own checks, and those only run on a pull request - so
a candidate is opened to be judged and closed unmerged, never to be merged.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from maintenance_github import CandidatePullRequests, CheckRunRecord  # noqa: E402

CANDIDATE_TITLE_PREFIX = "Integration candidate:"
"""
Opens a candidate's title, so one is recognisable among the fork's pull requests.
"""


class CheckRunField(StrEnum):
    """
    The fields of a check run this module reads.
    """

    NAME = "name"
    """What the check is called."""

    STATUS = "status"
    """Whether it has finished."""

    CONCLUSION = "conclusion"
    """How it finished, absent until it has."""


class CheckRunStatus(StrEnum):
    """
    How far along a check run is, as the API reports it.
    """

    COMPLETED = "completed"
    """It has finished, so its conclusion is the one it will keep."""


class CheckRunConclusion(StrEnum):
    """
    How a finished check run turned out, as the API reports it.
    """

    SUCCESS = "success"
    """It passed."""

    SKIPPED = "skipped"
    """It was not run, which is not a failure of the tree it was asked about."""

    NEUTRAL = "neutral"
    """It reported without judging, which is likewise not a failure."""


PASSING_CONCLUSIONS = frozenset(
    {CheckRunConclusion.SUCCESS, CheckRunConclusion.SKIPPED, CheckRunConclusion.NEUTRAL}
)
"""
The conclusions that do not stand in the way of publishing a build.

A skipped or neutral check says nothing about the tree, so treating either as a failure
would hold every build behind a job that declined to run.
"""


class ChecksVerdict(StrEnum):
    """
    What the checks reported against one commit or branch amount to so far.
    """

    PASSED = "passed"
    """Every check finished and none of them failed."""

    FAILED = "failed"
    """A check finished badly, so this build is not one to hand anybody."""

    RUNNING = "running"
    """Not every check has finished, so there is nothing to act on yet."""

    ABSENT = "absent"
    """No check has been reported at all.

    Told apart from :attr:`RUNNING` because it is the one that can mean something is
    wrong rather than slow: a candidate opened by a credential whose pushes start no
    workflow run sits here forever rather than turning red."""

    @property
    def has_settled(self) -> bool:
        """Whether this is the verdict the checks will keep.

        :return: Whether the checks have said everything they are going to.
        """
        return self in SETTLED_VERDICTS


SETTLED_VERDICTS = frozenset({ChecksVerdict.PASSED, ChecksVerdict.FAILED})
"""
The verdicts a candidate is done collecting checks for.

Neither of the other two is: a candidate opened seconds ago has reported nothing yet, so
reading an absent check as an answer acts on a build nothing has judged.
"""


@dataclass(frozen=True)
class CheckRun:
    """
    One check reported against a candidate's head.
    """

    name: str
    """What the check is called, which is how a failure is named to a reader."""

    status: str
    """Whether it has finished."""

    conclusion: str | None
    """How it finished, absent until it has."""

    @classmethod
    def from_json(cls, record: CheckRunRecord) -> CheckRun:
        """
        :param record: One check run, as the API answers it.
        :return: The check run it describes.
        """
        return cls(
            name=str(record[CheckRunField.NAME]),
            status=str(record[CheckRunField.STATUS]),
            conclusion=(
                None
                if record.get(CheckRunField.CONCLUSION) is None
                else str(record[CheckRunField.CONCLUSION])
            ),
        )

    @property
    def has_finished(self) -> bool:
        """:return: Whether its conclusion is the one it will keep."""
        return self.status == CheckRunStatus.COMPLETED

    @property
    def stands_in_the_way(self) -> bool:
        """:return: Whether it is a finished check that failed."""
        return self.has_finished and self.conclusion not in PASSING_CONCLUSIONS


@dataclass(frozen=True)
class ReportedChecks:
    """
    Every check reported against one commit or branch, and what they amount to.
    """

    runs: tuple[CheckRun, ...]
    """The checks, in the order the API reported them."""

    @classmethod
    def of(cls, records: list[CheckRunRecord]) -> ReportedChecks:
        """
        :param records: The check runs, as the API answers them.
        :return: The checks they make up.
        """
        return cls(tuple(CheckRun.from_json(record) for record in records))

    @property
    def failed(self) -> tuple[CheckRun, ...]:
        """:return: Every finished check that failed, which is what a reader is told."""
        return tuple(run for run in self.runs if run.stands_in_the_way)

    @property
    def verdict(self) -> ChecksVerdict:
        """The verdict so far.

        A failure is answered as soon as it is seen rather than once everything has
        finished: the build is not publishable either way, and waiting out a matrix to
        say so costs the time the whole candidate exists to save.

        :return: What the checks amount to.
        """
        if not self.runs:
            return ChecksVerdict.ABSENT
        if self.failed:
            return ChecksVerdict.FAILED
        if not all(run.has_finished for run in self.runs):
            return ChecksVerdict.RUNNING
        return ChecksVerdict.PASSED


# %% the candidate itself


@dataclass(frozen=True)
class Candidate:
    """
    A pull request opened so that a build is judged, and closed once it has been.
    """

    number: int
    """The pull request's number."""

    build_branch: str
    """The build it names."""

    head: str
    """The commit its checks are reported against."""


def candidate_title(build_branch: str) -> str:
    """
    :param build_branch: The build to be judged.
    :return: The candidate's title.
    """
    return f"{CANDIDATE_TITLE_PREFIX} {build_branch}"


def candidate_description(build_branch: str, base: str) -> str:
    """Write what the candidate is for, since a reader meets it as an ordinary pull
    request and it is not one.

    :param build_branch: The build to be judged.
    :param base: The branch the build would replace.
    :return: The description.
    """
    return (
        f"Opened so that this repository's own checks run over `{build_branch}`, which "
        f"is a build of the upstream base plus every reviewed, unblocked branch in "
        f"flight.\n\n"
        f"**Not for review, and never merged.** A build is regenerated from scratch, so "
        f"it shares no history with `{base}` and there is nothing here to merge: if the "
        f"checks pass, `{base}` is moved to this commit and this pull request is closed "
        f"unmerged; if they fail, it is closed and the branches that broke it are the "
        f"ones to act on."
    )


def open_candidate(
    fork: CandidatePullRequests, build_branch: str, base: str, head: str
) -> Candidate:
    """Open the pull request that gets the build judged.

    :param fork: The fork to open it on.
    :param build_branch: The build to be judged, already published.
    :param base: The branch the build would replace.
    :param head: The build's head commit.
    :return: The candidate.
    """
    number = fork.open_pull_request(
        title=candidate_title(build_branch),
        head=build_branch,
        base=base,
        body=candidate_description(build_branch, base),
    )
    return Candidate(number=number, build_branch=build_branch, head=head)


def read_checks(fork: CandidatePullRequests, reference: str) -> ReportedChecks:
    """
    :param fork: The fork to read.
    :param reference: The commit or branch to read the checks reported against.
    :return: What they say so far.
    """
    return ReportedChecks.of(fork.check_runs(reference))


# %% what a run of it reports


class VerdictReportKey(StrEnum):
    """
    The field names the verdict's document is read by.
    """

    VERDICT = "verdict"
    """What the checks amount to."""

    CANDIDATE = "candidate"
    """The pull request opened to collect them."""

    BUILD_BRANCH = "build_branch"
    """The build being judged."""

    HEAD = "head"
    """The commit the checks are reported against."""

    FAILED_CHECKS = "failed_checks"
    """Every finished check that failed, by name."""

    PUBLISHED = "published"
    """Whether the base branch was moved to this build."""


@dataclass(frozen=True)
class VerdictReport:
    """
    What one judging of a candidate found, and what was done about it.
    """

    candidate: Candidate
    """The pull request that collected the checks."""

    checks: ReportedChecks
    """What they said."""

    published: bool
    """Whether the base branch was moved to this build."""

    def to_json(self) -> dict[str, Any]:
        """:return: This verdict, keyed the way a reader parses it."""
        return {
            VerdictReportKey.VERDICT: str(self.checks.verdict),
            VerdictReportKey.CANDIDATE: self.candidate.number,
            VerdictReportKey.BUILD_BRANCH: self.candidate.build_branch,
            VerdictReportKey.HEAD: self.candidate.head,
            VerdictReportKey.FAILED_CHECKS: [run.name for run in self.checks.failed],
            VerdictReportKey.PUBLISHED: self.published,
        }
