"""
Localising a candidate's red to the tip whose arrival turned it.

A candidate red on a matrix job names a failing check and nothing else. The local search
cannot reproduce it - it re-runs the configured tooling suite, and the matrix runs a
library's own tests - so the failure is found by re-running that library over each prefix
of the merge order instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from integration_localisation import (
    PROBE_RUN_NAME_PREFIX,
    PROBE_WORKFLOW_FILE,
    LibraryUnderTest,
    ProbeWorkflowInput,
    probe_run_name,
)

WORKFLOW_DIRECTORY = Path(__file__).parent.parent.parent.parent / ".github" / "workflows"
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
    """The events a workflow answers to.

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
    Every existing caller passes no reference and must keep checking out the tree its own
    run started on, which is what an empty default leaves ``actions/checkout`` doing.
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
    A workflow cannot import a constant, so its ``run-name`` is the one place this prefix
    is spelled a second time. Spelled differently, every probe reads as one whose run has
    not appeared, and a localisation waits out its whole timeout finding nothing.
    """
    assert workflow(PROBE_WORKFLOW)["run-name"].startswith(PROBE_RUN_NAME_PREFIX)
    assert probe_run_name(A_PREFIX_BRANCH) == f"{PROBE_RUN_NAME_PREFIX}{A_PREFIX_BRANCH}"


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
    The matrix names each job for the library it runs, which is what makes re-running one
    of them expressible at all.
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
    ``test_claude_dev_tooling`` runs the same directories the local search re-runs, so it
    is already localised, faster, and before a build is pushed; the untracked-interfaces
    check is a property of one tree rather than of a combination, so no prefix scan says
    anything about it.
    """
    assert LibraryUnderTest.named_by(check) is None


def test_every_library_the_matrix_runs_is_one_this_can_ask_about():
    """
    A library added to the matrix and not here would have its failures reported as
    naming no library at all - silently answered as "nothing to localise" rather than
    as the gap it is.
    """
    matrix = workflow(WORKFLOW_DIRECTORY / "ci.yml")["jobs"]["test_each_lib"]["strategy"]

    assert {entry["lib"] for entry in matrix["matrix"]["include"]} == {
        str(library) for library in LibraryUnderTest
    }
