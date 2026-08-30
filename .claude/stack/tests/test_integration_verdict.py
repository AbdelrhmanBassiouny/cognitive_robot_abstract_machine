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

import pytest
import yaml

from maintenance_github import (
    CandidatePullRequests,
    CheckRunRecord,
    PullRequestReader,
    PullRequestRecord,
)

import integration_candidate_commands
import tool_runner
from integration_exit_codes import IntegrationExitCode

from maintenance_board import PullRequestField

from test_maintenance import an_api_record, make_configuration

from integration_pipeline_commands import RefreshCommand
from workflow_document import (
    CALLED_JOB_SEPARATOR,
    WorkflowDocument,
    WorkflowFile,
    every_workflow_file,
)

from integration_verdict import (
    PIPELINE_WORKFLOWS,
    Candidate,
    ChecksAboutTheBuild,
    ReportedChecks,
    ChecksVerdict,
    CheckRunConclusion,
    CheckRunField,
    CheckRunStatus,
    VerdictReportKey,
    VerdictReport,
    candidate_description,
    candidate_title,
    open_candidate,
    open_candidate_on,
    read_checks,
)

A_BUILD_BRANCH = "integration-20260828-212654"
"""
A build, named the way one is.
"""

THE_BASE = "integration"
"""
The branch a green build replaces.
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


def test_the_candidate_is_opened_against_the_branch_the_build_would_replace():
    """
    Opened against anything else, the checks judge a different tree from the one that
    would be published.
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
    assert candidate_title(A_BUILD_BRANCH).endswith(A_BUILD_BRANCH)
    assert candidate_title(A_BUILD_BRANCH) != A_BUILD_BRANCH


def an_open_pull_request(
    number: int, head: str, base: str, commit: str
) -> PullRequestRecord:
    """
    :param number: Its number.
    :param head: The branch it would merge.
    :param base: The branch it is opened against.
    :param commit: What that branch points at.
    :return: One open pull request, as the API answers it.
    """
    return an_api_record(number=number, head=head, base=base, commit=commit)


def test_the_candidate_a_later_run_settles_is_found_by_what_it_is_opened_against():
    """
    The run that opened a candidate is over long before its first check appears, so what
    settles it reads the fork rather than remembering - and what makes a pull request a
    build being judged is its base, which is the same fact that keeps one off the board.
    """
    fork = RecordingCandidates(
        pull_requests=[
            an_open_pull_request(41, "a-feature", "main", "aaaa"),
            an_open_pull_request(213, A_BUILD_BRANCH, THE_BASE, A_HEAD),
        ]
    )

    found = open_candidate_on(fork, THE_BASE)

    assert found == Candidate(number=213, build_branch=A_BUILD_BRANCH, head=A_HEAD)


def test_nothing_being_judged_is_told_apart_from_a_candidate():
    """
    A run finding none has a build to assemble rather than one to settle, so this is a
    different instruction rather than a missing answer.
    """
    fork = RecordingCandidates(
        pull_requests=[an_open_pull_request(41, "a-feature", "main", "aaaa")]
    )

    assert open_candidate_on(fork, THE_BASE) is None


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
    assert integration_candidate_commands._verdict_exit_code(verdict) is expected


def test_every_verdict_is_mapped_to_a_status():
    """
    The mapping is a chain of ifs with a fallthrough, so a verdict added later would
    silently take whichever branch happens to be last rather than one chosen for it.
    """
    assert {
        integration_candidate_commands._verdict_exit_code(verdict)
        for verdict in ChecksVerdict
    } <= set(IntegrationExitCode)


# %% the scheduled job that drives them


REFRESH_WORKFLOW = (
    Path(__file__).parent.parent.parent.parent
    / ".github"
    / "workflows"
    / "integration-refresh.yml"
)
"""
The scheduled job that rebuilds the branch and publishes a green build.
"""


def refresh_workflow_triggers() -> dict:
    """The events the scheduled job answers to.

    Read under ``True`` rather than ``"on"`` because YAML reads a bare ``on`` key as the
    boolean, which is why this is a named helper rather than an index at each caller.

    :return: The workflow's trigger block.
    """
    return yaml.safe_load(REFRESH_WORKFLOW.read_text())[True]


def refresh_job() -> dict:
    """
    :return: The job that rebuilds the branch.
    """
    return yaml.safe_load(REFRESH_WORKFLOW.read_text())["jobs"]["refresh"]


def test_a_pull_request_becoming_reviewable_rebuilds_the_branch():
    """
    Leaving draft is what makes a branch integrable, so it is the moment a rebuild is
    worth doing - waiting for the next scheduled run serves the stale branch for up to
    six hours after the work became available.
    """
    assert "ready_for_review" in refresh_workflow_triggers()["pull_request"]["types"]


def checkout_reference() -> str:
    """
    :return: The reference the job checks the tooling out at.
    """
    checkout = next(
        step
        for step in refresh_job()["steps"]
        if "actions/checkout" in step.get("uses", "")
    )
    return checkout["with"]["ref"]


def test_the_checkout_reference_is_one_expression_rather_than_several_lines():
    """
    A folded YAML scalar folds only the lines level with its first one; a continuation
    indented further keeps its newline, which parses cleanly and leaves a line break
    inside a ``${{ }}`` expression for GitHub to reject at run time.
    """
    assert "\n" not in checkout_reference()


def test_a_pull_request_rebuild_reads_the_tooling_from_the_default_branch():
    """
    A ``pull_request`` run checks out that pull request's merge reference by default, so
    an unguarded checkout would run whatever ``integration.py`` the triggering branch
    happens to carry, against a token that can write. The rebuild is never about the
    branch that triggered it.
    """
    assert "github.event.repository.default_branch" in checkout_reference()


def test_every_other_rebuild_reads_the_tooling_from_the_reference_it_was_started_on():
    """
    Pinning every trigger to the default branch would mean a change to the pipeline could
    only ever run once it was already published there - and publishing is what the
    pipeline does, so a change that broke publishing could not be fixed by running the
    fix. Dispatching a reference is how a change is tried before it lands.
    """
    assert checkout_reference().endswith("github.ref }}")


def test_a_pull_request_from_a_fork_does_not_start_a_rebuild():
    """
    A fork's pull request is handed no secret, so the run could only fail on a token it
    has not got - and fail on somebody else's pull request, where the failure reads as
    theirs. Not running says the same thing without the noise.
    """
    assert "head.repo.full_name == github.repository" in refresh_job()["if"]


def refresh_job_script() -> str:
    """Every shell the scheduled job runs, with its comments taken out.

    Stripped because the comments explain the very statuses and names these tests look
    for: left in, a status the job branches on wrongly would still be found in the
    sentence explaining what the right one means.

    :return: The executable shell, as one text.
    """
    job = yaml.safe_load(REFRESH_WORKFLOW.read_text())["jobs"]["refresh"]
    return "\n".join(
        line
        for step in job["steps"]
        for line in step.get("run", "").splitlines()
        if not line.lstrip().startswith("#")
    )


def test_the_scheduled_job_hands_the_rebuild_the_reference_to_dispatch_probes_on():
    """
    What the job still spells is what only a runner knows: which reference this pipeline
    was read from, since a dispatch runs the workflow file the dispatched reference
    carries and the tree under test carries none.

    Everything else it once spelled - each command's name, the statuses it branched on,
    the document keys the steps handed each other - moved into ``integration.py refresh``
    when the procedure did, and is checked there against the definitions themselves.
    """
    assert "PIPELINE_REFERENCE" in refresh_job_script()


@dataclass(frozen=True)
class RecordingGit:
    """
    A git stand-in recording the commands a settling ran.
    """

    commands: list[tuple[str, ...]] = field(default_factory=list)
    """Every command run through it, in order."""

    def run(self, *arguments: str) -> str:
        """
        :param arguments: The git command.
        :return: Nothing, which is all a settling reads.
        """
        self.commands.append(arguments)
        return ""


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


def settle(checks: list[CheckRunRecord]) -> RecordingIntegrationRun:
    """Settle a candidate against the checks it collected.

    :param checks: What its checks say.
    :return: The run, carrying what the settling did.
    """
    run = RecordingIntegrationRun(RecordingCandidates(checks=checks))
    integration_candidate_commands.SettleCandidateCommand().run(
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


def test_the_rebuild_runs_the_suite_before_it_pushes_anything():
    """
    The candidate's own checks include this suite, so running it here is duplication -
    on a good build. On a bad one it is what stops a known-broken build being pushed, a
    candidate being opened to be closed red, and a whole matrix being spent saying so.

    Asserted as the absence of the flag that turns it off rather than as the command
    line's shape, since that is the one edit that would give the duplication back its
    cost without giving back what it buys.
    """
    assert not any("--no-test" in str(flag) for flag in tool_runner.CommandLineFlag)
