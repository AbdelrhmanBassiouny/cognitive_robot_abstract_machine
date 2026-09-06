"""
The candidate a build is judged as, and what its checks amount to.

A build is regenerated from scratch, so publishing one is moving a pointer rather than
merging anything - and the only thing that can say whether it is worth moving to is the
repository's own checks, which run on a pull request and nowhere else.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import pytest

from bastler.git_commands import GitCommandResult

from .constants import REPOSITORY_ROOT
from .integration_fixtures import the_pipeline_this_checkout_carries

from bastler.maintenance_github import (
    CandidatePullRequests,
    CheckRunRecord,
    PullRequestReader,
    PullRequestRecord,
)

import bastler.integration_candidate_commands
import bastler.integration_exit_codes
import bastler.integration_pass_record
import bastler.integration_pipeline
import bastler.integration_verdict
import bastler.tool_runner
from bastler.integration_exit_codes import IntegrationExitCode

from bastler.maintenance_board import PullRequestField

from .test_maintenance import UPSTREAM_BASE, an_api_record, make_configuration

from bastler.integration_pipeline_commands import RefreshCommand
from bastler.workflow_document import (
    CALLED_JOB_SEPARATOR,
    WorkflowDocument,
    WorkflowFile,
    every_workflow_file,
)

from bastler.integration_verdict import (
    MEASURED_CANDIDATE_CHECK_TIMING,
    PIPELINE_WORKFLOWS,
    Candidate,
    CandidateCheckTiming,
    ChecksAboutTheBuild,
    ReportedChecks,
    ChecksVerdict,
    CheckRunConclusion,
    CheckRunField,
    CheckRunStatus,
    VerdictReportKey,
    VerdictReport,
    CandidateTitle,
    candidate_description,
    candidate_for_everything_in_flight,
    open_candidate,
    read_checks,
)

A_BUILD_BRANCH = "integration-20260828-212654"
"""
A build, named the way one is.
"""

THE_BASE = UPSTREAM_BASE
"""
The branch every candidate is opened against, which is the base the build was assembled
over and so the one it always merges with.
"""

A_PLAN = "stack-maintenance"
"""
A plan a filtered build is asked to carry.
"""

ANOTHER_PLAN = "rdr-refactor"
"""
A second one, so a title naming more than one is exercised.
"""

A_HEAD = "933161a263"
"""
The build's head, which its checks are reported against.
"""


def a_check(
    name: str = "test_bastler",
    status: str = CheckRunStatus.COMPLETED,
    conclusion: str | None = CheckRunConclusion.SUCCESS,
) -> CheckRunRecord:
    """
    :param name: What the check is called.
    :param status: Whether it has finished.
    :param conclusion: How it finished.
    :return: One check run, as the API answers it.
    """
    return {
        CheckRunField.NAME: name,
        CheckRunField.STATUS: status,
        CheckRunField.CONCLUSION: conclusion,
    }


def a_rebuild_check_name() -> str:
    """
    :return: What the rebuild's own job reports its check as, read off the workflow.
    """
    refresh = WorkflowFile.INTEGRATION_REFRESH.read()
    return refresh.job_whose_script_holds(RefreshCommand().invoked_as).name


def a_probe_check_name() -> str:
    """
    :return: What a probe reports its library job's check as, which is the calling job's
        name and the reusable workflow's job beneath it.
    """
    calling = next(
        job for job in WorkflowFile.INTEGRATION_PROBE.read().jobs if job.calls
    )
    called = WorkflowFile.REUSABLE_LIBRARY_JOB.read().jobs[0]
    return f"{calling.name}{CALLED_JOB_SEPARATOR}{called.name}"


@dataclass(frozen=True)
class OpenedPullRequest:
    """
    What a stand-in fork was asked to open, kept so a test asks what it was asked for
    rather than indexing into a mapping the stand-in built itself.
    """

    title: str
    """What the pull request is called."""

    head: str
    """The branch to be judged."""

    base: str
    """The branch it is opened against."""

    body: str
    """The description."""


@dataclass(frozen=True)
class RecordingCandidates(CandidatePullRequests, PullRequestReader):
    """
    A fork stand-in recording what a candidate did to it.

    Frozen because its base is: a dataclass refuses a non-frozen subclass of a frozen
    one, and the recording is appended to rather than reassigned.
    """

    checks: list[CheckRunRecord] = field(default_factory=list)
    """What it answers a check-run read with."""

    number: int = 4242
    """The number it gives a pull request it opens."""

    opened: list[OpenedPullRequest] = field(default_factory=list)
    """Every pull request opened on it."""

    closed: list[int] = field(default_factory=list)
    """Every pull request closed on it."""

    read_references: list[str] = field(default_factory=list)
    """Every commit or branch whose checks were read from it."""

    def open_pull_request(self, title: str, head: str, base: str, body: str) -> int:
        """
        :param title: The pull request's title.
        :param head: The branch to be judged.
        :param base: The branch it is opened against.
        :param body: The description.
        :return: The number it was given.
        """
        self.opened.append(
            OpenedPullRequest(title=title, head=head, base=base, body=body)
        )
        return self.number

    def close_pull_request(self, number: int) -> None:
        """:param number: The pull request closed."""
        self.closed.append(number)

    pull_requests: list[PullRequestRecord] = field(default_factory=list)
    """What it answers a read of the fork's open pull requests with."""

    def check_runs(self, reference: str) -> list[CheckRunRecord]:
        """
        :param reference: The commit or branch read.
        :return: The checks this stand-in was given.
        """
        self.read_references.append(reference)
        return self.checks

    def open_pull_requests(self) -> list[PullRequestRecord]:
        """:return: The open pull requests this stand-in was given."""
        return self.pull_requests

    def pull_request(self, number: int) -> PullRequestRecord:
        """:param number: The pull request wanted.
        :return: It, out of the ones this stand-in was given."""
        return next(
            record
            for record in self.pull_requests
            if PullRequestField.NUMBER.read(record) == number
        )


# %% what the checks amount to


def test_every_check_passing_is_the_only_thing_that_publishes_a_build():
    """
    A build replaces the branch a developer works from, so the one state that moves the
    pointer is every check finished and none of them failed.
    """
    checks = ReportedChecks.of([a_check(), a_check(name="test_each_lib")])

    assert checks.verdict is ChecksVerdict.PASSED
    assert checks.failed == ()


def test_a_check_still_running_is_not_a_verdict():
    """
    Publishing on a partial pass would move the pointer to a build the matrix had not
    finished judging.
    """
    checks = ReportedChecks.of(
        [a_check(), a_check(name="slow", status="in_progress", conclusion=None)]
    )

    assert checks.verdict is ChecksVerdict.RUNNING


def test_a_failure_is_answered_without_waiting_for_the_rest():
    """
    The build is not publishable either way, and waiting out a matrix to say so costs
    the time the candidate exists to save.
    """
    checks = ReportedChecks.of(
        [
            a_check(name="broke", conclusion="failure"),
            a_check(name="slow", status="in_progress", conclusion=None),
        ]
    )

    assert checks.verdict is ChecksVerdict.FAILED


def test_a_failure_names_the_checks_that_failed():
    """
    "The candidate is red" is not actionable; which job went red is where a reader
    starts.
    """
    checks = ReportedChecks.of(
        [
            a_check(),
            a_check(name="test_each_lib (coraplex)", conclusion="failure"),
            a_check(name="test_each_lib (krrood)", conclusion="timed_out"),
        ]
    )

    assert [run.name for run in checks.failed] == [
        "test_each_lib (coraplex)",
        "test_each_lib (krrood)",
    ]


@pytest.mark.parametrize("conclusion", sorted(CheckRunConclusion))
def test_a_check_that_declined_to_judge_does_not_hold_a_build_back(conclusion: str):
    """
    A skipped or neutral check says nothing about the tree it was asked about, so
    treating either as a failure would hold every build behind a job that declined to
    run.
    """
    checks = ReportedChecks.of([a_check(conclusion=conclusion)])

    assert checks.verdict is ChecksVerdict.PASSED


def test_no_check_at_all_is_told_apart_from_one_still_running():
    """
    This is the state that can mean something is wrong rather than slow: a candidate
    opened by a credential whose pushes start no workflow run sits here forever rather
    than turning red, and a caller that read it as "running" would wait forever with it.
    """
    assert ReportedChecks.of([]).verdict is ChecksVerdict.ABSENT


# %% the checks the pipeline reports about its own work


def test_the_rebuild_s_own_check_does_not_decide_whether_a_branch_is_fit_to_carry():
    """
    The rebuild opens a candidate for the *build*, and its run attaches a check to
    whichever branch triggered it. Counting that would let a rebuild that failed for its
    own reasons exclude the branch whose ready-flip asked for it - which is how the
    branch that triggered a build was left out of it.
    """
    checks = ReportedChecks.of(
        [a_check(), a_check(name=a_rebuild_check_name(), conclusion="failure")]
    )

    assert checks.verdict is ChecksVerdict.PASSED
    assert checks.failed == ()


def test_a_probe_s_check_does_not_decide_it_either():
    """
    A probe is dispatched on the reference carrying the pipeline, so its checks land on
    that branch - and a probe *failing* is how a localisation finds what it is looking
    for, so reading one as the branch's own red is backwards.
    """
    checks = ReportedChecks.of(
        [a_check(name=a_probe_check_name(), conclusion="failure")]
    )

    assert checks.verdict is ChecksVerdict.ABSENT


def test_a_branch_carrying_nothing_but_the_pipeline_s_own_checks_is_unjudged():
    """
    Told apart from a pass rather than folded into one: nothing has said anything about
    this tree, and answering "passed" would publish a build no matrix had looked at.
    """
    assert ReportedChecks.of([a_check(name=a_rebuild_check_name())]).verdict is (
        ChecksVerdict.ABSENT
    )


def test_the_pipeline_s_own_check_names_are_read_off_the_workflows_that_report_them():
    """
    A workflow cannot import a constant, so the names are its own to state - and a name
    retyped here would keep matching a job that had been renamed.
    """
    reported = ChecksAboutTheBuild.read()

    assert reported.reports(a_rebuild_check_name())
    assert not reported.reports(
        WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix.name
    )


def test_no_other_workflow_reports_a_check_the_pipeline_would_claim_as_its_own():
    """
    The exclusion is by name, so a job of this repository's sharing one with a job of
    the pipeline's would have its failures silently ignored - which is the opposite
    defect, and the one a shared ``to-lowercase`` key would have caused.
    """
    reported = ChecksAboutTheBuild.read()
    the_pipeline_s_own = {workflow.path for workflow in PIPELINE_WORKFLOWS}
    elsewhere = [
        job.name
        for workflow in every_workflow_file()
        if workflow not in the_pipeline_s_own
        for job in WorkflowDocument.at(workflow).jobs
    ]

    assert elsewhere
    assert [name for name in elsewhere if reported.reports(name)] == []


# %% the candidate itself


def test_the_candidate_is_opened_against_the_base_the_build_was_assembled_over():
    """
    A build is that base plus the merged tips, so it merges with it by construction -
    where against the branch it would replace, which is an older build of the same
    branches, the two conflict and GitHub computes no merge reference for anything to
    check out.
    """
    fork = RecordingCandidates()

    candidate = open_candidate(fork, A_BUILD_BRANCH, THE_BASE, A_HEAD)

    assert fork.opened[0].head == A_BUILD_BRANCH
    assert fork.opened[0].base == THE_BASE
    assert candidate.number == fork.number


def test_the_candidate_says_it_is_never_merged():
    """
    A reader meets it as an ordinary pull request and it is not one: merging it would
    give the branch a history the next build cannot regenerate.
    """
    description = candidate_description(A_BUILD_BRANCH, THE_BASE)

    assert "never merged" in description.lower()
    assert A_BUILD_BRANCH in description and THE_BASE in description


def test_the_candidate_is_recognisable_among_the_fork_s_pull_requests():
    """
    It sits in the same list as everything a person opened, so its title has to say what
    it is without being read.
    """
    title = str(CandidateTitle(A_BUILD_BRANCH))

    assert title.endswith(A_BUILD_BRANCH)
    assert title != A_BUILD_BRANCH


def test_a_candidate_s_title_says_which_plans_its_build_was_asked_to_carry():
    """
    The title is the discriminator because it is set in the call that creates the
    candidate: anything written afterwards is a second call that can fail on its own,
    and a candidate nothing recognises is one no later run settles.
    """
    everything = CandidateTitle(A_BUILD_BRANCH)
    filtered = CandidateTitle(A_BUILD_BRANCH, (A_PLAN, ANOTHER_PLAN))

    assert everything.judges_everything_in_flight
    assert not filtered.judges_everything_in_flight
    assert A_PLAN in str(filtered) and ANOTHER_PLAN in str(filtered)
    assert A_PLAN not in str(everything)


@pytest.mark.parametrize(
    "written",
    [
        CandidateTitle(A_BUILD_BRANCH),
        CandidateTitle(A_BUILD_BRANCH, (A_PLAN,)),
        CandidateTitle(A_BUILD_BRANCH, (A_PLAN, ANOTHER_PLAN)),
    ],
)
def test_what_a_candidate_was_opened_to_judge_is_read_back_off_its_title(
    written: CandidateTitle,
):
    """
    Both kinds are opened against the same base now, so the title is the only thing left
    that tells them apart - and one that did not read back as it was written would let a
    one-plan build be settled and published over everything else in flight.
    """
    assert CandidateTitle.read(str(written)) == written


def test_a_pull_request_somebody_opened_is_not_read_as_a_candidate_at_all():
    """
    A candidate sits in the same list as everybody's work, so the reading has to refuse
    what is not one rather than answer about it.
    """
    assert CandidateTitle.read("Localise a red integration candidate") is None


def an_open_pull_request(
    number: int, head: str, base: str, commit: str, title: str = ""
) -> PullRequestRecord:
    """
    :param number: Its number.
    :param head: The branch it would merge.
    :param base: The branch it is opened against.
    :param commit: What that branch points at.
    :param title: What it is called.
    :return: One open pull request, as the API answers it.
    """
    return an_api_record(
        number=number, head=head, base=base, commit=commit, title=title
    )


def test_the_candidate_a_later_run_settles_is_the_one_judging_everything_in_flight():
    """
    The run that opened a candidate is over long before its first check appears, so what
    settles it reads the fork rather than remembering - and every candidate is opened
    against the same base now, so what it says it judges is the only thing left that
    tells the one a run may publish from one carrying a plan.
    """
    fork = RecordingCandidates(
        pull_requests=[
            an_open_pull_request(41, "a-feature", THE_BASE, "aaaa"),
            an_open_pull_request(
                212,
                "integration-20260828-090000",
                THE_BASE,
                "bbbb",
                title=str(CandidateTitle("integration-20260828-090000", (A_PLAN,))),
            ),
            an_open_pull_request(
                213,
                A_BUILD_BRANCH,
                THE_BASE,
                A_HEAD,
                title=str(CandidateTitle(A_BUILD_BRANCH)),
            ),
        ]
    )

    found = candidate_for_everything_in_flight(fork)

    assert found == Candidate(number=213, build_branch=A_BUILD_BRANCH, head=A_HEAD)


def test_nothing_being_judged_is_told_apart_from_a_candidate():
    """
    A run finding none has a build to assemble rather than one to settle, so this is a
    different instruction rather than a missing answer.
    """
    fork = RecordingCandidates(
        pull_requests=[an_open_pull_request(41, "a-feature", THE_BASE, "aaaa")]
    )

    assert candidate_for_everything_in_flight(fork) is None


def test_the_verdict_is_read_against_the_build_s_own_head():
    """
    Checks belong to a commit rather than to a branch, and a branch moves.
    """
    fork = RecordingCandidates(checks=[a_check()])
    candidate = open_candidate(fork, A_BUILD_BRANCH, THE_BASE, A_HEAD)

    assert read_checks(fork, candidate.head).verdict is ChecksVerdict.PASSED
    assert fork.read_references == [A_HEAD]


# %% what a run of it reports


def test_the_report_names_the_failures_and_whether_anything_was_published():
    """
    The document is what a scheduled run leaves behind, and both halves are what a
    reader has to act on: which checks failed, and whether the branch moved.
    """
    fork = RecordingCandidates()
    candidate = open_candidate(fork, A_BUILD_BRANCH, THE_BASE, A_HEAD)
    checks = ReportedChecks.of([a_check(name="broke", conclusion="failure")])

    document = VerdictReport(
        candidate=candidate, checks=checks, published=False
    ).to_json()

    assert document == {
        VerdictReportKey.VERDICT: str(ChecksVerdict.FAILED),
        VerdictReportKey.CANDIDATE: fork.number,
        VerdictReportKey.BUILD_BRANCH: A_BUILD_BRANCH,
        VerdictReportKey.HEAD: A_HEAD,
        VerdictReportKey.FAILED_CHECKS: ["broke"],
        VerdictReportKey.PUBLISHED: False,
        VerdictReportKey.MISSING_PIPELINE: [],
    }


# %% the statuses the commands leave a caller with


@pytest.mark.parametrize(
    "verdict,expected",
    [
        (ChecksVerdict.PASSED, IntegrationExitCode.SUCCESS),
        (ChecksVerdict.FAILED, IntegrationExitCode.CANDIDATE_FAILED),
        (ChecksVerdict.RUNNING, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
        (ChecksVerdict.ABSENT, IntegrationExitCode.CANDIDATE_STILL_RUNNING),
    ],
)
def test_each_verdict_leaves_the_status_a_caller_acts_on(
    verdict: ChecksVerdict, expected: IntegrationExitCode
):
    """
    A scheduled run reads the status rather than the document, so a verdict that mapped
    onto the wrong one would either throw away a good build or publish a red one.

    An absent check is answered as still running: a caller that read it as red would
    discard a build nothing had judged.
    """
    assert (
        bastler.integration_candidate_commands._verdict_exit_code(verdict, published=True)
        is expected
    )


def test_every_verdict_is_mapped_to_a_status():
    """
    The mapping is a chain of ifs with a fallthrough, so a verdict added later would
    silently take whichever branch happens to be last rather than one chosen for it.
    """
    assert {
        bastler.integration_candidate_commands._verdict_exit_code(verdict, published=True)
        for verdict in ChecksVerdict
    } <= set(IntegrationExitCode)


@dataclass(frozen=True)
class RecordingGit:
    """
    A git stand-in recording the commands a settling ran.
    """

    commands: list[tuple[str, ...]] = field(default_factory=list)
    """Every command run through it, in order."""

    carried: Mapping[str, str] = field(
        default_factory=the_pipeline_this_checkout_carries
    )
    """
    What the tree being settled holds of the pipeline, keyed by path.

    An ordinary build carries the branches the pipeline lives on, so that is what this
    answers with unless a test says otherwise.
    """

    def run(self, *arguments: str) -> str:
        """
        :param arguments: The git command.
        :return: Nothing, which is all a settling reads.
        """
        self.commands.append(arguments)
        return ""

    def attempt(self, *arguments: str) -> GitCommandResult:
        """
        :param arguments: The git command, which is a read of one path out of the tree.
        :return: What that tree holds there, refusing as git does when it holds nothing.
        """
        self.commands.append(arguments)
        wanted = arguments[-1].split(":", 1)[-1]
        held = self.carried.get(wanted)
        return GitCommandResult(
            arguments=arguments,
            exit_status=0 if held is not None else 128,
            output=held or "",
            error_output="",
        )


@dataclass(frozen=True)
class RecordingIntegrationRun:
    """
    An :class:`~integration_run.IntegrationRun` stand-in for a settling that touches no
    repository.
    """

    fork_answers: RecordingCandidates
    """The fork it hands out."""

    git: RecordingGit = field(default_factory=RecordingGit)
    """The runner it hands out."""

    configuration: object = field(default_factory=make_configuration)
    """The resolved configuration, which names the remote a push goes to."""

    def fork(self) -> RecordingCandidates:
        """:return: The fork."""
        return self.fork_answers


def settle(
    checks: list[CheckRunRecord], git: RecordingGit | None = None
) -> RecordingIntegrationRun:
    """Settle a candidate against the checks it collected.

    :param checks: What its checks say.
    :param git: The tree it is settling, when a test is about what that tree carries.
    :return: The run, carrying what the settling did.
    """
    run = RecordingIntegrationRun(
        RecordingCandidates(checks=checks), git=git or RecordingGit()
    )
    bastler.integration_candidate_commands.SettleCandidateCommand().run(
        run,
        argparse.Namespace(candidate=41, build=A_BUILD_BRANCH, head=A_HEAD, json=True),
    )
    return run


def deleted_branches(run: RecordingIntegrationRun) -> list[str]:
    """
    :param run: A settling that has happened.
    :return: Every branch it deleted from the fork.
    """
    return [command[-1] for command in run.git.commands if "--delete" in command]


def test_a_published_build_s_branch_is_deleted_once_the_pointer_holds_it():
    """
    A rebuild runs on a schedule, so a branch left behind each time accumulates without
    limit - and once the pointer holds the same commit there is nothing in it to lose.
    """
    run = settle([a_check()])

    assert deleted_branches(run) == [A_BUILD_BRANCH]


def test_a_rejected_build_s_branch_is_kept_for_whoever_reads_its_checks():
    """
    Its candidate names checks somebody has to look at, and a closed pull request whose
    head is gone cannot be read.
    """
    run = settle([a_check(name="broke", conclusion="failure")])

    assert deleted_branches(run) == []
    assert run.fork_answers.closed == [41]


def test_a_candidate_still_running_is_left_open_and_its_branch_left_alone():
    """
    Nothing has been decided, so closing it would throw away the run that was going to
    decide it.
    """
    run = settle([a_check(status="in_progress", conclusion=None)])

    assert deleted_branches(run) == [] and run.fork_answers.closed == []


def test_a_candidate_nothing_has_reported_a_check_against_is_left_open():
    """
    This is what a candidate opened seconds ago looks like, before GitHub has created
    the run its checks come from - and closing one then is what stops that run from ever
    being created, so the candidate collects nothing and every later reading finds the
    same absence.
    """
    run = settle([])

    assert deleted_branches(run) == [] and run.fork_answers.closed == []


def test_a_candidate_no_run_can_judge_is_closed_so_a_rebuild_can_replace_it():
    """
    A rebuild that stopped on one it could not judge never reached the step that would
    have replaced it, which is how this pipeline stayed wedged through every scheduled
    run. Closing it is what lets the next build take its place - and unmerging it,
    since a build shares no history with anything and is never merged.
    """
    run = RecordingIntegrationRun(RecordingCandidates())

    status = bastler.integration_candidate_commands.CloseCandidateCommand().run(
        run, argparse.Namespace(candidate=41, json=True)
    )

    assert run.fork_answers.closed == [41]
    assert status is IntegrationExitCode.SUCCESS


def test_the_rebuild_runs_the_suite_before_it_pushes_anything():
    """
    The candidate's own checks include this suite, so running it here is duplication -
    on a good build. On a bad one it is what stops a known-broken build being pushed, a
    candidate being opened to be closed red, and a whole matrix being spent saying so.

    Asserted as the absence of the flag that turns it off rather than as the command
    line's shape, since that is the one edit that would give the duplication back its
    cost without giving back what it buys.
    """
    assert not any("--no-test" in str(flag) for flag in bastler.tool_runner.CommandLineFlag)


# %% how long a candidate's checks take, said once


def stack_modules() -> tuple[Path, ...]:
    """
    :return: Every module of the tooling, so a statement is looked for across all of
        them rather than across the ones a reader thought of.
    """
    return tuple(sorted(Path(bastler.integration_verdict.__file__).parent.glob("*.py")))


def slowest_wait_past_the_hour() -> int:
    """
    :return: The minutes past the hour the longest measured wait ran to, which is the
        one figure in that measurement no other number in this tooling shares.
    """
    whole_minutes = int(
        MEASURED_CANDIDATE_CHECK_TIMING.slowest_first_check.total_seconds() // 60
    )
    return whole_minutes % 60


def test_the_module_that_records_the_check_timing_says_how_long_it_was():
    """
    A record whose own module does not spell the measurement leaves every reference to
    it pointing at nothing.
    """
    recorded = Path(bastler.integration_verdict.__file__).read_text()

    assert str(slowest_wait_past_the_hour()) in recorded


def test_no_other_module_restates_how_long_a_candidate_waits():
    """
    The measurement shapes four separate designs, and written out at each of them it is
    four copies that go stale one at a time, with no reader able to tell which is
    current. Everywhere else refers to :class:`CandidateCheckTiming` instead.
    """
    restating = [
        module.name
        for module in stack_modules()
        if module.name != Path(bastler.integration_verdict.__file__).name
        and str(slowest_wait_past_the_hour()) in module.read_text()
    ]

    assert restating == []


def test_every_design_the_timing_shapes_refers_to_the_record():
    """
    A design explained by a measurement it does not name is one a reader cannot check,
    which is what restating the numbers was buying.
    """
    shaped_by_it = (
        bastler.integration_pipeline,
        bastler.integration_pass_record,
        bastler.integration_candidate_commands,
        bastler.integration_exit_codes,
    )

    silent = [
        module.__name__
        for module in shaped_by_it
        if CandidateCheckTiming.__name__ not in Path(module.__file__).read_text()
    ]

    assert silent == []
