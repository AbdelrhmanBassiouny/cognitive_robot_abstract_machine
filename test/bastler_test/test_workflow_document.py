"""
Reading this repository's workflows through something with names.

The model exists so a job, a step and the action it uses are reached by asking rather
than by indexing into a mapping under keys spelled again at every reader. These check it
against the real files, which is what makes it a parser rather than a second description
of them.
"""

from __future__ import annotations

import pytest

from bastler.matrix_libraries import LibraryUnderTest
from bastler.workflow_document import (
    Action,
    JobNotFoundError,
    StepNotFoundError,
    TriggerEvent,
    WorkflowFile,
)

# %% the files this tooling knows about


@pytest.mark.parametrize("named", list(WorkflowFile))
def test_every_workflow_this_tooling_names_is_one_the_repository_has(
    named: WorkflowFile,
):
    """
    A file name is what the dispatch endpoint takes, so one that names nothing is a
    request GitHub answers with a 404 at the far end of a runner.
    """
    assert named.path.is_file()


@pytest.mark.parametrize("named", list(WorkflowFile))
def test_every_named_workflow_parses_and_declares_a_trigger(named: WorkflowFile):
    """
    A workflow's trigger block is read under ``True`` rather than ``"on"``, because YAML
    reads a bare ``on`` key as the boolean - a reader that forgets it looks in an empty
    mapping and answers that the workflow responds to nothing.
    """
    assert named.read().triggers


# %% what a reader asks a job


def test_a_job_is_found_by_its_key_and_carries_it():
    """
    The key is what a check reported for the job is named after, so it is part of the
    job rather than something the caller has to remember it looked one up by.
    """
    found = WorkflowFile.INTEGRATION_PROBE.read().job("test")

    assert found.identifier == "test"


def test_a_job_the_workflow_does_not_declare_is_refused_with_the_ones_it_does():
    """
    Reached through a mapping this is a ``KeyError`` naming the key and nothing else,
    which says the same as a typo.
    """
    with pytest.raises(JobNotFoundError) as refusal:
        WorkflowFile.INTEGRATION_PROBE.read().job("no-such-job")

    assert "test" in str(refusal.value)


def test_a_step_is_found_by_the_action_it_uses_whatever_version_it_pins():
    """
    A step names an action as ``<action>@<version>``, so a reader matching the whole
    string finds nothing the day the version moves.
    """
    checkout = (
        WorkflowFile.REUSABLE_LIBRARY_JOB.read().job("test").step_using(Action.CHECKOUT)
    )

    assert checkout.uses.startswith(str(Action.CHECKOUT))


def test_a_job_using_no_such_action_is_refused_rather_than_answered_with_nothing():
    """
    Found by scanning, so the honest answer to "no step uses it" is a refusal - a
    ``None`` here reads at the call site as a step that uses the action and passes
    nothing.
    """
    with pytest.raises(StepNotFoundError):
        WorkflowFile.INTEGRATION_PROBE.read().job("test").step_using(Action.CHECKOUT)


def test_a_workflow_answers_whether_it_responds_to_an_event():
    """
    Asked of the model rather than of the trigger mapping, which is the half a reader
    that forgot the ``True`` key gets silently wrong.
    """
    refresh = WorkflowFile.INTEGRATION_REFRESH.read()

    assert refresh.answers_to(TriggerEvent.SCHEDULE)
    assert refresh.answers_to(TriggerEvent.WORKFLOW_DISPATCH)


# %% the libraries, read from the matrix rather than listed


def test_the_libraries_are_the_ones_the_matrix_declares():
    """
    Listed beside the matrix instead, a library added to it would have its failures
    reported as naming no library at all - answered as "nothing to localise" rather
    than as the gap it is.
    """
    declared = WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix

    assert [library.name for library in LibraryUnderTest.in_the_matrix()] == [
        entry["lib"] for entry in declared.matrix_entries
    ]


def test_the_matrix_job_is_found_by_fanning_out_rather_than_by_name():
    """
    What makes it the one is that it runs once per entry, so a rename of the job leaves
    the libraries readable where a name written here would not.
    """
    found = WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix

    assert found.matrix_entries


@pytest.mark.parametrize("library", LibraryUnderTest.in_the_matrix())
def test_every_library_the_matrix_runs_is_read_back_from_its_check_name(
    library: LibraryUnderTest,
):
    """
    The check name is all a red candidate gives, so a library the matrix runs and this
    cannot read back is one whose failures are answered as nothing to localise.
    """
    job = WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix

    assert LibraryUnderTest.named_by(f"{job.identifier} ({library})") == library


def test_a_check_name_a_called_workflow_has_suffixed_still_names_its_library():
    """
    A job calling a reusable workflow is reported with that workflow's own job appended,
    so the library is what the parentheses hold rather than what the name ends with.
    """
    job = WorkflowFile.CONTINUOUS_INTEGRATION.read().job_fanning_out_over_a_matrix
    library = LibraryUnderTest.in_the_matrix()[0]

    assert LibraryUnderTest.named_by(f"{job.identifier} ({library}) / test") == library


@pytest.mark.parametrize(
    "check", ["test_claude_dev_tooling", "check_generated_orm_interfaces_are_untracked"]
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


def test_a_check_naming_something_the_matrix_does_not_run_localises_nothing():
    """
    The parentheses alone do not make a check one of the matrix's, so what makes it
    answerable is that what they hold is a library the matrix declares.
    """
    assert LibraryUnderTest.named_by("some_other_job (not_a_library)") is None
