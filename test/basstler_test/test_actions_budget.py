"""
The Actions budget: every workflow in the repository is declared in the manifest,
answers exactly the triggers it declares, never runs on a schedule, and bounds every job
it runs.

The rule-by-rule tests read the dataset's manifest and one small workflow per rule; the
repository test holds every workflow on this branch to the repository's own manifest.
"""

from __future__ import annotations

import pytest

from basstler.actions_budget import (
    ActionsBudget,
    ConcurrencyDiffers,
    JobTimeoutOverCeiling,
    MissingForkGuard,
    MissingJobTimeout,
    MissingLabelGuard,
    MissingPullRequestCancellation,
    ScheduleDeclaredError,
    ScheduledWorkflow,
    TriggerDiffers,
    UnansweredTrigger,
    UndeclaredTrigger,
    UndeclaredWorkflow,
)
from basstler.workflows import TriggerEvent, Workflow

from .constants import DatasetLocation

# %% reading the dataset


@pytest.fixture
def budget() -> ActionsBudget:
    """
    :return: The dataset's manifest.
    """
    return ActionsBudget.from_file(DatasetLocation.ACTIONS_BUDGET / "manifest.toml")


def dataset_workflow(file_name: str) -> Workflow:
    """
    :param file_name: The workflow's file name in the dataset.
    :return: The parsed workflow.
    """
    return Workflow.at(DatasetLocation.ACTIONS_BUDGET_WORKFLOWS / file_name)


# %% reading a workflow


def test_triggers_are_read_from_the_key_yaml_parses_on_into():
    """
    YAML 1.1 reads a bare ``on`` key as ``True``, so a reader looking only under
    ``"on"`` would see a workflow answering to nothing.
    """
    workflow = dataset_workflow("missing-trigger.yml")

    assert [trigger.event for trigger in workflow.triggers] == [
        TriggerEvent.WORKFLOW_DISPATCH
    ]


def test_a_trigger_list_is_read_as_triggers_with_no_filters():
    workflow = dataset_workflow("short-trigger-list.yml")

    assert [trigger.event for trigger in workflow.triggers] == [
        TriggerEvent.WORKFLOW_DISPATCH,
        TriggerEvent.WORKFLOW_CALL,
    ]


def test_a_bare_concurrency_group_does_not_cancel():
    """
    ``concurrency: <group>`` is GitHub's short form for a group that queues rather than
    cancels.
    """
    concurrency = dataset_workflow("different-concurrency.yml").concurrency

    assert concurrency is not None
    assert concurrency.cancel_in_progress is False


# %% workflows that keep to the budget


def test_a_conforming_workflow_has_no_violations(budget: ActionsBudget):
    """
    A guarded push, a cancelling pull-request concurrency group and a job calling a
    reusable workflow - which GitHub gives no ``timeout-minutes`` of its own - all pass.
    """
    assert budget.violations_of(dataset_workflow("conforming.yml")) == ()


def test_a_reusable_workflow_is_declared_under_workflow_call(budget: ActionsBudget):
    assert budget.violations_of(dataset_workflow("reusable.yml")) == ()


def test_a_pull_request_workflow_answering_only_lifecycle_events_may_queue(
    budget: ActionsBudget,
):
    """
    A workflow that never runs on ``synchronize`` has no superseded commit to cancel a
    run for, so a queueing group is allowed.
    """
    assert budget.violations_of(dataset_workflow("lifecycle-pull-request.yml")) == ()


def test_a_trigger_list_conforms_to_its_declaration(budget: ActionsBudget):
    assert budget.violations_of(dataset_workflow("short-trigger-list.yml")) == ()


# %% workflows that break it


def test_an_undeclared_workflow_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("undeclared.yml")

    assert budget.violations_of(workflow) == (
        UndeclaredWorkflow(workflow=workflow.file_name),
    )


def test_a_scheduled_workflow_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("scheduled.yml")

    assert budget.violations_of(workflow) == (
        ScheduledWorkflow(workflow=workflow.file_name),
    )


def test_a_trigger_the_manifest_does_not_declare_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("extra-trigger.yml")

    assert budget.violations_of(workflow) == (
        UndeclaredTrigger(workflow=workflow.file_name, event=TriggerEvent.PUSH),
    )


def test_a_declared_trigger_the_workflow_does_not_answer_is_reported(
    budget: ActionsBudget,
):
    """
    The manifest states what a workflow does, not an upper bound on it, so a declaration
    left behind by a removed trigger is as wrong as a trigger nobody declared.
    """
    workflow = dataset_workflow("missing-trigger.yml")

    assert budget.violations_of(workflow) == (
        UnansweredTrigger(workflow=workflow.file_name, event=TriggerEvent.PUSH),
    )


@pytest.mark.parametrize(
    "file_name, event",
    [
        ("different-activity-types.yml", TriggerEvent.PULL_REQUEST),
        ("different-branches.yml", TriggerEvent.PUSH),
    ],
)
def test_a_trigger_with_different_filters_is_reported(
    budget: ActionsBudget, file_name: str, event: TriggerEvent
):
    workflow = dataset_workflow(file_name)

    assert budget.violations_of(workflow) == (
        TriggerDiffers(
            workflow=file_name,
            declared=budget.declaration_of(file_name).trigger(event).trigger,
            answered=workflow.trigger(event),
        ),
    )


def test_a_pull_request_workflow_running_on_every_push_must_cancel(
    budget: ActionsBudget,
):
    workflow = dataset_workflow("uncancelled-pull-request.yml")

    assert budget.violations_of(workflow) == (
        MissingPullRequestCancellation(workflow=workflow.file_name),
    )


def test_a_concurrency_group_other_than_the_declared_one_is_reported(
    budget: ActionsBudget,
):
    workflow = dataset_workflow("different-concurrency.yml")

    assert budget.violations_of(workflow) == (
        ConcurrencyDiffers(
            workflow=workflow.file_name,
            declared=budget.declaration_of(workflow.file_name).concurrency,
            answered=workflow.concurrency,
        ),
    )


def test_a_job_without_a_timeout_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("missing-timeout.yml")
    (job,) = workflow.jobs

    assert budget.violations_of(workflow) == (
        MissingJobTimeout(workflow=workflow.file_name, job=job.identifier),
    )


def test_a_job_timeout_above_the_declared_ceiling_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("timeout-over-ceiling.yml")
    (job,) = workflow.jobs

    assert budget.violations_of(workflow) == (
        JobTimeoutOverCeiling(
            workflow=workflow.file_name,
            job=job.identifier,
            timeout_minutes=job.timeout_minutes,
            ceiling_minutes=budget.declaration_of(
                workflow.file_name
            ).job_timeout_minutes,
        ),
    )


def test_a_first_job_without_the_fork_guard_is_reported(budget: ActionsBudget):
    """
    Only the job nothing else waits on needs the guard: a job that ``needs`` a skipped
    job is skipped with it.
    """
    workflow = dataset_workflow("unguarded-push.yml")
    (first_job,) = workflow.first_jobs

    assert budget.violations_of(workflow) == (
        MissingForkGuard(workflow=workflow.file_name, job=first_job.identifier),
    )


def test_a_first_job_without_the_label_guard_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("unguarded-label.yml")
    (first_job,) = workflow.first_jobs
    declared = budget.declaration_of(workflow.file_name).trigger(
        TriggerEvent.PULL_REQUEST
    )

    assert budget.violations_of(workflow) == (
        MissingLabelGuard(
            workflow=workflow.file_name,
            job=first_job.identifier,
            label=declared.required_label,
        ),
    )


# %% the manifest itself


def test_a_manifest_declaring_a_schedule_is_refused():
    with pytest.raises(ScheduleDeclaredError):
        ActionsBudget.from_file(
            DatasetLocation.ACTIONS_BUDGET / "scheduled-manifest.toml"
        )


def test_a_workflow_budget_sums_its_triggers(budget: ActionsBudget):
    """
    A workflow's daily volume is what each trigger is expected to add to it.
    """
    declaration = budget.declaration_of("conforming.yml")

    assert declaration.runs_per_day == sum(
        trigger.runs_per_day for trigger in declaration.triggers
    )
    assert declaration.jobs_per_day == sum(
        trigger.runs_per_day * trigger.jobs_per_run for trigger in declaration.triggers
    )


# %% this repository


@pytest.mark.parametrize(
    "workflow",
    Workflow.every_workflow_in_the_repository(),
    ids=lambda workflow: workflow.file_name,
)
def test_every_repository_workflow_keeps_to_the_repository_budget(workflow: Workflow):
    """
    The enforcement: a branch carrying a workflow the manifest does not allow fails here
    once it merges the branch carrying this test.
    """
    assert ActionsBudget.load().violations_of(workflow) == ()


def test_the_repository_has_workflows_to_check():
    """
    The parametrization above checks nothing if discovery finds no workflow.
    """
    assert Workflow.every_workflow_in_the_repository() != ()
