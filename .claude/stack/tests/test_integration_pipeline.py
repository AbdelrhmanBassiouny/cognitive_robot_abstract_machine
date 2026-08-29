"""
The rebuild the scheduled job performs, and what is left of the job that calls it.

Every decision the rebuild makes is a decision about an exit status. Written in a job's
``run:`` block those were loops, ``if`` statements and exit-code literals in YAML, which
nothing can run outside a runner and so nothing checked. Here they are ordinary branches
in a procedure, exercised through a runner that answers with the statuses a real one
would.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from command_line import commands_of

import integration_constants
import integration_pipeline_commands
from integration_run import IntegrationCommand
from integration_exit_codes import IntegrationExitCode
from integration_pipeline import A_BUILD_WAS_ASSEMBLED, RefreshPipeline
from tool_runner import (
    CommandLineFlag,
    CommandOutcome,
    IntegrationSubcommand,
    MaintenanceSubcommand,
    PollingSchedule,
    ToolRunner,
    ToolingScript,
)
from integration_verdict import ChecksVerdict, VerdictReportKey

A_BUILD_BRANCH = "integration-20260829-120000"
"""
The branch one rebuild assembled.
"""

A_CANDIDATE = 7
"""
The pull request opened so that build collects checks.
"""

A_HEAD = "0123456789abcdef"
"""
The commit the candidate's checks are reported against.
"""

QUICKLY = PollingSchedule(attempts=3, interval_seconds=0)
"""
A schedule short enough that a test giving up is a test that finished.
"""

A_SHORT_WARM_UP = 2
"""
How long a test lets a candidate answer nothing at all for, kept under
:data:`QUICKLY`'s attempts so that giving up on one is told apart from running out of
them.
"""


@dataclass
class RecordingRunner(ToolRunner):
    """
    A runner answering with prepared outcomes and recording what it was asked to run.
    """

    answers: list[CommandOutcome] = field(default_factory=list)
    """
    What to answer, in order; the last is repeated once the rest are spent.
    """

    invoked: list[tuple[str, ...]] = field(default_factory=list)
    """
    Every command run on it, as its script, subcommand and arguments.
    """

    def run(
        self, script: ToolingScript, subcommand: str, *arguments: str
    ) -> CommandOutcome:
        """:param script: The entry point run.
        :param subcommand: Which of its commands.
        :param arguments: What it was passed.
        :return: The next prepared outcome."""
        self.invoked.append((str(script), str(subcommand), *map(str, arguments)))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]

    @property
    def subcommands(self) -> list[str]:
        """:return: What was run, in order."""
        return [invocation[1] for invocation in self.invoked]


def succeeded(document: dict | None = None) -> CommandOutcome:
    """:param document: What the command printed, when it printed one.
    :return: One successful invocation."""
    return CommandOutcome(
        status=IntegrationExitCode.SUCCESS, output=json.dumps(document or {})
    )


def answered(status: IntegrationExitCode, document: dict | None = None):
    """:param status: What the command exited with.
    :param document: What it printed.
    :return: One finished invocation."""
    return CommandOutcome(status=int(status), output=json.dumps(document or {}))


def a_build(status: IntegrationExitCode = IntegrationExitCode.SUCCESS):
    """:param status: What assembling answered.
    :return: One build's outcome, naming the branch it left."""
    return answered(status, {VerdictReportKey.BUILD_BRANCH: A_BUILD_BRANCH})


def a_settling(verdict: ChecksVerdict, status: IntegrationExitCode) -> CommandOutcome:
    """:param verdict: What the candidate's checks amounted to.
    :param status: What reading them exited with.
    :return: One reading of the candidate's checks."""
    return answered(status, {VerdictReportKey.VERDICT: str(verdict)})


def an_open_candidate() -> CommandOutcome:
    """:return: One candidate's outcome, naming the pull request and the commit."""
    return succeeded(
        {
            VerdictReportKey.CANDIDATE: A_CANDIDATE,
            VerdictReportKey.HEAD: A_HEAD,
        }
    )


def rebuild(*answers: CommandOutcome, tmp_path: Path) -> tuple:
    """
    :param answers: What each command in turn answers.
    :param tmp_path: Where the localisation would keep its state.
    :return: The status the rebuild reached, and the runner that recorded it.
    """
    runner = RecordingRunner(answers=list(answers))
    status = RefreshPipeline(
        dispatch_on="integration",
        state_document=tmp_path / "localisation.json",
        runner=runner,
        wait=lambda seconds: None,
        verdict_schedule=QUICKLY,
        warm_up_attempts=A_SHORT_WARM_UP,
        localisation_schedule=QUICKLY,
    ).run()
    return status, runner


# %% the commands a rebuild names


@pytest.mark.parametrize("named", list(IntegrationSubcommand))
def test_every_command_a_rebuild_runs_is_one_the_builder_answers_to(
    named: IntegrationSubcommand,
):
    """
    Spelled here and implemented there, so a name that names nothing is a usage error at
    the far end of a runner - after the base has been fast-forwarded and a branch built.
    """
    assert str(named) in {
        command.invoked_as for command in commands_of(IntegrationCommand)
    }


def test_the_rebuild_itself_is_one_of_those_commands():
    """
    The workflow calls one thing, so a rebuild that is not a command of the builder is a
    workflow calling something that does not exist.
    """
    assert integration_pipeline_commands.RefreshCommand().invoked_as in {
        command.invoked_as for command in commands_of(IntegrationCommand)
    }


@pytest.mark.parametrize(
    "read",
    [VerdictReportKey.BUILD_BRANCH, VerdictReportKey.CANDIDATE, VerdictReportKey.HEAD],
)
def test_the_rebuild_reads_each_document_by_the_key_the_command_writes(
    read: VerdictReportKey,
):
    """
    The steps hand each other a build branch, a candidate number and a head through the
    documents the commands print - and the writer keys them through its own report while
    the rebuild reads them through the verdict's. Spelled differently in either, the
    hand-off breaks between two commands rather than inside one.
    """
    assert str(read) in {str(written) for written in integration_constants.ReportKey}


# %% what a rebuild does with each answer


def test_a_green_rebuild_publishes_without_localising_anything(tmp_path: Path):
    """
    Nothing failed, so there is no branch to look for - and a search costs a round of
    matrix runs per prefix.
    """
    status, runner = rebuild(
        succeeded(), a_build(), an_open_candidate(), succeeded(), tmp_path=tmp_path
    )

    assert status is IntegrationExitCode.SUCCESS
    assert runner.subcommands == [
        str(MaintenanceSubcommand.FAST_FORWARD),
        str(IntegrationSubcommand.BUILD),
        str(IntegrationSubcommand.OPEN_CANDIDATE),
        str(IntegrationSubcommand.SETTLE_CANDIDATE),
    ]


def test_a_base_that_would_not_come_forward_stops_before_anything_is_assembled(
    tmp_path: Path,
):
    """
    A build measured against a stale base is a build nobody asked for, and every later
    step would be about it.
    """
    status, runner = rebuild(
        answered(IntegrationExitCode.GIT_COMMAND_FAILED), tmp_path=tmp_path
    )

    assert status is IntegrationExitCode.BASE_NOT_PREPARED
    assert runner.subcommands == [str(MaintenanceSubcommand.FAST_FORWARD)]


def test_a_tip_left_out_is_still_a_build_worth_judging(tmp_path: Path):
    """
    A collision to triage rather than a build that failed: what was assembled is usable,
    it is simply not whole - so it is still published if its checks pass.
    """
    status, runner = rebuild(
        succeeded(),
        a_build(IntegrationExitCode.TIP_LEFT_OUT),
        an_open_candidate(),
        succeeded(),
        tmp_path=tmp_path,
    )

    assert IntegrationExitCode.TIP_LEFT_OUT in A_BUILD_WAS_ASSEMBLED
    assert status is IntegrationExitCode.SUCCESS
    assert str(IntegrationSubcommand.OPEN_CANDIDATE) in runner.subcommands


def test_a_suite_that_failed_on_the_build_blocks_the_tip_that_turned_it(
    tmp_path: Path,
):
    """
    Two branches that each pass alone, merge cleanly and break together. Nothing GitHub
    reports finds that, so it is found here or not at all - and a break nobody acts on is
    carried by every later build.
    """
    status, runner = rebuild(
        succeeded(),
        a_build(IntegrationExitCode.TESTS_FAILED),
        succeeded(),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.TESTS_FAILED
    assert runner.subcommands == [
        str(MaintenanceSubcommand.FAST_FORWARD),
        str(IntegrationSubcommand.BUILD),
        str(IntegrationSubcommand.BLOCK_BRANCH),
    ]


def test_a_red_candidate_is_localised_rather_than_left_naming_a_check(tmp_path: Path):
    """
    A red names a failing job, and a job name is not a branch. Without this the same red
    repeats on every rebuild with nobody told which pair to look at.
    """
    status, runner = rebuild(
        succeeded(),
        a_build(),
        an_open_candidate(),
        answered(IntegrationExitCode.CANDIDATE_FAILED),
        answered(IntegrationExitCode.NO_LIBRARY_CHECK_FAILED),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.CANDIDATE_FAILED
    assert runner.subcommands[-1] == str(IntegrationSubcommand.LOCATE_CANDIDATE_FAILURE)


def test_only_a_candidate_that_failed_is_localised(tmp_path: Path):
    """
    A search costs a round of matrix runs per prefix, so spending one on a build that
    published, or on one still waiting, is a real cost for no answer.
    """
    _, runner = rebuild(
        succeeded(), a_build(), an_open_candidate(), succeeded(), tmp_path=tmp_path
    )

    assert str(IntegrationSubcommand.LOCATE_CANDIDATE_FAILURE) not in runner.subcommands


# %% waiting for an answer that is not ready


def test_a_rebuild_keeps_asking_while_the_candidate_s_checks_are_unfinished(
    tmp_path: Path,
):
    """
    Read once and acted on, a candidate whose matrix has not finished reads as a build
    nothing had judged - and throwing one away is what this waiting exists to prevent.
    """
    status, runner = rebuild(
        succeeded(),
        a_build(),
        an_open_candidate(),
        answered(IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.CANDIDATE_STILL_RUNNING
    assert runner.subcommands.count(str(IntegrationSubcommand.SETTLE_CANDIDATE)) == (
        QUICKLY.attempts
    )


def test_a_rebuild_keeps_asking_while_a_localisation_s_probes_are_still_running(
    tmp_path: Path,
):
    """
    A round of probes is a matrix run each, so the first call has nothing to conclude
    from: it dispatches and leaves the round to be read back by a later call.
    """
    _, runner = rebuild(
        succeeded(),
        a_build(),
        an_open_candidate(),
        answered(IntegrationExitCode.CANDIDATE_FAILED),
        answered(IntegrationExitCode.PROBES_STILL_RUNNING),
        tmp_path=tmp_path,
    )

    assert (
        runner.subcommands.count(str(IntegrationSubcommand.LOCATE_CANDIDATE_FAILURE))
        == QUICKLY.attempts
    )


def test_a_localisation_is_told_where_to_dispatch_and_where_to_keep_its_state(
    tmp_path: Path,
):
    """
    A dispatch runs the workflow file the dispatched reference carries, and the tree
    under test carries none; the state is what makes the next call the same search
    rather than a new one.
    """
    _, runner = rebuild(
        succeeded(),
        a_build(),
        an_open_candidate(),
        answered(IntegrationExitCode.CANDIDATE_FAILED),
        answered(IntegrationExitCode.NO_LIBRARY_CHECK_FAILED),
        tmp_path=tmp_path,
    )
    localising = runner.invoked[-1]

    assert str(CommandLineFlag.DISPATCH_ON) in localising
    assert str(tmp_path / "localisation.json") in localising


def test_a_candidate_nothing_reports_a_check_against_stops_the_rebuild(tmp_path: Path):
    """
    No check having been created is a different thing from a matrix taking its time, and
    waiting it out spends the whole schedule to end saying the checks were slow - when
    what a reader has to look at is whatever should have started one.
    """
    status, runner = rebuild(
        succeeded(),
        a_build(),
        an_open_candidate(),
        a_settling(ChecksVerdict.ABSENT, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.CANDIDATE_UNCHECKED
    assert runner.subcommands.count(str(IntegrationSubcommand.SETTLE_CANDIDATE)) == (
        A_SHORT_WARM_UP
    )


def test_a_first_reading_finding_no_check_yet_is_waited_through(tmp_path: Path):
    """
    A candidate's run takes a moment to be created, so the first reading finding nothing
    is what an ordinary rebuild looks like - giving up there would throw away the build
    that run was about to judge.
    """
    status, _ = rebuild(
        succeeded(),
        a_build(),
        an_open_candidate(),
        a_settling(ChecksVerdict.ABSENT, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        succeeded(),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.SUCCESS
