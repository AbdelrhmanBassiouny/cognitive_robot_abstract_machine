"""
The rebuild the scheduled job performs, and what is left of the job that calls it.

Every decision the rebuild makes is a decision about an exit status. Written in a job's
``run:`` block those were loops, ``if`` statements and exit-code literals in YAML, which
nothing can run outside a runner and so nothing checked. Here they are ordinary branches
in a procedure, exercised through a runner that answers with the statuses a real one
would.

A rebuild never reaches a verdict on the candidate it opened: measured on this fork, the
first check appeared 19 minutes after one candidate was opened and 2 hours 47 minutes
after another, which no job can outwait. So one run opens a candidate and a later one
settles it, and these are written in terms of what a run inherits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import integration_constants
import integration_pipeline_commands
from integration_commands import COMMANDS
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


def no_candidate_open() -> CommandOutcome:
    """:return: The answer a run gets when nothing is being judged."""
    return answered(IntegrationExitCode.NO_CANDIDATE_OPEN)


def no_recorded_pass() -> CommandOutcome:
    """:return: The answer a run gets when this build's tree is one nothing has checked."""
    return answered(IntegrationExitCode.NO_RECORDED_PASS)


def a_reported_candidate() -> CommandOutcome:
    """
    Both opening a candidate and finding the one already open report the same three
    facts, which is what lets a run settle a candidate it did not open.

    :return: One candidate's outcome, naming the pull request, the build and the commit.
    """
    return succeeded(
        {
            VerdictReportKey.CANDIDATE: A_CANDIDATE,
            VerdictReportKey.BUILD_BRANCH: A_BUILD_BRANCH,
            VerdictReportKey.HEAD: A_HEAD,
        }
    )


def rebuild(
    *answers: CommandOutcome,
    tmp_path: Path,
    take_down: CommandOutcome | None = None,
) -> tuple:
    """
    The take-down a rebuild opens with is answered here rather than by each caller: its
    status is deliberately not acted on, so scripting it would put a step no decision
    depends on in front of every one that does.

    :param answers: What each command a rebuild decides on answers, in turn.
    :param tmp_path: Where the localisation would keep its state.
    :param take_down: What the take-down answers, where a test is about that.
    :return: The status the rebuild reached, and the runner that recorded it.
    """
    runner = RecordingRunner(answers=[take_down or succeeded(), *answers])
    status = RefreshPipeline(
        dispatch_on="integration",
        state_document=tmp_path / "localisation.json",
        runner=runner,
        wait=lambda seconds: None,
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
    assert str(named) in {command.invoked_as for command in COMMANDS}


def test_the_rebuild_itself_is_one_of_those_commands():
    """
    The workflow calls one thing, so a rebuild that is not a command of the builder is a
    workflow calling something that does not exist.
    """
    assert integration_pipeline_commands.RefreshCommand().invoked_as in {
        command.invoked_as for command in COMMANDS
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


# %% the candidate a run inherits


def test_a_rebuild_asks_what_is_already_being_judged_before_assembling_anything():
    """
    Two candidates open at once are two builds racing for one branch, and the checks a
    run opens a candidate for do not start while it is still running - so what an
    earlier run left is the first thing a rebuild has to know about.
    """
    _, runner = rebuild(
        no_candidate_open(),
        succeeded(),
        a_build(),
        no_recorded_pass(),
        a_reported_candidate(),
        tmp_path=Path("/nowhere"),
    )

    asked = runner.subcommands

    assert asked.index(str(IntegrationSubcommand.FIND_CANDIDATE)) < asked.index(
        str(MaintenanceSubcommand.FAST_FORWARD)
    )


def test_a_rebuild_takes_down_what_earlier_runs_left_before_it_adds_another(
    tmp_path: Path,
):
    """
    Only publishing takes a build down on its own, so every rebuild that ends any other
    way leaves one - four times a day. Asked before the run reaches anything it can stop
    on, since a run that stopped early is exactly the kind that left one.
    """
    _, runner = rebuild(
        no_candidate_open(),
        answered(IntegrationExitCode.GIT_COMMAND_FAILED),
        tmp_path=tmp_path,
    )

    assert runner.subcommands[0] == str(
        IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS
    )


def test_a_rebuild_carries_on_past_a_take_down_that_failed(tmp_path: Path):
    """
    Tidying is not the work a rebuild exists to do, so a fork that refused a deletion
    must not cost the build - the branches it did not drop are dropped by the next run.
    """
    status, runner = rebuild(
        no_candidate_open(),
        succeeded(),
        a_build(),
        no_recorded_pass(),
        a_reported_candidate(),
        tmp_path=tmp_path,
        take_down=answered(IntegrationExitCode.GIT_COMMAND_FAILED),
    )

    assert status is IntegrationExitCode.SUCCESS
    assert str(IntegrationSubcommand.OPEN_CANDIDATE) in runner.subcommands


def test_a_candidate_still_collecting_checks_is_left_for_a_later_run(tmp_path: Path):
    """
    Measured on this fork, a candidate's first check appeared 19 minutes after it was
    opened and, for another, 2 hours 47 minutes - so a run that waited would time out
    with the build unjudged, and one that assembled another would open a second
    candidate against the same branch.
    """
    status, runner = rebuild(
        a_reported_candidate(),
        a_settling(ChecksVerdict.RUNNING, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.SUCCESS
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(IntegrationSubcommand.FIND_CANDIDATE),
        str(IntegrationSubcommand.SETTLE_CANDIDATE),
    ]


def test_the_candidate_a_run_inherits_is_settled_as_the_build_it_was_opened_for(
    tmp_path: Path,
):
    """
    The run that opened it is over, so the branch it judges and the commit its checks
    are reported against are read back off the fork rather than remembered.
    """
    _, runner = rebuild(
        a_reported_candidate(),
        a_settling(ChecksVerdict.RUNNING, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        tmp_path=tmp_path,
    )
    settling = next(
        invocation
        for invocation in runner.invoked
        if str(IntegrationSubcommand.SETTLE_CANDIDATE) in invocation
    )

    assert str(A_CANDIDATE) in settling
    assert A_BUILD_BRANCH in settling
    assert A_HEAD in settling


def test_a_green_candidate_is_published_and_the_run_goes_on_to_the_next_build(
    tmp_path: Path,
):
    """
    Publishing is what the settling does; assembling again afterwards is what keeps one
    scheduled run worth one build rather than one every other run.
    """
    status, runner = rebuild(
        a_reported_candidate(),
        succeeded(),
        succeeded(),
        a_build(),
        no_recorded_pass(),
        a_reported_candidate(),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.SUCCESS
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(IntegrationSubcommand.FIND_CANDIDATE),
        str(IntegrationSubcommand.SETTLE_CANDIDATE),
        str(MaintenanceSubcommand.FAST_FORWARD),
        str(IntegrationSubcommand.BUILD),
        str(IntegrationSubcommand.PUBLISH_RECORDED_PASS),
        str(IntegrationSubcommand.OPEN_CANDIDATE),
    ]


def test_an_inherited_candidate_nothing_reported_a_check_against_stops_the_rebuild(
    tmp_path: Path,
):
    """
    A candidate reads as unchecked for its first minutes whatever happens, so nothing
    could be concluded from that inside the run that opened it. One that has been open
    since the previous run and still has no check is a different statement: whatever
    should have started one - the trigger, or the credential it was opened with - did
    not.
    """
    status, _ = rebuild(
        a_reported_candidate(),
        a_settling(ChecksVerdict.ABSENT, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.CANDIDATE_UNCHECKED


# %% what a rebuild does with each answer


def test_a_rebuild_that_opened_a_candidate_stops_rather_than_waiting_for_its_checks(
    tmp_path: Path,
):
    """
    Nothing is thrown away by stopping - the candidate is open and the next run settles
    it - where waiting holds a runner for the whole job to end on a build still
    unjudged.
    """
    status, runner = rebuild(
        no_candidate_open(),
        succeeded(),
        a_build(),
        no_recorded_pass(),
        a_reported_candidate(),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.SUCCESS
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(IntegrationSubcommand.FIND_CANDIDATE),
        str(MaintenanceSubcommand.FAST_FORWARD),
        str(IntegrationSubcommand.BUILD),
        str(IntegrationSubcommand.PUBLISH_RECORDED_PASS),
        str(IntegrationSubcommand.OPEN_CANDIDATE),
    ]


def test_a_build_whose_tree_has_already_passed_is_published_with_no_candidate(
    tmp_path: Path,
):
    """
    Nothing moved, so the assembled tree is the one already published: opening a
    candidate for it spends about twenty-five minutes of matrix, plus however long
    GitHub takes to start one, to be told what the fork already recorded.
    """
    status, runner = rebuild(
        no_candidate_open(),
        succeeded(),
        a_build(),
        succeeded(),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.SUCCESS
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(IntegrationSubcommand.FIND_CANDIDATE),
        str(MaintenanceSubcommand.FAST_FORWARD),
        str(IntegrationSubcommand.BUILD),
        str(IntegrationSubcommand.PUBLISH_RECORDED_PASS),
    ]


def test_a_build_the_publication_refused_is_not_judged_instead(tmp_path: Path):
    """
    The refusal is about what the build carries rather than about its checks, so a
    candidate opened for it would spend a whole matrix to be refused on the same rule.
    """
    status, runner = rebuild(
        no_candidate_open(),
        succeeded(),
        a_build(),
        answered(IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED
    assert str(IntegrationSubcommand.OPEN_CANDIDATE) not in runner.subcommands


def test_an_inherited_candidate_whose_build_was_refused_stops_the_run(tmp_path: Path):
    """
    A run that read the refusal as its own success would carry on and assemble the next
    build, which is how a fork ends up rebuilding four times a day around a pointer
    nothing is moving and nobody is told about.
    """
    status, runner = rebuild(
        a_reported_candidate(),
        a_settling(ChecksVerdict.PASSED, IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.PIPELINE_WOULD_BE_REMOVED
    assert str(IntegrationSubcommand.BUILD) not in runner.subcommands


def test_a_base_that_would_not_come_forward_stops_before_anything_is_assembled(
    tmp_path: Path,
):
    """
    A build measured against a stale base is a build nobody asked for, and every later
    step would be about it.
    """
    status, runner = rebuild(
        no_candidate_open(),
        answered(IntegrationExitCode.GIT_COMMAND_FAILED),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.BASE_NOT_PREPARED
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(IntegrationSubcommand.FIND_CANDIDATE),
        str(MaintenanceSubcommand.FAST_FORWARD),
    ]


def test_a_tip_left_out_is_still_a_build_worth_judging(tmp_path: Path):
    """
    A collision to triage rather than a build that failed: what was assembled is usable,
    it is simply not whole - so it is still opened as a candidate.
    """
    status, runner = rebuild(
        no_candidate_open(),
        succeeded(),
        a_build(IntegrationExitCode.TIP_LEFT_OUT),
        no_recorded_pass(),
        a_reported_candidate(),
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
        no_candidate_open(),
        succeeded(),
        a_build(IntegrationExitCode.TESTS_FAILED),
        succeeded(),
        tmp_path=tmp_path,
    )

    assert status is IntegrationExitCode.TESTS_FAILED
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(IntegrationSubcommand.FIND_CANDIDATE),
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
        a_reported_candidate(),
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
        a_reported_candidate(),
        succeeded(),
        succeeded(),
        a_build(),
        no_recorded_pass(),
        a_reported_candidate(),
        tmp_path=tmp_path,
    )

    assert str(IntegrationSubcommand.LOCATE_CANDIDATE_FAILURE) not in runner.subcommands


# %% a rebuild asked for one plan


A_PLAN = "rdr-refactor"
"""
The plan a filtered rebuild is asked for.
"""


def filtered_rebuild(*answers: CommandOutcome, tmp_path: Path) -> tuple:
    """
    :param answers: What each command in turn answers.
    :param tmp_path: Where the localisation would keep its state.
    :return: The status the rebuild reached, and the runner that recorded it.
    """
    runner = RecordingRunner(answers=list(answers))
    status = RefreshPipeline(
        dispatch_on="integration",
        plans=(A_PLAN,),
        state_document=tmp_path / "localisation.json",
        runner=runner,
        wait=lambda seconds: None,
        localisation_schedule=QUICKLY,
    ).run()
    return status, runner


def test_a_rebuild_asked_for_one_plan_settles_nothing_and_publishes_nothing(
    tmp_path: Path,
):
    """
    The build it assembles is deliberately not the whole of what is in flight, so
    settling the cycle's candidate or moving the branch a developer works from onto this
    would act on everything else on the strength of one plan.
    """
    status, runner = filtered_rebuild(
        succeeded(), a_build(), a_reported_candidate(), tmp_path=tmp_path
    )

    assert status is IntegrationExitCode.SUCCESS
    assert runner.subcommands == [
        str(IntegrationSubcommand.TAKE_DOWN_UNREFERENCED_BUILDS),
        str(MaintenanceSubcommand.FAST_FORWARD),
        str(IntegrationSubcommand.BUILD),
        str(IntegrationSubcommand.OPEN_CANDIDATE),
    ]


def test_both_the_build_and_its_candidate_are_told_which_plan_was_asked_for(
    tmp_path: Path,
):
    """
    The build to know which tips to carry, and the candidate because what keeps a
    filtered build from ever being published is where its candidate is opened.
    """
    _, runner = filtered_rebuild(
        succeeded(), a_build(), a_reported_candidate(), tmp_path=tmp_path
    )
    told = [
        invocation
        for invocation in runner.invoked
        if {str(IntegrationSubcommand.BUILD), str(IntegrationSubcommand.OPEN_CANDIDATE)}
        & set(invocation)
    ]

    assert len(told) == 2
    for invocation in told:
        assert str(CommandLineFlag.PLAN) in invocation
        assert A_PLAN in invocation


# %% waiting for an answer that is not ready


def test_a_rebuild_keeps_asking_while_a_localisation_s_probes_are_still_running(
    tmp_path: Path,
):
    """
    A round of probes is a matrix run each, so the first call has nothing to conclude
    from: it dispatches and leaves the round to be read back by a later call.
    """
    _, runner = rebuild(
        a_reported_candidate(),
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
        a_reported_candidate(),
        answered(IntegrationExitCode.CANDIDATE_FAILED),
        answered(IntegrationExitCode.NO_LIBRARY_CHECK_FAILED),
        tmp_path=tmp_path,
    )
    localising = runner.invoked[-1]

    assert str(CommandLineFlag.DISPATCH_ON) in localising
    assert str(tmp_path / "localisation.json") in localising
