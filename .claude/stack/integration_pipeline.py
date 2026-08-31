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

One run never reaches a verdict on the candidate it opened. What a candidate's checks
take was measured rather than assumed, and no job can outwait it - see
:class:`~integration_verdict.CandidateCheckTiming` - so a run opens a candidate and
stops, and the next run inherits and settles it.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from integration_constants import ReportKey  # noqa: E402
from integration_exit_codes import IntegrationExitCode  # noqa: E402
from integration_verdict import ChecksVerdict, VerdictReportKey  # noqa: E402
from tool_runner import (  # noqa: E402
    CommandLineFlag,
    CommandOutcome,
    IntegrationSubcommand,
    MaintenanceSubcommand,
    LOCALISATION_SCHEDULE,
    PollingSchedule,
    SubprocessToolRunner,
    ToolRunner,
    ToolingScript,
)

# %% the rebuild


A_BUILD_WAS_ASSEMBLED = frozenset(
    {IntegrationExitCode.SUCCESS, IntegrationExitCode.TIP_LEFT_OUT}
)
"""
The statuses that still leave a branch worth judging.

A tip left out is a collision to triage rather than a build that failed: what was
assembled is usable, it is simply not whole.
"""

BREAKS_ONE_REBUILD_BLOCKS = 5
"""
How many cross-branch breaks one rebuild blocks before leaving the rest to the next.

A budget rather than a measurement. Each round costs a restack, a merge and a whole
suite, so an unbounded one can spend the job's timeout on a stack broken in many places
and end with nothing to show; what a run blocked stands either way, and the next rebuild
carries on from those labels. A rebuild that has blocked five is also telling somebody
something they should read before it goes further.
"""


@dataclass(frozen=True)
class Candidate:
    """
    The pull request a build is being judged as.
    """

    number: str
    """
    Its number, as the command that reported it spelled it.
    """

    build_branch: str
    """
    The build it is judging.
    """

    head: str
    """
    The commit its checks are reported against.
    """

    @classmethod
    def from_json(cls, document: Mapping[str, Any]) -> Candidate:
        """:param document: What a command that reported a candidate printed.
        :return: The candidate it names."""
        return cls(
            number=str(document[VerdictReportKey.CANDIDATE]),
            build_branch=str(document[VerdictReportKey.BUILD_BRANCH]),
            head=str(document[VerdictReportKey.HEAD]),
        )


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
    One rebuild: settle whatever an earlier run left being judged, then bring the base
    forward and assemble the next build for the run after this one to settle.
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

    plans: tuple[str, ...] = ()
    """
    The plans this rebuild was asked to carry, empty when it carries all of them.

    A filtered rebuild answers one question - whether those plans hold together on their
    own - and answers it about a build that is deliberately not the whole of what is in
    flight. So it never settles the candidate the cycle left, and never publishes: the
    branch a developer works from is only ever moved onto a build carrying everything.
    """

    runner: ToolRunner = field(default_factory=SubprocessToolRunner)
    """
    How each command is run.
    """

    wait: Callable[[float], None] = time.sleep
    """
    How the rebuild waits between asking a question again.
    """

    localisation_schedule: PollingSchedule = LOCALISATION_SCHEDULE
    """
    How long to wait for a search's probes.
    """

    breaks_to_block: int = BREAKS_ONE_REBUILD_BLOCKS
    """
    How many cross-branch breaks to block before leaving the rest to the next rebuild.
    """

    def run(self) -> IntegrationExitCode:
        """
        Perform the rebuild.

        Success is this run having done its part rather than a build having been
        published: what a run can finish is settling what it inherited and leaving the
        next build being judged, and the checks it opened a candidate for start long
        after the run is over. A status other than success is one somebody has to look
        at.

        A rebuild asked for particular plans does neither of the two things that act on
        the whole of what is in flight - it settles no inherited candidate and publishes
        nothing - because the build it assembled is deliberately partial.

        An inherited candidate no run can judge is the one answer this carries on past
        rather than stopping on. Stopping is what wedged this pipeline permanently: the
        rebuild never reached the step that would have replaced the candidate, so every
        later run inherited the same unjudgeable one. It is closed and replaced instead,
        and the run still exits saying so, since a run that exited success over it would
        leave nobody to look at whatever is failing to start a check.

        :return: The status of whichever step decided the run.
        """
        self._take_down_unreferenced_builds()
        moved_past_an_unjudgeable_candidate = False
        if not self.plans:
            inherited = self._settle_what_is_already_being_judged()
            if inherited is IntegrationExitCode.CANDIDATE_UNCHECKED:
                moved_past_an_unjudgeable_candidate = True
            elif inherited is not None:
                return inherited
        if not self._fast_forward():
            return IntegrationExitCode.BASE_NOT_PREPARED
        assembled = self._build()
        if assembled.branch is None:
            return assembled.status
        if not self.plans:
            published = self._publish_recorded_pass(assembled.branch)
            if published is not None:
                return published
        if self._open_candidate(assembled.branch) is None:
            return IntegrationExitCode.GITHUB_REQUEST_FAILED
        if moved_past_an_unjudgeable_candidate:
            return IntegrationExitCode.CANDIDATE_UNCHECKED
        return IntegrationExitCode.SUCCESS

    def _take_down_unreferenced_builds(self) -> None:
        """
        Drop the builds earlier rebuilds left behind.

        Asked first, and its answer is not acted on: only publishing takes a build down
        on its own, so every other outcome leaves one, and a rebuild that stopped over
        tidying would leave the work it exists to do undone. What is still being judged
        has a pull request open against it, which is what keeps it.
        """
        self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS,
            CommandLineFlag.JSON,
        )

    def _settle_what_is_already_being_judged(self) -> IntegrationExitCode | None:
        """
        Read the candidate an earlier run left, and act on what its checks say.

        A run that assembled while one was open would open a second candidate against the
        same branch, so this is what the rebuild asks first. A candidate whose checks are
        still coming is left where it is rather than waited on: this run has nothing
        further it can do, and the next one inherits it.

        :return: The status to stop with, ``None`` when the run should carry on and
            assemble the next build, or
            :attr:`~integration_exit_codes.IntegrationExitCode.CANDIDATE_UNCHECKED` when
            it should carry on and still report that it moved past one nothing judged.
        """
        found = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.FIND_CANDIDATE,
            CommandLineFlag.JSON,
        )
        if IntegrationExitCode(found.status) is IntegrationExitCode.NO_CANDIDATE_OPEN:
            return None
        if found.status != IntegrationExitCode.SUCCESS:
            print(found.output, end="")
            return IntegrationExitCode.GITHUB_REQUEST_FAILED
        candidate = Candidate.from_json(found.document())
        return self._act_on(candidate, self._settle(candidate))

    def _act_on(
        self, candidate: Candidate, settled: CommandOutcome
    ) -> IntegrationExitCode | None:
        """
        Decide what one reading of an inherited candidate leaves the run to do.

        A candidate with no check at all is the one case this can call a fault rather
        than slowness: it has been open since at least the previous run, so whatever
        should have started one - the trigger, or the credential it was opened with - did
        not. Nothing is ever going to judge it, so it is closed here and the run goes on
        to assemble the build that replaces it; leaving it open is what left every later
        run inheriting the same one.

        :param candidate: The candidate that was read.
        :param settled: What reading its checks answered.
        :return: The status to stop with, ``None`` when the run should carry on, or
            :attr:`~integration_exit_codes.IntegrationExitCode.CANDIDATE_UNCHECKED` when
            it should carry on past one nothing judged and say so at the end.
        """
        status = IntegrationExitCode(settled.status)
        if status is IntegrationExitCode.CANDIDATE_STILL_RUNNING:
            if _reported_no_check(settled):
                print(
                    f"no check has been reported against candidate {candidate.number} "
                    "since before the previous rebuild, so nothing is starting one; "
                    "closing it and assembling the build that replaces it",
                    file=sys.stderr,
                )
                self._close(candidate)
                return IntegrationExitCode.CANDIDATE_UNCHECKED
            return IntegrationExitCode.SUCCESS
        if status is IntegrationExitCode.CANDIDATE_FAILED:
            self._localise(candidate)
            return status
        if status is not IntegrationExitCode.SUCCESS:
            print(settled.output, end="")
            return status
        return None

    def _close(self, candidate: Candidate) -> None:
        """
        Close a candidate nothing is ever going to judge.

        Its build's branch is left to the next rebuild's take-down, which drops whatever
        no open pull request refers to any more - so nothing here has to know how this
        run ends.

        :param candidate: The candidate to close.
        """
        self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.CLOSE_CANDIDATE,
            CommandLineFlag.CANDIDATE,
            candidate.number,
            CommandLineFlag.JSON,
        )

    def _settle(self, candidate: Candidate) -> CommandOutcome:
        """:param candidate: The candidate to read.
        :return: What reading its checks answered."""
        return self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.SETTLE_CANDIDATE,
            CommandLineFlag.CANDIDATE,
            candidate.number,
            CommandLineFlag.BUILD,
            candidate.build_branch,
            CommandLineFlag.HEAD,
            candidate.head,
            CommandLineFlag.JSON,
        )

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
        Assemble the branch, blocking each break the suite finds and assembling again
        without it.

        A suite that failed is two branches that each pass alone and break together -
        nothing GitHub reports finds that, so it is found here or not at all. The tree
        that failed is the one carrying the culprit, so there is nothing in it to carry
        on with; what this run can still make is the build without it, which is the one
        the next rebuild would have produced a cycle later. Ending the run instead spends
        a whole cycle, and however long its queue takes, per break.

        Each attempt reads the fork again, so the label the last one wrote is one this
        one sees - the same rule that says a write is computed from what a pull request
        carries now rather than from a snapshot taken before it moved.

        :return: What the last attempt answered, and the branch when it left one.
        """
        blocked_so_far = 0
        while True:
            assembled = self._assemble()
            status = IntegrationExitCode(assembled.status)
            if status is not IntegrationExitCode.TESTS_FAILED:
                return self._what_it_assembled(status, assembled)
            if blocked_so_far == self.breaks_to_block:
                return AssembledBuild(status=status)
            if self._block_the_branch_that_broke_it() is None:
                return AssembledBuild(status=status)
            blocked_so_far += 1

    def _assemble(self) -> CommandOutcome:
        """
        Assemble the branch once, and say what it holds.

        The document is printed whatever the attempt answered, because it is the only
        thing that names the branches the build left out - and a rebuild that published
        without ever having printed one left nobody able to say what the tree held.

        :return: What assembling answered.
        """
        assembled = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.BUILD,
            CommandLineFlag.RESTACK,
            *self._named_plans(),
            CommandLineFlag.JSON,
        )
        print(assembled.output, end="")
        return assembled

    @staticmethod
    def _what_it_assembled(
        status: IntegrationExitCode, assembled: CommandOutcome
    ) -> AssembledBuild:
        """:param status: What assembling answered.
        :param assembled: The attempt itself.
        :return: The branch it left, or nothing to judge."""
        if status not in A_BUILD_WAS_ASSEMBLED:
            return AssembledBuild(status=status)
        return AssembledBuild(
            status=status,
            branch=assembled.document()[VerdictReportKey.BUILD_BRANCH],
        )

    def _block_the_branch_that_broke_it(self) -> str | None:
        """
        Find the tip whose arrival turned the suite, and hold it out of later builds.

        Read through the key the block itself writes rather than through the verdict's,
        which has no name for it: a blocked branch is not a field of a verdict.

        A search that reached no pair is what stops the assembling: it leaves the same
        branches to merge, so another attempt would rebuild the same failing tree.

        :return: The branch that was blocked, or ``None`` when nothing could be blamed.
        """
        blocked = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.BLOCK_BRANCH,
            CommandLineFlag.JSON,
        )
        print(blocked.output, end="")
        if IntegrationExitCode(blocked.status) is not IntegrationExitCode.TESTS_FAILED:
            return None
        return str(blocked.document()[ReportKey.BLOCKED])

    def _publish_recorded_pass(self, build: str) -> IntegrationExitCode | None:
        """
        Publish the build outright if its tree is one already seen to pass.

        A rebuild assembles the same branches over the same base four times a day and
        nothing has usually moved, so most builds are byte-for-byte one already judged -
        and judging it again costs a matrix plus however long GitHub takes to start one.

        A build nothing has recorded is the ordinary answer and the run carries on to
        have it judged. Anything else stops the run: a build refused publication is one
        a candidate would spend a matrix to reach the same refusal about, and a
        publication that failed part-way is not a state to build a candidate on top of.

        :param build: The assembled branch.
        :return: The status to stop with, or ``None`` when the build still has to be
            judged.
        """
        published = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.PUBLISH_RECORDED_PASS,
            CommandLineFlag.BUILD,
            build,
            CommandLineFlag.JSON,
        )
        status = IntegrationExitCode(published.status)
        if status is IntegrationExitCode.NO_RECORDED_PASS:
            return None
        if status is not IntegrationExitCode.SUCCESS:
            print(published.output, end="")
        return status

    def _open_candidate(self, build: str) -> Candidate | None:
        """:param build: The assembled branch to get checked.
        :return: The pull request collecting its checks, or ``None`` when none opened.
        """
        opened = self.runner.run(
            ToolingScript.INTEGRATION,
            IntegrationSubcommand.OPEN_CANDIDATE,
            CommandLineFlag.BUILD,
            build,
            *self._named_plans(),
            CommandLineFlag.JSON,
        )
        if opened.status != IntegrationExitCode.SUCCESS:
            print(opened.output, end="")
            return None
        return Candidate.from_json(opened.document())

    def _named_plans(self) -> tuple[str, ...]:
        """:return: The plans as a command line names them, empty when unfiltered."""
        return tuple(
            argument
            for plan in self.plans
            for argument in (str(CommandLineFlag.PLAN), plan)
        )

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
