"""
The workflow one probe is a run of, and how its run is found again.

A dispatch is answered 204 with no run identifier, and every probe of one localisation is
dispatched on the same reference - so what the workflow calls its runs is the only thing
telling two of them apart, and it is the one place the reader's own prefix is spelled a
second time.
"""

from __future__ import annotations

from integration_probes import (
    PROBE_RUN_NAME_PREFIX,
    ProbeWorkflowInput,
    probe_run_name,
)
from workflow_document import Action, TriggerEvent, WorkflowFile

from localisation_fixtures import A_PREFIX_BRANCH


def an_input_expression(named: ProbeWorkflowInput) -> str:
    """
    :param named: The input to read.
    :return: How a workflow spells reading it.
    """
    return f"${{{{ inputs.{named} }}}}"


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
    probe = WorkflowFile.INTEGRATION_PROBE.read()

    assert probe.answers_to(TriggerEvent.WORKFLOW_DISPATCH)
    assert set(ProbeWorkflowInput) <= set(probe.dispatch_inputs)
    assert all(
        probe.dispatch_inputs[str(declared)]["required"]
        for declared in ProbeWorkflowInput
    )


def test_the_probe_checks_out_the_tree_it_was_handed():
    """
    Dispatching on a reference that carries the pipeline means the run starts on the
    wrong tree by construction, so the tree under test has to reach the checkout.
    """
    called = WorkflowFile.INTEGRATION_PROBE.read().job("test")

    assert called.inputs["ref"] == an_input_expression(ProbeWorkflowInput.BUILD)


def test_the_probe_runs_the_library_it_was_asked_about():
    """
    Re-running the whole matrix per prefix costs sixteen jobs to answer about one; the
    failing check names the library, so that is the only job worth running.
    """
    called = WorkflowFile.INTEGRATION_PROBE.read().job("test")

    assert called.inputs["lib"] == an_input_expression(ProbeWorkflowInput.LIBRARY)


def test_the_probe_reuses_the_library_job_rather_than_restating_it():
    """
    Sixty lines of container setup written a second time is sixty lines that drift from
    the matrix the candidate was judged by - and a probe answering differently from the
    job it is meant to reproduce localises nothing.
    """
    called = WorkflowFile.INTEGRATION_PROBE.read().job("test")

    assert called.calls.endswith(str(WorkflowFile.REUSABLE_LIBRARY_JOB))


def test_the_reusable_job_checks_out_the_reference_it_is_given():
    """
    A probe reuses the library job rather than restating sixty lines of container setup,
    so the one thing it needs from it is the ability to run over a tree other than the
    one the run started on.
    """
    checkout = (
        WorkflowFile.REUSABLE_LIBRARY_JOB.read().job("test").step_using(Action.CHECKOUT)
    )

    assert checkout.inputs["ref"] == "${{ inputs.ref }}"


def test_the_reusable_job_still_runs_over_its_own_reference_when_given_none():
    """
    Every existing caller passes no reference and must keep checking out the tree its
    own run started on, which is what an empty default leaves ``actions/checkout``
    doing.
    """
    declared = WorkflowFile.REUSABLE_LIBRARY_JOB.read().inputs_for(
        TriggerEvent.WORKFLOW_CALL
    )["ref"]

    assert declared["required"] is False
    assert declared["default"] == ""


# %% finding a probe's run again


def test_a_probe_run_is_named_after_the_tree_it_tests():
    """
    A dispatch answers 204 with no run identifier, and every probe of one localisation
    shares the reference it was dispatched on - so the name is the only thing that tells
    two of them apart.
    """
    assert WorkflowFile.INTEGRATION_PROBE.read().run_name == probe_run_name(
        an_input_expression(ProbeWorkflowInput.BUILD)
    )


def test_the_reader_and_the_workflow_agree_on_how_a_run_is_named():
    """
    A workflow cannot import a constant, so its ``run-name`` is the one place this
    prefix is spelled a second time.

    Spelled differently, every probe reads as one whose run has not appeared, and a
    localisation waits out its whole timeout finding nothing.
    """
    assert WorkflowFile.INTEGRATION_PROBE.read().run_name.startswith(
        PROBE_RUN_NAME_PREFIX
    )
    assert (
        probe_run_name(A_PREFIX_BRANCH) == f"{PROBE_RUN_NAME_PREFIX}{A_PREFIX_BRANCH}"
    )
