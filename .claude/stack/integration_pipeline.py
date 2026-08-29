"""
The rebuild a scheduled run performs, as one procedure rather than as shell.

Every step of it is a decision about a status: a build that left a tip out is still a
build, one whose suite failed is a collision to localise rather than a build, a candidate
whose checks have not finished is asked again rather than judged. Written in a job's
``run:`` block that is loops, ``if`` statements and exit-code literals in YAML - none of
which anything can run outside a runner, so none of which anything checks.

Here each of those is an ordinary branch in a tested procedure, and the workflow is
reduced to what only a runner can do: check a tree out, put an interpreter on the path,
install, and call this.

The individual commands are unchanged and still each answer one question and exit, so a
caller that does not want to wait need not; the waiting is this composition's, not
theirs.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from integration_exit_codes import IntegrationExitCode  # noqa: E402
from integration_verdict import ChecksVerdict, VerdictReportKey  # noqa: E402
from tool_runner import (  # noqa: E402
    CommandLineFlag,
    CommandOutcome,
    IntegrationSubcommand,
    MaintenanceSubcommand,
    LOCALISATION_SCHEDULE,
    VERDICT_SCHEDULE,
    PollingSchedule,
    SubprocessToolRunner,
    ToolRunner,
    ToolingScript,
)

# %% the rebuild


CHECKS_WARM_UP_ATTEMPTS = 5
"""
How many readings of a candidate may find no check at all before the rebuild stops
waiting for one.

GitHub creates a pull request's run within seconds of the request being opened, so on
the verdict schedule's interval this is minutes of nothing having started - long enough
that a queue is not mistaken for a trigger that never fired, and short enough that one
that never fired is not waited out for an hour.
"""

A_BUILD_WAS_ASSEMBLED = frozenset(
    {IntegrationExitCode.SUCCESS, IntegrationExitCode.TIP_LEFT_OUT}
)
"""
The statuses that still leave a branch worth judging.

A tip left out is a collision to triage rather than a build that failed: what was
assembled is usable, it is simply not whole.
"""


@dataclass(frozen=True)
class Candidate:
    """
    The pull request opened so a build collects checks.
    """

    number: str
    """
    Its number, as the command that opened it reported.
    """

    head: str
    """
    The commit its checks are reported against.
    """


@dataclass(frozen=True)
class AssembledBuild:
    """
    What assembling answered, and the branch it left when it left one.
    """

    status: IntegrationExitCode
    """
    The status the build command exited with.
    """

    branch: str | None = None
    """
    The branch assembled, or ``None`` when there is nothing to judge.
    """


@dataclass
class RefreshPipeline:
    """
    One rebuild: bring the base forward, assemble, get it checked, publish it if green,
    and localise it if not.
    """

    dispatch_on: str
    """
    The reference carrying this pipeline, which a probe's own run is dispatched on -
    never the tree under test, which carries no workflow of its own.
    """

    state_document: Path
    """
    Where the localisation keeps what it has established between calls.
    """

    runner: ToolRunner = field(default_factory=SubprocessToolRunner)
    """
    How each command is run.
    """

    wait: Callable[[float], None] = time.sleep
    """
    How the rebuild waits between asking a question again.
    """

    verdict_schedule: PollingSchedule = VERDICT_SCHEDULE
    """
    How long to wait for the candidate's checks.
    """

    warm_up_attempts: int = CHECKS_WARM_UP_ATTEMPTS
    """
    How many readings may find no check at all before the rebuild gives up on one.
    """

    localisation_schedule: PollingSchedule = LOCALISATION_SCHEDULE
    """
    How long to wait for a search's probes.
    """

    def run(self) -> IntegrationExitCode:
        """
        Perform the rebuild.

        :return: The status of whichever step decided the run - success only when a
            build was assembled, checked and published.
        """
        if not self._fast_forward():
            return IntegrationExitCode.BASE_NOT_PREPARED
        assembled = self._build()
        if assembled.branch is None:
            return assembled.status
        candidate = self._open_candidate(assembled.branch)
        if candidate is None:
            return IntegrationExitCode.GITHUB_REQUEST_FAILED
        verdict = self._await_verdict(assembled.branch, candidate)
        if verdict is IntegrationExitCode.CANDIDATE_FAILED:
            self._localise(candidate)
        return verdict

    def _fast_forward(self) -> bool:
        """
        Bring the fork's base onto the upstream the build is measured against.

        Answered as whether it worked rather than with the pass's own status: why it
        refused is the pass's to diagnose, and it has already said so on standard error.

        :return: Whether the base is now current.
        """
        return (
            self.runner.run(
                ToolingScript.MAINTENANCE, MaintenanceSubcommand.FAST_FORWARD
            ).status
            == IntegrationExitCode.SUCCESS
        )

    def _build(self) -> AssembledBuild:
        """
        Assemble the branch, and localise a suite that failed on the result.

        A suite that failed is two branches that each pass alone and break together -
        nothing GitHub reports finds that, so it is found here or not at all, and the tip
        that turned it is blocked so the next rebuild leaves it out.

        :return: What assembling answered, and the branch when it left one.
        """
        assembled = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.BUILD,
            CommandLineFlag.RESTACK,
            CommandLineFlag.JSON,
        )
        status = IntegrationExitCode(assembled.status)
        if status is IntegrationExitCode.TESTS_FAILED:
            self.runner.run(
                ToolingScript.INTEGRATION,
                IntegrationSubcommand.BLOCK_BRANCH,
                CommandLineFlag.JSON,
            )
            return AssembledBuild(status=status)
        if status not in A_BUILD_WAS_ASSEMBLED:
            print(assembled.output, end="")
            return AssembledBuild(status=status)
        return AssembledBuild(
            status=status,
            branch=assembled.document()[VerdictReportKey.BUILD_BRANCH],
        )

    def _open_candidate(self, build: str) -> Candidate | None:
        """:param build: The assembled branch to get checked.
        :return: The pull request collecting its checks, or ``None`` when none opened.
        """
        opened = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.OPEN_CANDIDATE,
            CommandLineFlag.BUILD,
            build,
            CommandLineFlag.JSON,
        )
        if opened.status != IntegrationExitCode.SUCCESS:
            print(opened.output, end="")
            return None
        document = opened.document()
        return Candidate(
            number=str(document[VerdictReportKey.CANDIDATE]),
            head=document[VerdictReportKey.HEAD],
        )

    def _await_verdict(self, build: str, candidate: Candidate) -> IntegrationExitCode:
        """
        Ask what the candidate's checks say until they have finished saying it.

        A candidate nothing has reported a check against is given a warm-up and then
        given up on rather than waited out: no run having been created is a different
        thing from a matrix taking its time, and spending the whole schedule on it ends
        the rebuild saying the checks were slow when none was ever started.

        :param build: The assembled branch under judgement.
        :param candidate: The pull request collecting the checks.
        :return: The verdict's own status.
        """
        settled = IntegrationExitCode.CANDIDATE_STILL_RUNNING
        for attempt, answer in enumerate(
            self._ask_repeatedly(
                self.verdict_schedule,
                ToolingScript.INTEGRATION,
                IntegrationSubcommand.SETTLE_CANDIDATE,
                CommandLineFlag.CANDIDATE,
                candidate.number,
                CommandLineFlag.BUILD,
                build,
                CommandLineFlag.HEAD,
                candidate.head,
                CommandLineFlag.JSON,
            )
        ):
            settled = IntegrationExitCode(answer.status)
            if settled is not IntegrationExitCode.CANDIDATE_STILL_RUNNING:
                return settled
            if attempt + 1 >= self.warm_up_attempts and _reported_no_check(answer):
                print(
                    "no check has been reported against the candidate in "
                    f"{self.warm_up_attempts} readings, so nothing is starting one",
                    file=sys.stderr,
                )
                return IntegrationExitCode.CANDIDATE_UNCHECKED
        print(
            "the candidate's checks had not finished in "
            f"{self.verdict_schedule.attempts} attempts",
            file=sys.stderr,
        )
        return settled

    def _localise(self, candidate: Candidate) -> None:
        """
        Find the branch a red candidate is about.

        A red names a failing check and nothing else, and the suite the build already ran
        cannot reproduce a matrix job's failure. Re-running that library over each prefix
        of the merge order is what names the tip whose arrival turned it, so the branch is
        blocked and the next rebuild is assembled without it.

        :param candidate: The pull request whose checks failed.
        """
        self._until_answered(
            self.localisation_schedule,
            IntegrationExitCode.PROBES_STILL_RUNNING,
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.LOCATE_CANDIDATE_FAILURE,
            CommandLineFlag.HEAD,
            candidate.head,
            CommandLineFlag.STATE,
            str(self.state_document),
            CommandLineFlag.DISPATCH_ON,
            self.dispatch_on,
            CommandLineFlag.JSON,
        )

    def _until_answered(
        self,
        schedule: PollingSchedule,
        not_yet: IntegrationExitCode,
        script: ToolingScript,
        subcommand: str,
        *arguments: str,
    ) -> IntegrationExitCode:
        """
        Run one command until it answers something other than *not yet*.

        :param schedule: How many times to ask, and how long to leave between.
        :param not_yet: The status meaning the answer is not ready.
        :param script: The entry point to run.
        :param subcommand: Which of its commands.
        :param arguments: What to pass it.
        :return: The last status it gave.
        """
        status = not_yet
        for answer in self._ask_repeatedly(schedule, script, subcommand, *arguments):
            status = IntegrationExitCode(answer.status)
            if status is not not_yet:
                return status
        return status

    def _ask_repeatedly(
        self,
        schedule: PollingSchedule,
        script: ToolingScript,
        subcommand: str,
        *arguments: str,
    ) -> Iterator[CommandOutcome]:
        """
        Run one command up to the schedule's attempts, and hand back each answer for
        the caller to judge.

        Nothing is waited out after an answer the caller acts on: the wait happens only
        when it comes back for another.

        :param schedule: How many times to ask, and how long to leave between.
        :param script: The entry point to run.
        :param subcommand: Which of its commands.
        :param arguments: What to pass it.
        :return: Each answer in turn.
        """
        for attempt in range(schedule.attempts):
            yield self.runner.run(script, subcommand, *arguments)
            if attempt + 1 < schedule.attempts:
                self.wait(schedule.interval_seconds)


def _reported_no_check(answer: CommandOutcome) -> bool:
    """
    :param answer: One reading of a candidate's checks.
    :return: Whether it found no check reported against it at all.
    """
    return answer.document().get(VerdictReportKey.VERDICT) == ChecksVerdict.ABSENT
