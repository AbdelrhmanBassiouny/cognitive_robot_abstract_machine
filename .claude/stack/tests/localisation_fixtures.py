"""
What the localisation tests share: the stand-ins, the builders and the scratch fork.

Split out of one module rather than repeated across the several that replaced it, so a
probe, a round and a fork stand-in are each built one way wherever they are needed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Sequence
from pathlib import Path

from git_commands import BRANCH_REFERENCE_PREFIX
from stack import PullRequest

from maintenance_github import DispatchedWorkflowRuns, WorkflowRunRecord

import integration_localisation_commands
from integration_exit_codes import IntegrationExitCode
from integration_probe_assembly import ProbeAssembly
from integration_tips import ResolutionProvenance
from integration_verdict import CheckRunField, ChecksVerdict
from matrix_libraries import LibraryUnderTest
from workflow_document import WorkflowFile

from integration_localisation import (
    Localisation,
    LocalisationStage,
    TipUnderSuspicion,
)
from integration_probes import DispatchedProbe, WorkflowRunField, probe_run_name

from test_maintenance import (
    ForkCheckout,
    RecordingPullRequests,
    UPSTREAM_BASE,
    a_stack,
    make_configuration,
)

from integration_fixtures import FIRST_TIP, SECOND_TIP, THIRD_TIP

A_LIBRARY = LibraryUnderTest.in_the_matrix()[0]
"""
One of the libraries the matrix runs, taken from the matrix rather than named here so a
test says nothing about which libraries this repository happens to have.
"""

MATRIX_JOB = WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix
"""
The job that fans out over the libraries, whose key is what its checks are named after.
"""

A_PREFIX_BRANCH = "integration-probe-20260829-120000-prefixes-2"
"""
A prefix of a merge order, published under a name of its own.
"""

THE_PIPELINE_REFERENCE = "integration"
"""
The reference the probes are dispatched on, which is the one carrying the pipeline.
"""

A_MOMENT = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
"""
When a round's branches are named after, fixed so a name is the test's to predict.
"""


def check_name_for(library: LibraryUnderTest, suffix: str = "") -> str:
    """
    Name a check the way the matrix names one, from the job it fans out.

    :param library: The library the job ran.
    :param suffix: What a called workflow adds to it, when one does.
    :return: The check's name as the API reports it.
    """
    return f"{MATRIX_JOB.identifier} ({library}){suffix}"


# %% probes and rounds, without a repository behind them


def create_probe(
    tip: str = "a-tip",
    verdict: ChecksVerdict = ChecksVerdict.ABSENT,
    number: int = 7,
) -> DispatchedProbe:
    """
    :param tip: The tip this probe is about.
    :param verdict: What its run says so far.
    :param number: The fork pull request publishing the tip.
    :return: One probe, without a repository behind it.
    """
    return DispatchedProbe(
        branch=f"integration-probe-{tip}",
        tip=tip,
        pull_request_number=number,
        verdict=verdict,
    )


def create_localisation(
    probes: tuple[DispatchedProbe, ...],
    stage: LocalisationStage = LocalisationStage.PREFIXES,
    suspect: TipUnderSuspicion | None = None,
) -> Localisation:
    """
    :param probes: The probes in flight.
    :param stage: Which round they belong to.
    :param suspect: The tip round one localised, once it has.
    :return: A search in flight.
    """
    return Localisation(library=A_LIBRARY, stage=stage, probes=probes, suspect=suspect)


def a_run(
    build_branch: str,
    status: str = "completed",
    conclusion: str | None = "success",
) -> WorkflowRunRecord:
    """
    :param build_branch: The tree the run tested, which is what names it.
    :param status: Whether it has finished.
    :param conclusion: How it finished.
    :return: One workflow run, as the API answers it.
    """
    return {
        WorkflowRunField.NAME: probe_run_name(build_branch),
        WorkflowRunField.STATUS: status,
        WorkflowRunField.CONCLUSION: conclusion,
    }


def a_failing_check(name: str) -> dict:
    """
    :param name: The check's name.
    :return: One finished, failed check run.
    """
    return {
        CheckRunField.NAME: name,
        CheckRunField.STATUS: "completed",
        CheckRunField.CONCLUSION: "failure",
    }


# %% fork stand-ins


@dataclass(frozen=True)
class RecordingWorkflowRuns(DispatchedWorkflowRuns):
    """
    A fork stand-in recording what a localisation dispatched, and answering with runs.

    Frozen because its base is: a dataclass refuses a non-frozen subclass of a frozen
    one, and the recording is appended to rather than reassigned.
    """

    runs: list[WorkflowRunRecord] = field(default_factory=list)
    """
    What it answers a run read with.
    """

    dispatched: list[dict] = field(default_factory=list)
    """
    Every dispatch made on it.
    """

    def dispatch_workflow(self, workflow, reference, inputs) -> None:
        """
        :param workflow: The workflow file run.
        :param reference: The reference it was run on.
        :param inputs: What it was handed.
        """
        self.dispatched.append(
            {"workflow": workflow, "reference": reference, "inputs": dict(inputs)}
        )

    def workflow_runs(self, workflow: str) -> list[WorkflowRunRecord]:
        """
        :param workflow: The workflow file read.
        :return: The runs this stand-in was given.
        """
        return self.runs


@dataclass(frozen=True)
class RecordingFork(RecordingPullRequests, DispatchedWorkflowRuns):
    """
    A fork stand-in that answers a candidate's checks, a probe's runs, and the writes
    blocking a branch makes.
    """

    checks: list = field(default_factory=list)
    """
    What it answers a check-run read with.
    """

    runs: list[WorkflowRunRecord] = field(default_factory=list)
    """
    What it answers a workflow-run read with.
    """

    dispatched: list[dict] = field(default_factory=list)
    """
    Every dispatch made on it.
    """

    def check_runs(self, reference: str) -> list:
        """
        :param reference: The commit read.
        :return: The candidate's checks.
        """
        return self.checks

    def dispatch_workflow(self, workflow, reference, inputs) -> None:
        """
        :param workflow: The workflow file run.
        :param reference: The reference it was run on.
        :param inputs: What it was handed.
        """
        self.dispatched.append(
            {"workflow": workflow, "reference": reference, "inputs": dict(inputs)}
        )

    def workflow_runs(self, workflow: str) -> list[WorkflowRunRecord]:
        """
        :param workflow: The workflow file read.
        :return: The runs this stand-in was given.
        """
        return self.runs


@dataclass(frozen=True)
class LocalisingRun:
    """
    An :class:`~integration_run.IntegrationRun` stand-in wired to the scratch fork.
    """

    checkout: ForkCheckout
    """
    The checkout the trees are assembled and published from.
    """

    pull_requests: list[PullRequest]
    """
    The board entries the stack is derived from.
    """

    fork_answers: RecordingFork
    """
    The fork it hands out.
    """

    @property
    def configuration(self):
        """:return: The resolved configuration."""
        return make_configuration()

    @property
    def git(self):
        """:return: The runner naming the checkout."""
        return self.checkout.git

    def fork(self) -> RecordingFork:
        """:return: The fork."""
        return self.fork_answers

    def stack(self, fork):
        """
        :param fork: Ignored; the board is the one the test arranged.
        :return: The derived stack.
        """
        return a_stack(self.checkout, self.pull_requests)

    def refresh_remotes(self) -> None:
        """
        Nothing to refresh: the scratch fork's remotes are already current.
        """

    def provenance_path(self) -> Path:
        """:return: A path carrying no recorded resolutions."""
        return self.checkout.project_root / "no-provenance.json"


# %% the scratch fork


def three_tips(checkout: ForkCheckout) -> list[PullRequest]:
    """
    Three tips that merge cleanly in order, so a round's own arithmetic is what a test
    about assembling reads rather than any collision between them.

    :param checkout: The checkout to build them in.
    :return: The board entries.
    """
    for tip in (FIRST_TIP, SECOND_TIP, THIRD_TIP):
        checkout.branch_from(tip, UPSTREAM_BASE)
    checkout.git.switch_to(UPSTREAM_BASE)
    return [
        PullRequest(number=index, head=tip, base=UPSTREAM_BASE, draft=False)
        for index, tip in enumerate((FIRST_TIP, SECOND_TIP, THIRD_TIP), start=1)
    ]


def assemble(checkout: ForkCheckout, pull_requests: list[PullRequest]) -> ProbeAssembly:
    """
    :param checkout: The checkout to assemble in.
    :param pull_requests: The board entries the stack is derived from.
    :return: An assembly wired to the scratch fork, at a fixed moment.
    """
    return ProbeAssembly(
        stack=a_stack(checkout, pull_requests),
        git=checkout.git,
        provenance=ResolutionProvenance({}),
        named_at=A_MOMENT,
    )


def files_in(checkout: ForkCheckout, branch: str) -> set[str]:
    """
    :param checkout: The checkout to read from.
    :param branch: The published branch to read.
    :return: The names of the files that branch carries.
    """
    return set(checkout.git.file_names_in(f"origin/{branch}"))


def published(checkout: ForkCheckout, probes: Sequence[DispatchedProbe]) -> list[str]:
    """
    :param checkout: The checkout to read from.
    :param probes: The probes whose trees to look for.
    :return: The branches of those still on the fork.
    """
    return [
        probe.branch
        for probe in probes
        if checkout.git.remote_reference(
            "origin", f"{BRANCH_REFERENCE_PREFIX}{probe.branch}"
        )
    ]


def locate(
    run: LocalisingRun, state: Path, head: str = "a-head"
) -> IntegrationExitCode:
    """
    Take one step of a localisation against the scratch fork.

    :param run: The run to take it in.
    :param state: Where the search in flight is kept.
    :param head: The commit the candidate's checks are on.
    :return: The status the step left.
    """
    return integration_localisation_commands.LocateCandidateFailureCommand().run(
        run,
        argparse.Namespace(
            head=head, state=state, dispatch_on=THE_PIPELINE_REFERENCE, json=True
        ),
    )
