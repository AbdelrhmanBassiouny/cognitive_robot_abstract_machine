"""
The Actions budget: every workflow in the repository keeps to the rules basstler holds
any workflow to, within the limits the repository's budget file sets.

The rule-by-rule tests read the dataset's budget and one small workflow per rule; the
repository test holds every workflow on this branch to the repository's own budget.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from basstler.actions_budget import ActionsBudget, BudgetDefinition, WorkflowLimits
from basstler.exceptions import (
    BudgetFileExists,
    MissingBudgetFunction,
    JobTimeoutOverCeiling,
    MissingForkGuard,
    MissingJobTimeout,
    MissingLabelGuard,
    MissingPullRequestCancellation,
    OverrideWithoutWorkflow,
    ScheduledWorkflow,
    TooManyJobsOnEveryPush,
    UncountableJobs,
)
from basstler.workflows import TriggerEvent, Workflow

from .constants import DatasetLocation

# %% reading the dataset


@pytest.fixture
def budget() -> ActionsBudget:
    """
    :return: The dataset's budget.
    """
    return ActionsBudget.from_file(DatasetLocation.ACTIONS_BUDGET / "budget.py")


def dataset_workflow(file_name: str) -> Workflow:
    """
    :param file_name: The workflow's file name in the dataset.
    :return: The parsed workflow.
    """
    return Workflow.at(DatasetLocation.ACTIONS_BUDGET_WORKFLOWS / file_name)


def every_dataset_workflow() -> tuple[Workflow, ...]:
    """
    :return: Every workflow in the dataset, in file name order.
    """
    return tuple(
        Workflow.at(path)
        for path in sorted(DatasetLocation.ACTIONS_BUDGET_WORKFLOWS.glob("*.yml"))
    )


# %% reading a workflow


def test_triggers_are_read_from_the_key_yaml_parses_on_into():
    """
    YAML 1.1 reads a bare ``on`` key as ``True``, so a reader looking only under
    ``"on"`` would see a workflow answering to nothing.
    """
    workflow = dataset_workflow("dispatch-only.yml")

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
    concurrency = dataset_workflow("bare-concurrency.yml").concurrency

    assert concurrency is not None
    assert concurrency.cancel_in_progress is False


def test_a_matrix_runs_its_job_once_per_combination_at_most():
    """
    Three Python versions on two systems, one combination excluded and one included.
    """
    (job,) = dataset_workflow("axis-matrix.yml").jobs

    assert job.instances == 3 * 2 - 1 + 1


def test_a_job_calling_a_reusable_workflow_counts_the_called_jobs():
    """
    One preparing job, and one call to a reusable workflow that runs one job.
    """
    assert dataset_workflow("conforming.yml").jobs_per_run == 2


def test_a_matrix_computed_at_run_time_cannot_be_counted():
    assert dataset_workflow("computed-matrix.yml").jobs_per_run is None


# %% workflows that keep to the budget


@pytest.mark.parametrize(
    "file_name",
    [
        "conforming.yml",
        "reusable.yml",
        "lifecycle-pull-request.yml",
        "short-trigger-list.yml",
        "axis-matrix.yml",
        "overridden-heavy-pull-request.yml",
        "fork-push-allowed.yml",
    ],
)
def test_a_workflow_keeping_to_the_budget_has_no_violations(
    budget: ActionsBudget, file_name: str
):
    """
    Among them: a pull-request workflow answering only lifecycle events, which may
    queue; a heavy workflow whose own limit the budget raises; and a push the budget
    lets a fork run.
    """
    assert budget.violations_of(dataset_workflow(file_name)) == ()


# %% workflows that break it


def test_a_scheduled_workflow_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("scheduled.yml")

    assert budget.violations_of(workflow) == (
        ScheduledWorkflow(workflow=workflow.file_name),
    )


def test_a_pull_request_workflow_running_on_every_push_must_cancel(
    budget: ActionsBudget,
):
    workflow = dataset_workflow("uncancelled-pull-request.yml")

    assert budget.violations_of(workflow) == (
        MissingPullRequestCancellation(workflow=workflow.file_name),
    )


def test_a_job_without_a_timeout_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("missing-timeout.yml")
    (job,) = workflow.jobs

    assert budget.violations_of(workflow) == (
        MissingJobTimeout(workflow=workflow.file_name, job=job.identifier),
    )


def test_a_job_timeout_above_the_ceiling_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("timeout-over-ceiling.yml")
    (job,) = workflow.jobs

    assert budget.violations_of(workflow) == (
        JobTimeoutOverCeiling(
            workflow=workflow.file_name,
            job=job.identifier,
            timeout_minutes=job.timeout_minutes,
            ceiling_minutes=budget.limits_of(workflow.file_name).job_timeout_minutes,
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
        MissingForkGuard(
            workflow=workflow.file_name,
            job=first_job.identifier,
            condition=WorkflowLimits.fork_push_condition,
        ),
    )


def test_a_first_job_without_a_label_check_is_reported(budget: ActionsBudget):
    workflow = dataset_workflow("unguarded-label.yml")
    (first_job,) = workflow.first_jobs

    assert budget.violations_of(workflow) == (
        MissingLabelGuard(workflow=workflow.file_name, job=first_job.identifier),
    )


@pytest.mark.parametrize("file_name", ["heavy-pull-request.yml", "wide-push.yml"])
def test_a_workflow_running_too_many_jobs_on_every_push_is_reported(
    budget: ActionsBudget, file_name: str
):
    """
    Both a pull request's every push and a push to any branch count.
    """
    workflow = dataset_workflow(file_name)

    assert budget.violations_of(workflow) == (
        TooManyJobsOnEveryPush(
            workflow=workflow.file_name,
            jobs=workflow.jobs_per_run,
            ceiling=budget.limits_of(workflow.file_name).jobs_per_push_run,
        ),
    )


def test_a_workflow_running_on_every_push_must_have_countable_jobs(
    budget: ActionsBudget,
):
    workflow = dataset_workflow("computed-matrix.yml")

    assert budget.violations_of(workflow) == (
        UncountableJobs(workflow=workflow.file_name),
    )


# %% the budget file


def test_a_workflow_the_file_does_not_name_gets_the_defaults(budget: ActionsBudget):
    assert budget.limits_of("conforming.yml") == budget.defaults


def test_a_budget_file_without_the_budget_function_is_reported():
    path = DatasetLocation.ACTIONS_BUDGET / "without-budget-function.py"

    with pytest.raises(MissingBudgetFunction) as raised:
        ActionsBudget.from_file(path)

    assert raised.value == MissingBudgetFunction(
        path=path, function=BudgetDefinition.FUNCTION
    )


def test_an_override_naming_no_workflow_is_reported(budget: ActionsBudget):
    """
    The dataset's budget names one workflow file the dataset does not have.
    """
    workflow_files = {workflow.file_name for workflow in every_dataset_workflow()}
    (missing,) = set(budget.overrides) - workflow_files

    assert budget.overrides_without_workflow(every_dataset_workflow()) == (
        OverrideWithoutWorkflow(workflow=missing),
    )


def test_a_written_budget_reads_back_equal(budget: ActionsBudget, tmp_path: Path):
    path = tmp_path / "budget.py"

    budget.write(path)

    assert ActionsBudget.from_file(path) == budget


def test_writing_never_replaces_an_existing_budget(
    budget: ActionsBudget, tmp_path: Path
):
    """
    The file is reviewed by hand once written, so replacing it would bless whatever the
    workflows do at that moment.
    """
    path = tmp_path / "budget.py"
    budget.write(path)

    with pytest.raises(BudgetFileExists):
        budget.write(path)


@pytest.mark.parametrize(
    "file_name",
    [
        "timeout-over-ceiling.yml",
        "heavy-pull-request.yml",
        "wide-push.yml",
        "unguarded-push.yml",
    ],
)
def test_a_baseline_raises_each_limit_a_workflow_needs(
    budget: ActionsBudget, file_name: str
):
    baseline = ActionsBudget.baseline_for(every_dataset_workflow(), budget.defaults)

    assert baseline.violations_of(dataset_workflow(file_name)) == ()


def test_a_baseline_names_only_the_workflows_the_defaults_do_not_fit(
    budget: ActionsBudget,
):
    baseline = ActionsBudget.baseline_for(
        (dataset_workflow("conforming.yml"),), budget.defaults
    )

    assert baseline.overrides == {}


# %% this repository


@pytest.mark.parametrize(
    "workflow",
    Workflow.every_workflow_in_the_repository(),
    ids=lambda workflow: workflow.file_name,
)
def test_every_repository_workflow_keeps_to_the_repository_budget(workflow: Workflow):
    """
    The enforcement: a branch carrying a workflow that breaks a rule fails here once it
    merges the branch carrying this test.
    """
    assert ActionsBudget.load().violations_of(workflow) == ()


def test_every_repository_override_names_a_workflow():
    assert (
        ActionsBudget.load().overrides_without_workflow(
            Workflow.every_workflow_in_the_repository()
        )
        == ()
    )


def test_the_repository_has_workflows_to_check():
    """
    The parametrization above checks nothing if discovery finds no workflow.
    """
    assert Workflow.every_workflow_in_the_repository() != ()
