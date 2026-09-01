"""
The reproduction tests a break is recorded as, and the block a passing one lifts.

Two branches can each pass their own checks, merge with no conflict at all, and fail
together. The branch that causes it is blocked with its own label, and nothing GitHub
reports can ever clear that label again: such a break never makes either pull request
conflicted, so the state that clears a base conflict says nothing here.

What does say something is the reproduction test pushed onto the breaking branch. It
carries a marker naming the branch it was broken against, a targeted job runs every
marked test and writes what each one did, and a branch whose reproductions all pass has
its block lifted. This module is that marker, that document, and that lifting; it is
also the ``pytest`` plugin the targeted job loads to write the document.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from maintenance_board import PullRequestField  # noqa: E402
from maintenance_github import ForkPullRequests  # noqa: E402
from stack import Configuration, DefaultLabel, LabelWrite  # noqa: E402

REPRODUCTION_MARKER = DefaultLabel.INTEGRATION_CONFLICT.replace("-", "_")
"""
The ``pytest`` marker a reproduction test carries, given the branch it was broken
against.

Derived from the label it clears rather than spelled a second time: a marker name is an
identifier and cannot carry the label's hyphen, and two independent spellings drifting
apart would leave a passing reproduction clearing nothing.
"""

REPRODUCTION_REPORT_DESTINATION = "reproduction_report"
"""
Where the option's value lands on a parsed ``pytest`` configuration.
"""

REPRODUCTION_REPORT_OPTION = f"--{REPRODUCTION_REPORT_DESTINATION.replace('_', '-')}"
"""
The option the targeted job names the document's destination with, derived from where
its value lands rather than spelled twice.
"""

CLEARED_COMMENT_PREFIX = "🟢 INTEGRATION - BREAK FIXED:"
"""
Opens the comment a lifted block is reported in, matching the prefix the block itself
arrived under so both ends of one branch's story read the same way.
"""


@dataclass
class ReproductionNamesNoBranchError(ValueError):
    """
    Raised when a reproduction test's marker names no branch.

    Without the branch, a passing reproduction says something is fixed but not whose,
    so there is nothing to clear.
    """

    test: str
    """The test whose marker was given no branch."""

    def __str__(self) -> str:
        """:return: What is missing, and where."""
        return (
            f"{self.test} is marked {REPRODUCTION_MARKER} but names no branch: mark it "
            f"@pytest.mark.{REPRODUCTION_MARKER}('<branch>')"
        )


class ReproductionReportKey(StrEnum):
    """
    The field names the run's document is read by.

    The job that runs the reproductions and the command that clears labels are separate
    processes, so these keys are the contract between them.
    """

    REPRODUCTIONS = "reproductions"
    """Every reproduction the run collected."""

    BRANCH = "branch"
    """The branch a reproduction was recorded against."""

    TEST = "test"
    """The reproduction test itself."""

    PASSED = "passed"
    """Whether it passed this time."""


# %% what a run of the reproductions found


@dataclass(frozen=True)
class ReproductionOutcome:
    """
    One reproduction test's result, and the branch whose break it reproduces.
    """

    branch: str
    """The branch the reproduction was recorded against."""

    test: str
    """The test's node identifier."""

    passed: bool
    """Whether it passed this time, which is what says the break is gone."""

    @classmethod
    def from_json(cls, document: dict[str, Any]) -> ReproductionOutcome:
        """
        :param document: One reproduction's object, as :meth:`to_json` wrote it.
        :return: The outcome it describes.
        """
        return cls(
            branch=document[ReproductionReportKey.BRANCH],
            test=document[ReproductionReportKey.TEST],
            passed=document[ReproductionReportKey.PASSED],
        )

    def to_json(self) -> dict[str, Any]:
        """:return: This outcome, keyed the way a reader parses it."""
        return {
            ReproductionReportKey.BRANCH: self.branch,
            ReproductionReportKey.TEST: self.test,
            ReproductionReportKey.PASSED: self.passed,
        }


@dataclass(frozen=True)
class RecordedBreak:
    """
    Every reproduction recorded against one branch, and whether they all pass now.
    """

    branch: str
    """The branch the reproductions were recorded against."""

    outcomes: tuple[ReproductionOutcome, ...]
    """What each of them did, in the order the run collected them."""

    @property
    def is_fixed(self) -> bool:
        """Whether every break recorded against this branch is gone.

        A branch can break more than one sibling and so collect a reproduction per
        break; clearing on the first passing one would lift the block while another
        recorded break still reproduces.

        :return: Whether the block on this branch can be lifted.
        """
        return all(outcome.passed for outcome in self.outcomes)


@dataclass(frozen=True)
class ReproductionRun:
    """
    What one run of the reproduction tests found, per branch.
    """

    outcomes: tuple[ReproductionOutcome, ...] = ()
    """Every reproduction the run collected, in collection order."""

    @property
    def breaks(self) -> tuple[RecordedBreak, ...]:
        """The reproductions grouped under the branch that carries their label.

        :return: One entry per branch a reproduction was recorded against.
        """
        grouped: dict[str, list[ReproductionOutcome]] = {}
        for outcome in self.outcomes:
            grouped.setdefault(outcome.branch, []).append(outcome)
        return tuple(
            RecordedBreak(branch=branch, outcomes=tuple(outcomes))
            for branch, outcomes in grouped.items()
        )

    @property
    def fixed_branches(self) -> tuple[str, ...]:
        """The branches whose every recorded break now passes.

        An empty run means nothing is recorded rather than everything is fixed, which
        is also what ``pytest``'s exit status 5 means when no reproduction is collected.

        :return: The branches whose block can be lifted.
        """
        return tuple(recorded.branch for recorded in self.breaks if recorded.is_fixed)

    @classmethod
    def from_json(cls, text: str) -> ReproductionRun:
        """
        :param text: The document, as :meth:`as_json` wrote it.
        :return: The run it describes.
        """
        document = json.loads(text)
        return cls(
            tuple(
                ReproductionOutcome.from_json(reproduction)
                for reproduction in document[ReproductionReportKey.REPRODUCTIONS]
            )
        )

    def as_json(self) -> str:
        """:return: This run, as the document a separate process reads it back from."""
        return json.dumps(
            {
                ReproductionReportKey.REPRODUCTIONS: [
                    outcome.to_json() for outcome in self.outcomes
                ]
            },
            indent=2,
        )


# %% lifting the block a fixed break leaves behind


@dataclass(frozen=True)
class ClearedBranchReport:
    """
    What lifting one branch's block wrote, and where.
    """

    branch: str
    """The branch whose block was lifted."""

    pull_request_number: int
    """The fork pull request that carries it."""

    label: str
    """The label that was removed."""

    comment: str
    """What was said on the pull request."""


def clearing_comment(branch: str) -> str:
    """Write the comment telling a branch's owner that its block is lifted.

    :param branch: The branch whose reproductions now pass.
    :return: The comment body.
    """
    return (
        f"{CLEARED_COMMENT_PREFIX} every test marked `{REPRODUCTION_MARKER}` against "
        f"`{branch}` passes, so the break it was blocked for is gone and the label is "
        f"removed.\n\nThis is the only evidence that can lift this block: the break was "
        f"between two branches that merge cleanly, so nothing about the merge ever said "
        f"it was there and nothing about the merge can say it is over."
    )


def clear_fixed_breaks(
    run: ReproductionRun, configuration: Configuration, fork: ForkPullRequests
) -> tuple[ClearedBranchReport, ...]:
    """Lift the block on every branch whose recorded breaks now pass.

    A branch that carries no block is left alone rather than written to: a reproduction
    keeps passing on every later run once the break is fixed, and re-clearing a label
    that is already gone would comment again each time.

    :param run: What the reproduction tests did.
    :param configuration: The resolved configuration, naming the label to remove.
    :param fork: The fork to label and comment on.
    :return: What was written where, one entry per branch actually unblocked.
    """
    label = configuration.integration_conflict_label
    blocked = _blocked_pull_requests_by_branch(fork, label)
    cleared: list[ClearedBranchReport] = []
    for branch in run.fixed_branches:
        number = blocked.get(branch)
        if number is None:
            continue
        pull_request = fork.pull_request(number)
        fork.replace_labels(
            number,
            LabelWrite.replacing(
                PullRequestField.LABELS.read(pull_request, number), removed=[label]
            ).labels,
        )
        comment = clearing_comment(branch)
        fork.add_comment(number, comment)
        cleared.append(
            ClearedBranchReport(
                branch=branch,
                pull_request_number=number,
                label=label,
                comment=comment,
            )
        )
    return tuple(cleared)


def _blocked_pull_requests_by_branch(
    fork: ForkPullRequests, label: str
) -> dict[str, int]:
    """Find the open pull request carrying the block, per branch.

    :param fork: The fork to read.
    :param label: The label that marks a branch as blocked.
    :return: The pull request number per blocked branch.
    """
    blocked: dict[str, int] = {}
    for record in fork.open_pull_requests():
        number = PullRequestField.NUMBER.read(record)
        if label in PullRequestField.LABELS.read(record, number):
            blocked[PullRequestField.HEAD.read(record, number)] = number
    return blocked


# %% the pytest plugin the targeted job loads


@dataclass
class ReproductionRecorder:
    """
    Collects what each reproduction test did, and writes the run's document.

    Registered as a plugin instance rather than reading and writing module state, so a
    run's collection belongs to that run.
    """

    report_path: Path
    """Where the run's document is written."""

    branches_by_test: dict[str, str] = field(default_factory=dict)
    """The branch each collected reproduction was recorded against, by node identifier."""

    passed_calls: set[str] = field(default_factory=set)
    """The reproductions whose own body ran and passed."""

    failed_phases: set[str] = field(default_factory=set)
    """The reproductions any phase of which failed, setup and teardown included."""

    def pytest_collection_modifyitems(self, items: Iterable[Any]) -> None:
        """Note which collected tests are reproductions, and of what.

        :param items: The collected tests.
        :raises ReproductionNamesNoBranchError: If a marker names no branch.
        """
        for item in items:
            marker = item.get_closest_marker(REPRODUCTION_MARKER)
            if marker is None:
                continue
            if not marker.args:
                raise ReproductionNamesNoBranchError(item.nodeid)
            self.branches_by_test[item.nodeid] = marker.args[0]

    def pytest_runtest_logreport(self, report: Any) -> None:
        """Record what one phase of one test did.

        :param report: The phase's result.
        """
        if report.nodeid not in self.branches_by_test:
            return
        if report.failed:
            self.failed_phases.add(report.nodeid)
        if report.when == "call" and report.passed:
            self.passed_calls.add(report.nodeid)

    def pytest_sessionfinish(self, session: Any, exitstatus: Any) -> None:
        """Write the run's document.

        :param session: The finished session.
        :param exitstatus: The status the run will exit with.
        """
        self.report_path.write_text(self.run().as_json())

    def run(self) -> ReproductionRun:
        """What the session found, as the document's model.

        A reproduction counts as passing only if its own body ran and passed and no
        phase of it failed, so one that was skipped or errored in setup leaves its
        branch blocked rather than clearing it on evidence that never ran.

        :return: The run.
        """
        return ReproductionRun(
            tuple(
                ReproductionOutcome(
                    branch=branch,
                    test=test,
                    passed=test in self.passed_calls and test not in self.failed_phases,
                )
                for test, branch in self.branches_by_test.items()
            )
        )


def pytest_addoption(parser: Any) -> None:
    """Declare where the run's document is written.

    :param parser: ``pytest``'s option parser.
    """
    parser.addoption(
        REPRODUCTION_REPORT_OPTION,
        default=None,
        help="write what each reproduction test did to this path",
    )


def pytest_configure(config: Any) -> None:
    """Start recording, when a destination for the document was named.

    :param config: The session's configuration.
    """
    destination = config.getoption(REPRODUCTION_REPORT_DESTINATION)
    if not destination:
        return
    config.pluginmanager.register(ReproductionRecorder(Path(destination)))
