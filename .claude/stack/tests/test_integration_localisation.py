"""
Localising a candidate's red to the tip whose arrival turned it.

A candidate red on a matrix job names a failing check and nothing else. The local search
cannot reproduce it - it re-runs the configured tooling suite, and the matrix runs a
library's own tests - so the failure is found by re-running that library over each prefix
of the merge order instead.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from stack import PullRequest

from maintenance_github import DispatchedWorkflowRuns, WorkflowRunRecord

import integration
from integration import IntegrationExitCode, ProbeAssembly, ResolutionProvenance
from integration_verdict import CheckRunField, ChecksVerdict

from integration_localisation import (
    PROBE_RUN_NAME_PREFIX,
    PROBE_WORKFLOW_FILE,
    LibraryUnderTest,
    Localisation,
    LocalisationStage,
    LocalisationStep,
    Probe,
    ProbeWorkflowInput,
    TipUnderSuspicion,
    WorkflowRunField,
    dispatch,
    probe_run_name,
    verdict_of,
)

from test_maintenance import (
    ForkCheckout,
    RecordingPullRequests,
    UPSTREAM_BASE,
    a_stack,
    fork_checkout,  # noqa: F401  (imported so pytest finds the fixture by name)
    make_configuration,
)

from integration_fixtures import FIRST_TIP, INNOCENT_TIP, SECOND_TIP, THIRD_TIP

from test_integration_verdict import refresh_job, refresh_job_script

WORKFLOW_DIRECTORY = (
    Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
)
"""
Where this repository's workflows live, from this test module's own location.
"""

PROBE_WORKFLOW = WORKFLOW_DIRECTORY / PROBE_WORKFLOW_FILE
"""
The dispatchable job one probe is a run of, named by the constant that dispatches it.
"""

REUSABLE_WORKFLOW = WORKFLOW_DIRECTORY / "ci_reusable.yml"
"""
The job that runs one library's tests, which a probe reuses rather than restates.
"""

A_PREFIX_BRANCH = "integration-probe-20260829-120000-2"
"""
A prefix of a merge order, published under a name of its own.
"""


def workflow(path: Path) -> dict:
    """
    :param path: The workflow to read.
    :return: Its parsed document.
    """
    return yaml.safe_load(path.read_text())


def triggers(path: Path) -> dict:
    """
    The events a workflow answers to.

    Read under ``True`` rather than ``"on"`` because YAML reads a bare ``on`` key as the
    boolean.

    :param path: The workflow to read.
    :return: Its trigger block.
    """
    return workflow(path)[True]


# %% the tree a probe tests


def test_a_probe_is_dispatched_on_a_reference_that_carries_it_and_told_what_to_test():
    """
    The obvious shape - dispatch the probe on the prefix itself - cannot work: a prefix
    is the upstream base plus some tips, and a dispatch runs the workflow file the
    dispatched reference carries. The empty prefix is bare upstream ``main``, which
    carries no probe workflow and never will until this lands there.

    So the tree under test is an input, and the reference dispatched is one that has the
    pipeline on it.
    """
    inputs = triggers(PROBE_WORKFLOW)["workflow_dispatch"]["inputs"]

    assert set(ProbeWorkflowInput) <= set(inputs)
    assert all(inputs[str(declared)]["required"] for declared in ProbeWorkflowInput)


def test_the_probe_checks_out_the_tree_it_was_handed():
    """
    Dispatching on a reference that carries the pipeline means the run starts on the
    wrong tree by construction, so the tree under test has to reach the checkout.
    """
    called = workflow(PROBE_WORKFLOW)["jobs"]["test"]["with"]

    assert called["ref"] == f"${{{{ inputs.{ProbeWorkflowInput.BUILD} }}}}"


def test_the_reusable_job_checks_out_the_reference_it_is_given():
    """
    A probe reuses the library job rather than restating sixty lines of container setup,
    so the one thing it needs from it is the ability to run over a tree other than the
    one the run started on.
    """
    checkout = next(
        step
        for step in workflow(REUSABLE_WORKFLOW)["jobs"]["test"]["steps"]
        if "actions/checkout" in step.get("uses", "")
    )

    assert checkout["with"]["ref"] == "${{ inputs.ref }}"


def test_the_reusable_job_still_runs_over_its_own_reference_when_given_none():
    """
    Every existing caller passes no reference and must keep checking out the tree its
    own run started on, which is what an empty default leaves ``actions/checkout``
    doing.
    """
    declared = triggers(REUSABLE_WORKFLOW)["workflow_call"]["inputs"]["ref"]

    assert declared["required"] is False and declared["default"] == ""


def test_the_probe_runs_the_library_it_was_asked_about():
    """
    Re-running the whole matrix per prefix costs sixteen jobs to answer about one; the
    failing check names the library, so that is the only job worth running.
    """
    called = workflow(PROBE_WORKFLOW)["jobs"]["test"]["with"]

    assert called["lib"] == f"${{{{ inputs.{ProbeWorkflowInput.LIBRARY} }}}}"


# %% finding a probe's run again


def test_a_probe_run_is_named_after_the_tree_it_tests():
    """
    A dispatch answers 204 with no run identifier, and every probe of one localisation
    shares the reference it was dispatched on - so the name is the only thing that tells
    two of them apart.
    """
    assert workflow(PROBE_WORKFLOW)["run-name"] == probe_run_name(
        f"${{{{ inputs.{ProbeWorkflowInput.BUILD} }}}}"
    )


def test_the_reader_and_the_workflow_agree_on_how_a_run_is_named():
    """
    A workflow cannot import a constant, so its ``run-name`` is the one place this
    prefix is spelled a second time.

    Spelled differently, every probe reads as one whose run has not appeared, and a
    localisation waits out its whole timeout finding nothing.
    """
    assert workflow(PROBE_WORKFLOW)["run-name"].startswith(PROBE_RUN_NAME_PREFIX)
    assert (
        probe_run_name(A_PREFIX_BRANCH) == f"{PROBE_RUN_NAME_PREFIX}{A_PREFIX_BRANCH}"
    )


# %% which failing checks this can answer about


@pytest.mark.parametrize(
    "check,library",
    [
        ("test_each_lib (krrood)", "krrood"),
        ("test_each_lib (semantic_digital_twin)", "semantic_digital_twin"),
        ("test_each_lib (krrood) / test", "krrood"),
    ],
)
def test_a_failing_matrix_check_names_the_library_to_re_run(check: str, library: str):
    """
    The matrix names each job for the library it runs, which is what makes re-running
    one of them expressible at all.
    """
    assert LibraryUnderTest.named_by(check) == LibraryUnderTest(library)


@pytest.mark.parametrize(
    "check",
    ["test_claude_dev_tooling", "check_generated_orm_interfaces_are_untracked"],
)
def test_a_failing_check_that_names_no_library_is_not_this_search_s_to_answer(
    check: str,
):
    """
    Both are real failures and neither is localised by re-running a library.

    ``test_claude_dev_tooling`` runs the same directories the local search re-runs, so
    it is already localised, faster, and before a build is pushed; the untracked-
    interfaces check is a property of one tree rather than of a combination, so no
    prefix scan says anything about it.
    """
    assert LibraryUnderTest.named_by(check) is None


def test_every_library_the_matrix_runs_is_one_this_can_ask_about():
    """
    A library added to the matrix and not here would have its failures reported as
    naming no library at all - silently answered as "nothing to localise" rather than
    as the gap it is.
    """
    matrix = workflow(WORKFLOW_DIRECTORY / "ci.yml")["jobs"]["test_each_lib"][
        "strategy"
    ]

    assert {entry["lib"] for entry in matrix["matrix"]["include"]} == {
        str(library) for library in LibraryUnderTest
    }


# %% what one probe's run says


def create_probe(
    tip: str = "a-tip",
    verdict: ChecksVerdict = ChecksVerdict.ABSENT,
    number: int = 7,
) -> Probe:
    """
    :param tip: The tip this probe is about.
    :param verdict: What its run says so far.
    :param number: The fork pull request publishing the tip.
    :return: One probe, without a repository behind it.
    """
    return Probe(
        branch=f"integration-probe-{tip}",
        tip=tip,
        pull_request_number=number,
        verdict=verdict,
    )


def create_localisation(
    probes: tuple[Probe, ...],
    stage: LocalisationStage = LocalisationStage.PREFIXES,
    suspect: TipUnderSuspicion | None = None,
) -> Localisation:
    """
    :param probes: The probes in flight.
    :param stage: Which round they belong to.
    :param suspect: The tip round one localised, once it has.
    :return: A search in flight.
    """
    return Localisation(
        library=LibraryUnderTest.KRROOD, stage=stage, probes=probes, suspect=suspect
    )


def test_a_probe_whose_run_has_not_appeared_yet_is_waited_for():
    """
    A dispatch is accepted before its run object exists, so no run at all is the
    ordinary first answer rather than a sign anything is wrong.

    What catches a dispatch that never produced one is the caller's own timeout.
    """
    localisation = create_localisation((create_probe(verdict=ChecksVerdict.ABSENT),))

    assert localisation.next_step is LocalisationStep.WAIT


def test_one_probe_still_running_holds_the_whole_round():
    """
    A round's answer is which of its probes failed, and reading that from a partial set
    would name whichever finished first rather than whichever is earliest in merge
    order.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.RUNNING),
        )
    )

    assert localisation.next_step is LocalisationStep.WAIT


# %% what the first round localises


def test_a_prefix_round_that_passes_throughout_localises_nothing():
    """
    Every prefix of the merge order passing means the candidate's red is not reproducible
    by adding the tips one at a time - a flake, or something outside the tree. Saying so
    is the answer; inventing a culprit from the last prefix would name an innocent branch.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.PASSED),
        )
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.localised_suspect is None


def test_the_first_prefix_that_fails_names_the_tip_whose_arrival_turned_it():
    """
    The tips before it were in a passing build, so the one that turned the suite is the
    one that arrived - which is the same rule the local search follows by stopping at the
    first prefix that fails.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.FAILED, number=42),
            create_probe(tip=THIRD_TIP, verdict=ChecksVerdict.FAILED),
        )
    )

    assert localisation.localised_suspect == TipUnderSuspicion(
        branch=SECOND_TIP, pull_request_number=42, already_included=(FIRST_TIP,)
    )


def test_a_first_prefix_that_fails_with_nothing_before_it_is_concluded_rather_than_narrowed():
    """
    There is no earlier tip to narrow against, so the failure is the tip against the base
    alone - and a narrowing round over an empty set would dispatch nothing and wait for it.
    """
    localisation = create_localisation(
        (create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.FAILED),)
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.breaks_against is None


def test_a_failure_with_earlier_tips_is_narrowed_rather_than_reported_as_the_combination():
    """
    ``breaks_against`` of ``None`` is a positive claim - that no single earlier tip
    reproduces the failure alone - and the comment says so in those words. Reporting it
    without a narrowing round would state something nothing had checked.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.FAILED),
        )
    )

    assert localisation.next_step is LocalisationStep.NARROW


# %% what the second round narrows to


def test_narrowing_names_the_latest_earlier_tip_that_reproduces_the_failure():
    """
    Asked most-recent-first, the same way a merge conflict's partner is: that is the tip
    whose commits the failing one just met.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.FAILED),
            create_probe(tip=INNOCENT_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=THIRD_TIP, verdict=ChecksVerdict.FAILED),
        ),
        stage=LocalisationStage.NARROWING,
        suspect=TipUnderSuspicion(SECOND_TIP, 42, (FIRST_TIP, INNOCENT_TIP, THIRD_TIP)),
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.breaks_against == THIRD_TIP


def test_a_narrowing_round_that_reproduces_nothing_is_what_makes_the_combination_claim_true():
    """
    Every pairing passing is the evidence behind "no single one of which reproduces it
    alone" - the claim the report makes when nothing is named.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=THIRD_TIP, verdict=ChecksVerdict.PASSED),
        ),
        stage=LocalisationStage.NARROWING,
        suspect=TipUnderSuspicion(SECOND_TIP, 42, (FIRST_TIP, THIRD_TIP)),
    )

    assert localisation.next_step is LocalisationStep.CONCLUDE
    assert localisation.breaks_against is None


# %% reading a probe's run back


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


def test_a_probe_reads_the_run_named_after_its_own_tree():
    """
    Every probe of one localisation is dispatched on the same reference, so a reader
    that took the newest run, or the one on that reference, would answer every probe
    with whichever finished last.
    """
    probe = create_probe(tip=SECOND_TIP)
    other = create_probe(tip=FIRST_TIP)
    runs = [a_run(other.branch, conclusion="failure"), a_run(probe.branch)]

    assert verdict_of(runs, probe.branch) is ChecksVerdict.PASSED
    assert verdict_of(runs, other.branch) is ChecksVerdict.FAILED


def test_a_probe_with_no_run_of_its_own_yet_reports_none_reported():
    """
    A dispatch is accepted before its run object exists, so this is the ordinary first
    answer - told apart from a run in progress because it is also what a dispatch that
    never started one looks like.
    """
    assert verdict_of([], "integration-probe-nothing") is ChecksVerdict.ABSENT


# %% the document a repeatable call reads and rewrites


def test_the_search_survives_the_call_that_wrote_it():
    """
    The waiting lives with the caller, so a search is picked up by a later invocation
    that shares nothing with the one that started it but this document.
    """
    localisation = create_localisation(
        (
            create_probe(tip=FIRST_TIP, verdict=ChecksVerdict.PASSED),
            create_probe(tip=SECOND_TIP, verdict=ChecksVerdict.FAILED, number=42),
        ),
        stage=LocalisationStage.NARROWING,
        suspect=TipUnderSuspicion(THIRD_TIP, 9, (FIRST_TIP,)),
    )

    assert Localisation.from_json(localisation.as_json()) == localisation


# %% assembling and publishing the trees a round asks about


THE_PIPELINE_REFERENCE = "integration"
"""
The reference the probes are dispatched on, which is the one carrying the pipeline.
"""


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
        named_at=datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc),
    )


def files_in(checkout: ForkCheckout, branch: str) -> set[str]:
    """
    :param checkout: The checkout to read from.
    :param branch: The published branch to read.
    :return: The names of the files that branch carries.
    """
    listed = checkout.run_git("ls-tree", "--name-only", f"origin/{branch}")
    return set(listed.splitlines())


def test_a_prefix_round_publishes_the_merge_order_one_tip_at_a_time(
    fork_checkout: ForkCheckout,
):
    """
    Each probe has to be a tree a run can check out, and the trees are exactly the
    prefixes the build itself went through - so the answer describes the build that
    failed rather than some other ordering of it.
    """
    pull_requests = three_tips(fork_checkout)

    probes = assemble(fork_checkout, pull_requests).prefixes()
    fork_checkout.run_git("fetch", "--quiet", "origin")

    assert [probe.tip for probe in probes] == [FIRST_TIP, SECOND_TIP, THIRD_TIP]
    assert files_in(fork_checkout, probes[0].branch) == {"a-file", f"{FIRST_TIP}-file"}
    assert files_in(fork_checkout, probes[2].branch) == {
        "a-file",
        f"{FIRST_TIP}-file",
        f"{SECOND_TIP}-file",
        f"{THIRD_TIP}-file",
    }


def test_a_probe_carries_the_pull_request_of_the_tip_it_is_about(
    fork_checkout: ForkCheckout,
):
    """
    The tip a round localises is reported to its own pull request, and the number is
    read here rather than looked up again later against a board that has since moved.
    """
    pull_requests = three_tips(fork_checkout)

    probes = assemble(fork_checkout, pull_requests).prefixes()

    assert [probe.pull_request_number for probe in probes] == [1, 2, 3]


def test_a_narrowing_round_pairs_each_earlier_tip_with_the_one_under_suspicion(
    fork_checkout: ForkCheckout,
):
    """
    Which earlier tip the suspect fails against alone is a different question from which
    prefix turned the tests, and only a tree holding just those two answers it.
    """
    pull_requests = three_tips(fork_checkout)
    assembly = assemble(fork_checkout, pull_requests)

    probes = assembly.pairings(THIRD_TIP, (FIRST_TIP, SECOND_TIP))
    fork_checkout.run_git("fetch", "--quiet", "origin")

    assert [probe.tip for probe in probes] == [FIRST_TIP, SECOND_TIP]
    assert files_in(fork_checkout, probes[0].branch) == {
        "a-file",
        f"{FIRST_TIP}-file",
        f"{THIRD_TIP}-file",
    }


def test_every_probe_of_a_round_is_dispatched_at_once(fork_checkout: ForkCheckout):
    """
    The probes are independent, so dispatching them together costs one run's wall clock
    for the whole round where asking one at a time costs one per tip - which is what
    makes a linear scan the right shape rather than a bisection.
    """
    fork = RecordingWorkflowRuns()
    probes = (create_probe(tip=FIRST_TIP), create_probe(tip=SECOND_TIP))

    dispatch(fork, THE_PIPELINE_REFERENCE, LibraryUnderTest.KRROOD, probes)

    assert [dispatched["inputs"] for dispatched in fork.dispatched] == [
        {
            ProbeWorkflowInput.BUILD: probes[0].branch,
            ProbeWorkflowInput.LIBRARY: str(LibraryUnderTest.KRROOD),
        },
        {
            ProbeWorkflowInput.BUILD: probes[1].branch,
            ProbeWorkflowInput.LIBRARY: str(LibraryUnderTest.KRROOD),
        },
    ]


def test_a_probe_is_dispatched_on_the_reference_carrying_the_pipeline():
    """
    A dispatch runs the workflow file the dispatched reference carries, and no prefix
    carries one - the empty prefix is bare upstream ``main``. Dispatching on the tree
    under test would only ever start working once this had landed upstream.
    """
    fork = RecordingWorkflowRuns()

    dispatch(fork, THE_PIPELINE_REFERENCE, LibraryUnderTest.KRROOD, (create_probe(),))

    assert fork.dispatched[0]["reference"] == THE_PIPELINE_REFERENCE
    assert fork.dispatched[0]["workflow"] == PROBE_WORKFLOW_FILE


def test_the_trees_a_search_published_are_taken_down_when_it_concludes(
    fork_checkout: ForkCheckout,
):
    """
    A localisation runs whenever a candidate goes red, so trees left behind accumulate -
    and once the search has answered there is nothing in one to read: a run outlives the
    branch it ran on.
    """
    pull_requests = three_tips(fork_checkout)
    assembly = assemble(fork_checkout, pull_requests)
    probes = assembly.prefixes()
    fork_checkout.run_git("fetch", "--quiet", "--prune", "origin")

    assembly.take_down(probes)
    fork_checkout.run_git("fetch", "--quiet", "--prune", "origin")

    assert [
        probe.branch
        for probe in probes
        if fork_checkout.run_git("ls-remote", "origin", f"refs/heads/{probe.branch}")
    ] == []


# %% the command that takes the search one step


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
    An :class:`~integration.IntegrationRun` stand-in wired to the scratch fork.
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
    return integration.LocateCandidateFailureCommand().run(
        run,
        argparse.Namespace(
            head=head, state=state, dispatch_on="integration", json=True
        ),
    )


def a_failing_check(name: str):
    """
    :param name: The check's name.
    :return: One finished, failed check run.
    """
    return {
        CheckRunField.NAME: name,
        CheckRunField.STATUS: "completed",
        CheckRunField.CONCLUSION: "failure",
    }


def test_a_candidate_whose_failures_name_no_library_is_answered_rather_than_probed(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    A tooling check is already localised by the local search - faster, and before a build
    is pushed - and a check that is a property of one tree is not about a combination at
    all. Probing either would spend a round of matrix runs to say nothing.
    """
    fork = RecordingFork(checks=[a_failing_check("test_claude_dev_tooling")])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)

    status = locate(run, tmp_path / "state.json")

    assert status is IntegrationExitCode.NO_LIBRARY_CHECK_FAILED
    assert fork.dispatched == []
    assert not (tmp_path / "state.json").exists()


def test_the_first_call_publishes_the_prefixes_and_leaves_the_search_to_be_read_back(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    A dispatch is only the start of a probe, so the first call has nothing to conclude
    from - it leaves the round in the document a later call picks up, and a status saying
    to ask again.
    """
    fork = RecordingFork(checks=[a_failing_check("test_each_lib (krrood)")])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)
    state = tmp_path / "state.json"

    status = locate(run, state)

    assert status is IntegrationExitCode.PROBES_STILL_RUNNING
    assert len(fork.dispatched) == 3
    assert Localisation.from_json(json.loads(state.read_text())).library is (
        LibraryUnderTest.KRROOD
    )


def test_a_prefix_round_that_answers_opens_the_narrowing_round(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    Which earlier tip the suspect fails against alone is what the report claims when it
    names one - and claims the absence of when it names none, so the round that settles
    it is opened rather than skipped.
    """
    fork = RecordingFork(checks=[a_failing_check("test_each_lib (krrood)")])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)
    state = tmp_path / "state.json"
    locate(run, state)
    published = Localisation.from_json(json.loads(state.read_text())).probes
    fork.runs.extend(
        [
            a_run(published[0].branch),
            a_run(published[1].branch, conclusion="failure"),
            a_run(published[2].branch, conclusion="failure"),
        ]
    )
    fork.dispatched.clear()

    status = locate(run, state)

    assert status is IntegrationExitCode.PROBES_STILL_RUNNING
    assert Localisation.from_json(json.loads(state.read_text())).stage is (
        LocalisationStage.NARROWING
    )
    assert len(fork.dispatched) == 1


def test_a_concluded_search_blocks_the_branch_in_the_same_words_a_local_one_does(
    fork_checkout: ForkCheckout, tmp_path: Path
):
    """
    What a localisation finds is the same kind of thing either way, so it produces the.

    same finding, reports it to the same pull request, and holds the branch out of
    promotion with the same label - there is one place that decides what happens to a
    branch that breaks another.
    """
    fork = RecordingFork(checks=[a_failing_check("test_each_lib (krrood)")])
    run = LocalisingRun(fork_checkout, three_tips(fork_checkout), fork)
    state = tmp_path / "state.json"
    locate(run, state)
    published = Localisation.from_json(json.loads(state.read_text())).probes
    fork.runs.extend(
        [
            a_run(published[0].branch),
            a_run(published[1].branch, conclusion="failure"),
            a_run(published[2].branch, conclusion="failure"),
        ]
    )
    locate(run, state)
    narrowing = Localisation.from_json(json.loads(state.read_text())).probes
    fork.runs.append(a_run(narrowing[0].branch, conclusion="failure"))

    status = locate(run, state)

    assert status is IntegrationExitCode.TESTS_FAILED
    assert fork.comments[0].body.startswith(integration.FAILURE_COMMENT_PREFIX)
    assert SECOND_TIP in fork.comments[0].body and FIRST_TIP in fork.comments[0].body
    assert not state.exists()
    assert [
        probe.branch
        for probe in published + narrowing
        if fork_checkout.run_git("ls-remote", "origin", f"refs/heads/{probe.branch}")
    ] == []


def test_the_two_rounds_of_one_search_never_publish_under_the_same_name(
    fork_checkout: ForkCheckout,
):
    """
    Both rounds are opened by calls that can land in the same second, and a narrowing.

    probe reusing a prefix probe's name would be answered by the run that judged a
    different tree - the search would read its own stale answer as this round's.
    """
    assembly = assemble(fork_checkout, three_tips(fork_checkout))

    assert assembly.branch_name(LocalisationStage.PREFIXES, 0) != assembly.branch_name(
        LocalisationStage.NARROWING, 0
    )


# %% the scheduled job that reaches for it


def localisation_step() -> dict:
    """
    :return: The rebuild step that localises a red candidate.
    """
    return next(
        step
        for step in refresh_job()["steps"]
        if integration.LocateCandidateFailureCommand().invoked_as in step.get("run", "")
    )


def test_a_red_candidate_is_localised_rather_than_left_naming_a_check():
    """
    Without this the same red repeats on every rebuild with nobody told which pair of
    branches to look at - the candidate names a failing job, and a job name is not a
    branch.
    """
    assert (
        integration.LocateCandidateFailureCommand().invoked_as in refresh_job_script()
    )


def test_only_a_candidate_that_failed_is_localised():
    """
    Read from the step's own condition rather than from its shell, because that is where
    it is decided: a search costs a round of matrix runs per prefix, so spending one on a
    build that published, or on one still waiting, is a real cost for no answer.
    """
    assert str(int(IntegrationExitCode.CANDIDATE_FAILED)) in localisation_step()["if"]


def test_the_scheduled_job_keeps_asking_while_a_round_is_still_running():
    """
    Read as a number in shell, so spelled differently the loop stops after its first
    round - dispatching the prefixes and never reading what they said.
    """
    assert str(int(IntegrationExitCode.PROBES_STILL_RUNNING)) in refresh_job_script()


def test_the_probes_are_dispatched_on_the_reference_the_tooling_was_read_from():
    """
    A dispatch runs the workflow file the dispatched reference carries, and the tree under
    test carries none - so the reference has to be one holding this pipeline, which is the
    same one the job checked the tooling out at.
    """
    assert (
        "github.event.repository.default_branch"
        in localisation_step()["env"]["PIPELINE_REFERENCE"]
    )


def test_the_dispatch_reference_is_one_expression_rather_than_several_lines():
    """
    A folded YAML scalar folds only the lines level with its first one; a continuation
    indented further keeps its newline, which parses cleanly and leaves a line break
    inside a ``${{ }}`` expression for GitHub to reject at run time.
    """
    assert "\n" not in localisation_step()["env"]["PIPELINE_REFERENCE"]
