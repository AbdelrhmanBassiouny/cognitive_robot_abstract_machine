"""
The document a build hands back, and how it is rendered or acted on.

The status is derived from the report rather than decided beside it, so no two callers
can disagree about what a clean build was.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from integration_constants import ReportKey
from integration_exit_codes import IntegrationExitCode
from integration_tips import (
    PullRequestStackTipOutcome,
    ReadmittedBranch,
    ResolutionAuthor,
    TipStatus,
)


@dataclass(frozen=True)
class IntegrationReport:
    """
    One build: what reached the branch, what did not, and whether it works.
    """

    build_branch: str
    """
    The branch this build was assembled onto.
    """

    base: str
    """
    The upstream base it started from.
    """

    tips: tuple[PullRequestStackTipOutcome, ...] = ()
    """
    What became of each tip, in the order they were merged.
    """

    tests_passed: bool | None = None
    """Whether the configured suite passed, or ``None`` when it was not run - which a
    caller has to be able to tell from a suite that ran and passed."""

    left_out: tuple[PullRequestStackTipOutcome, ...] = ()
    """The branches the build never tried to merge - unreviewed, or blocked by a label.

    Kept apart from :attr:`tips` rather than filed among them: a tip left out is a build
    that did not do what it set out to, and one of these is the build doing exactly what
    it was asked to."""

    readmitted: tuple[ReadmittedBranch, ...] = ()
    """The branches carried although a label withholds them, because the tree their
    block was measured in is gone, and that reached the finished branch - so a suite
    that passed over it is what lifts their label."""

    def as_json(self) -> str:
        """:return: The build as one machine-readable document, led by its status."""
        status = exit_code_for(self)
        return json.dumps(
            {
                ReportKey.STATUS: status.name_for_a_caller,
                ReportKey.EXIT_CODE: int(status),
                **asdict(self),
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> IntegrationReport:
        """
        Read a build back out of the document it was written to.

        The status and exit code are not read: both are derived from what the build left
        behind, so a document claiming otherwise would be describing a different build.

        :param text: A document :meth:`as_json` wrote.
        :return: The build it describes.
        """
        document = json.loads(text)
        return cls(
            build_branch=document[ReportKey.BUILD_BRANCH],
            base=document[ReportKey.BASE],
            tips=tuple(
                PullRequestStackTipOutcome.from_json(outcome)
                for outcome in document[ReportKey.TIPS]
            ),
            tests_passed=document.get(ReportKey.TESTS_PASSED),
            left_out=tuple(
                PullRequestStackTipOutcome.from_json(outcome)
                for outcome in document[ReportKey.LEFT_OUT]
            ),
            readmitted=tuple(
                ReadmittedBranch.from_json(branch)
                for branch in document[ReportKey.READMITTED]
            ),
        )

    @property
    def tips_left_out(self) -> tuple[PullRequestStackTipOutcome, ...]:
        """:return: Every tip whose commits are not in the finished branch."""
        return tuple(outcome for outcome in self.tips if not outcome.is_integrated)

    @property
    def replayed_by_a_skill(self) -> tuple[PullRequestStackTipOutcome, ...]:
        """:return: Every tip whose merge replayed a machine-written resolution."""
        return tuple(
            outcome
            for outcome in self.tips
            if outcome.status is TipStatus.REPLAYED
            and outcome.resolved_by is ResolutionAuthor.SKILL
        )


def exit_code_for(report: IntegrationReport) -> IntegrationExitCode:
    """
    Decide one build's exit status from what it actually left behind.

    Shared by every command that produces a report, so none of them can disagree about
    what a clean build is. A tip silently missing, or a red suite reported as success,
    is exactly the kind of silence this exists to prevent - and the exit status is the
    only half a caller with no model in it reads.

    :param report: What the build did.
    :return: The process exit code.
    """
    if report.tests_passed is False:
        if report.replayed_by_a_skill:
            return IntegrationExitCode.SUSPECT_REPLAY
        return IntegrationExitCode.TESTS_FAILED
    if report.tips_left_out:
        return IntegrationExitCode.TIP_LEFT_OUT
    return IntegrationExitCode.SUCCESS


def print_build(report: IntegrationReport) -> None:
    """:param report: The build to summarise, one tab-separated line per tip."""
    print(f"{report.build_branch}\tbuilt-on\t{report.base}")
    for outcome in report.tips:
        detail = (
            ",".join(outcome.conflicting_paths)
            or outcome.explanation
            or (outcome.resolved_by or "")
        )
        collided = f" (with {outcome.attributed_to})" if outcome.attributed_to else ""
        print(f"{outcome.branch}\t{outcome.status}{collided}\t{detail}")
    for absent in report.left_out:
        beneath = f"under {absent.attributed_to}" if absent.attributed_to else "itself"
        print(f"{absent.branch}\t{absent.status}\t{beneath}")
    for carried_again in report.readmitted:
        print(
            f"{carried_again.branch}\treadmitted\t#{carried_again.pull_request_number}"
        )
    if report.tests_passed is not None:
        print(
            f"{report.build_branch}\ttests\t{'passed' if report.tests_passed else 'failed'}"
        )
