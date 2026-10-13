"""
The Actions budget: which workflows may run in this repository, on which events, and how
much each is expected to cost.

``actions_budget.toml`` beside this module is the one statement of it. Every workflow
file is read into the same shape as its declaration, and every way a file can break the
declaration is a violation of its own type, so a test over the workflow directory can
hold each file to the manifest and say exactly what is wrong with one that drifts.
"""

from __future__ import annotations

import tomllib
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from basstler.locations import PackageLocation
from basstler.workflows import (
    ActivityType,
    Concurrency,
    Trigger,
    TriggerEvent,
    Workflow,
)

# %% vocabulary


FORK_PUSH_GUARD = "github.event_name != 'push' || !github.event.repository.fork"
"""
The condition that skips a job on a push to a fork, which only re-tests code the upstream
repository has already tested. Read off the event, so no repository is named.
"""


def label_guard(label: str) -> str:
    """
    :param label: The label a ``labeled`` event has to be about.
    :return: The condition that skips a job when any other label was added.
    """
    return f"github.event.action != 'labeled' || github.event.label.name == '{label}'"


class ManifestKey(StrEnum):
    """
    The keys of the budget manifest.
    """

    WORKFLOW = "workflow"
    """
    The array of declared workflows.
    """

    FILE = "file"
    """
    A workflow's file name.
    """

    JOB_TIMEOUT_MINUTES = "job_timeout_minutes"
    """
    The most any job of the workflow may declare as its timeout.
    """

    SKIPS_PUSH_ON_FORK = "skips_push_on_fork"
    """
    Whether a push to a fork skips the workflow's first jobs.
    """

    CONCURRENCY = "concurrency"
    """
    The concurrency the workflow has to declare.
    """

    GROUP = "group"
    """
    The concurrency group.
    """

    CANCEL_IN_PROGRESS = "cancel_in_progress"
    """
    Whether a new run in the group cancels the one in progress.
    """

    TRIGGER = "trigger"
    """
    The array of a workflow's declared triggers.
    """

    EVENT = "event"
    """
    A trigger's event.
    """

    ACTIVITY_TYPES = "activity_types"
    """
    A trigger's activity types.
    """

    BRANCHES = "branches"
    """
    A trigger's branch filters.
    """

    REQUIRED_LABEL = "required_label"
    """
    The label a ``labeled`` trigger's first jobs have to be about.
    """

    JOBS_PER_RUN = "jobs_per_run"
    """
    The jobs one run started by the trigger runs.
    """

    RUNS_PER_DAY = "runs_per_day"
    """
    The runs the trigger is expected to start in a day.
    """


# %% what the manifest allows


@dataclass(frozen=True)
class TriggerBudget:
    """
    One trigger a workflow may answer to, and what it is expected to cost.
    """

    trigger: Trigger
    """
    The trigger, which the workflow has to answer to exactly as declared.
    """

    jobs_per_run: int
    """
    The jobs one run started by this trigger runs, counting each matrix entry.
    """

    runs_per_day: float
    """
    The runs this trigger is expected to start in a day.
    """

    required_label: str | None = None
    """
    For a trigger answering ``labeled``, the label its first jobs have to be about.
    """

    @classmethod
    def from_manifest(cls, declared: Mapping[str, Any]) -> TriggerBudget:
        """
        :param declared: One ``[[workflow.trigger]]`` table.
        :return: The trigger's budget.
        """
        event = TriggerEvent(declared[ManifestKey.EVENT])
        if event is TriggerEvent.SCHEDULE:
            raise ScheduleDeclaredError()
        return cls(
            trigger=Trigger(
                event=event,
                activity_types=frozenset(
                    ActivityType(activity_type)
                    for activity_type in declared.get(ManifestKey.ACTIVITY_TYPES, ())
                ),
                branches=frozenset(declared.get(ManifestKey.BRANCHES, ())),
            ),
            jobs_per_run=declared[ManifestKey.JOBS_PER_RUN],
            runs_per_day=declared[ManifestKey.RUNS_PER_DAY],
            required_label=declared.get(ManifestKey.REQUIRED_LABEL),
        )


@dataclass(frozen=True)
class WorkflowBudget:
    """
    Everything the manifest allows one workflow.
    """

    file_name: str
    """
    The workflow's file name.
    """

    job_timeout_minutes: int
    """
    The most any job of the workflow may declare as its ``timeout-minutes``.
    """

    triggers: tuple[TriggerBudget, ...]
    """
    The triggers it may answer to.
    """

    concurrency: Concurrency | None = None
    """
    The concurrency it has to declare, or none.
    """

    skips_push_on_fork: bool = False
    """
    Whether a push to a fork has to skip its first jobs.
    """

    @classmethod
    def from_manifest(cls, declared: Mapping[str, Any]) -> WorkflowBudget:
        """
        :param declared: One ``[[workflow]]`` table.
        :return: The workflow's budget.
        """
        concurrency = declared.get(ManifestKey.CONCURRENCY)
        return cls(
            file_name=declared[ManifestKey.FILE],
            job_timeout_minutes=declared[ManifestKey.JOB_TIMEOUT_MINUTES],
            triggers=tuple(
                TriggerBudget.from_manifest(trigger)
                for trigger in declared[ManifestKey.TRIGGER]
            ),
            concurrency=(
                None
                if concurrency is None
                else Concurrency(
                    group=concurrency[ManifestKey.GROUP],
                    cancel_in_progress=concurrency[ManifestKey.CANCEL_IN_PROGRESS],
                )
            ),
            skips_push_on_fork=declared.get(ManifestKey.SKIPS_PUSH_ON_FORK, False),
        )

    @property
    def events(self) -> frozenset[TriggerEvent]:
        """
        :return: The events the workflow may answer to.
        """
        return frozenset(budget.trigger.event for budget in self.triggers)

    def trigger(self, event: TriggerEvent) -> TriggerBudget:
        """
        :param event: A declared event.
        :return: Its budget.
        """
        return next(budget for budget in self.triggers if budget.trigger.event is event)

    @property
    def runs_per_day(self) -> float:
        """
        :return: The runs the workflow is expected to start in a day.
        """
        return sum(budget.runs_per_day for budget in self.triggers)

    @property
    def jobs_per_day(self) -> float:
        """
        :return: The jobs the workflow is expected to run in a day.
        """
        return sum(
            budget.runs_per_day * budget.jobs_per_run for budget in self.triggers
        )

    def violations_of(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: The workflow this budget declares.
        :return: Every way the workflow breaks it, in the order the rules are listed here.
        """
        return (
            *self._schedule_violations(workflow),
            *self._trigger_violations(workflow),
            *self._concurrency_violations(workflow),
            *self._timeout_violations(workflow),
            *self._guard_violations(workflow),
        )

    def _schedule_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: The workflow this budget declares.
        :return: The schedule violation, if the workflow runs on one.
        """
        if TriggerEvent.SCHEDULE not in workflow.events:
            return ()
        return (ScheduledWorkflow(workflow=workflow.file_name),)

    def _trigger_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: The workflow this budget declares.
        :return: Events answered but not declared, declared but not answered, or
            answered with other filters.
        """
        answered = workflow.events - {TriggerEvent.SCHEDULE}
        undeclared = tuple(
            UndeclaredTrigger(workflow=workflow.file_name, event=trigger.event)
            for trigger in workflow.triggers
            if trigger.event in answered - self.events
        )
        unanswered = tuple(
            UnansweredTrigger(workflow=workflow.file_name, event=budget.trigger.event)
            for budget in self.triggers
            if budget.trigger.event not in answered
        )
        different = tuple(
            TriggerDiffers(
                workflow=workflow.file_name,
                declared=budget.trigger,
                answered=workflow.trigger(budget.trigger.event),
            )
            for budget in self.triggers
            if budget.trigger.event in answered
            and workflow.trigger(budget.trigger.event) != budget.trigger
        )
        return (*undeclared, *unanswered, *different)

    def _concurrency_violations(
        self, workflow: Workflow
    ) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: The workflow this budget declares.
        :return: A pull-request workflow that does not cancel superseded runs, and
            concurrency other than declared.
        """
        cancels = workflow.concurrency is not None and (
            workflow.concurrency.cancel_in_progress
        )
        uncancelled = (
            (MissingPullRequestCancellation(workflow=workflow.file_name),)
            if any(trigger.runs_on_every_push for trigger in workflow.triggers)
            and not cancels
            else ()
        )
        different = (
            (
                ConcurrencyDiffers(
                    workflow=workflow.file_name,
                    declared=self.concurrency,
                    answered=workflow.concurrency,
                ),
            )
            if workflow.concurrency != self.concurrency
            else ()
        )
        return (*uncancelled, *different)

    def _timeout_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: The workflow this budget declares.
        :return: Runner jobs without a timeout, or with one above the ceiling.
        """
        runner_jobs = tuple(job for job in workflow.jobs if job.runs_on_a_runner)
        missing = tuple(
            MissingJobTimeout(workflow=workflow.file_name, job=job.identifier)
            for job in runner_jobs
            if job.timeout_minutes is None
        )
        over = tuple(
            JobTimeoutOverCeiling(
                workflow=workflow.file_name,
                job=job.identifier,
                timeout_minutes=job.timeout_minutes,
                ceiling_minutes=self.job_timeout_minutes,
            )
            for job in runner_jobs
            if job.timeout_minutes is not None
            and job.timeout_minutes > self.job_timeout_minutes
        )
        return (*missing, *over)

    def _guard_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: The workflow this budget declares.
        :return: First jobs missing the fork or label condition the budget asks of
            them.
        """
        unguarded_push = (
            tuple(
                MissingForkGuard(workflow=workflow.file_name, job=job.identifier)
                for job in workflow.first_jobs
                if FORK_PUSH_GUARD not in job.condition
            )
            if self.skips_push_on_fork
            else ()
        )
        unguarded_label = tuple(
            MissingLabelGuard(
                workflow=workflow.file_name,
                job=job.identifier,
                label=budget.required_label,
            )
            for budget in self.triggers
            if budget.required_label is not None
            for job in workflow.first_jobs
            if label_guard(budget.required_label) not in job.condition
        )
        return (*unguarded_push, *unguarded_label)


@dataclass(frozen=True)
class ActionsBudget:
    """
    The whole manifest: every workflow allowed in the repository.

    It declares workflows that only unlanded branches carry too, with the triggers they
    are meant to have, so such a branch fails the budget test once it merges this one.
    """

    workflows: tuple[WorkflowBudget, ...]
    """
    Every declared workflow.
    """

    @classmethod
    def from_file(cls, path: Path) -> ActionsBudget:
        """
        :param path: A budget manifest.
        :return: The budget it declares.
        """
        declared = tomllib.loads(path.read_text())
        return cls(
            workflows=tuple(
                WorkflowBudget.from_manifest(workflow)
                for workflow in declared[ManifestKey.WORKFLOW]
            )
        )

    @classmethod
    def load(cls) -> ActionsBudget:
        """
        :return: The repository's own budget.
        """
        return cls.from_file(PackageLocation.ACTIONS_BUDGET.value)

    def declaration_of(self, file_name: str) -> WorkflowBudget | None:
        """
        :param file_name: A workflow's file name.
        :return: Its budget, or none when the manifest does not declare it.
        """
        return next(
            (budget for budget in self.workflows if budget.file_name == file_name),
            None,
        )

    def violations_of(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: Any workflow.
        :return: Every way it breaks this budget.
        """
        declaration = self.declaration_of(workflow.file_name)
        if declaration is None:
            return (UndeclaredWorkflow(workflow=workflow.file_name),)
        return declaration.violations_of(workflow)


# %% failures


@dataclass
class BudgetViolation(Exception, ABC):
    """
    One way a workflow breaks the budget, carrying what a reader needs to fix it.
    """

    workflow: str
    """
    The file name of the workflow that breaks it.
    """

    def __post_init__(self) -> None:
        """
        Compose the message from the subclass's own description.
        """
        super().__init__(f"{self.workflow}: {self.error_message()}")

    def __str__(self) -> str:
        """
        The composed message, rather than a repr of the dataclass fields.
        """
        return Exception.__str__(self)

    @abstractmethod
    def error_message(self) -> str:
        """
        :return: What is wrong.
        """


@dataclass
class UndeclaredWorkflow(BudgetViolation):
    """
    The manifest does not declare the workflow at all.
    """

    def error_message(self) -> str:
        return f"not declared in {PackageLocation.ACTIONS_BUDGET.value.name}"


@dataclass
class ScheduledWorkflow(BudgetViolation):
    """
    The workflow runs on a schedule, which nothing in this repository may.
    """

    def error_message(self) -> str:
        return "runs on a schedule; trigger it on the event it is waiting for instead"


@dataclass
class UndeclaredTrigger(BudgetViolation):
    """
    The workflow answers an event the manifest does not declare for it.
    """

    event: TriggerEvent
    """
    The undeclared event.
    """

    def error_message(self) -> str:
        return f"answers {self.event}, which is not declared"


@dataclass
class UnansweredTrigger(BudgetViolation):
    """
    The manifest declares an event the workflow does not answer.
    """

    event: TriggerEvent
    """
    The declared event.
    """

    def error_message(self) -> str:
        return f"is declared on {self.event}, which it does not answer"


@dataclass
class TriggerDiffers(BudgetViolation):
    """
    The workflow answers a declared event with other activity types or branches.
    """

    declared: Trigger
    """
    The trigger as the manifest declares it.
    """

    answered: Trigger
    """
    The trigger as the workflow answers it.
    """

    def error_message(self) -> str:
        return f"answers {self.answered}, declared as {self.declared}"


@dataclass
class MissingPullRequestCancellation(BudgetViolation):
    """
    The workflow runs on every push to a pull request without cancelling the run for the
    commit before.
    """

    def error_message(self) -> str:
        return "runs on every pull-request push without cancel-in-progress concurrency"


@dataclass
class ConcurrencyDiffers(BudgetViolation):
    """
    The workflow's concurrency is not the declared one.
    """

    declared: Concurrency | None
    """
    The concurrency as the manifest declares it.
    """

    answered: Concurrency | None
    """
    The concurrency as the workflow declares it.
    """

    def error_message(self) -> str:
        return f"has concurrency {self.answered}, declared as {self.declared}"


@dataclass
class MissingJobTimeout(BudgetViolation):
    """
    A job that takes a runner declares no ``timeout-minutes``, so a hang holds the runner
    for GitHub's six-hour default.
    """

    job: str
    """
    The job's key.
    """

    def error_message(self) -> str:
        return f"job {self.job} has no timeout-minutes"


@dataclass
class JobTimeoutOverCeiling(BudgetViolation):
    """
    A job's ``timeout-minutes`` is above the workflow's declared ceiling.
    """

    job: str
    """
    The job's key.
    """

    timeout_minutes: int
    """
    The job's timeout.
    """

    ceiling_minutes: int
    """
    The declared ceiling.
    """

    def error_message(self) -> str:
        return (
            f"job {self.job} times out after {self.timeout_minutes} minutes, "
            f"above the declared {self.ceiling_minutes}"
        )


@dataclass
class MissingForkGuard(BudgetViolation):
    """
    A first job of a workflow declared to skip pushes to a fork does not skip them.
    """

    job: str
    """
    The job's key.
    """

    def error_message(self) -> str:
        return f"job {self.job} does not skip a push to a fork: if: {FORK_PUSH_GUARD}"


@dataclass
class MissingLabelGuard(BudgetViolation):
    """
    A first job of a workflow answering ``labeled`` runs for any label, not only the one
    declared.
    """

    job: str
    """
    The job's key.
    """

    label: str
    """
    The label the job has to be about.
    """

    def error_message(self) -> str:
        return f"job {self.job} runs for any label: if: {label_guard(self.label)}"


@dataclass
class ScheduleDeclaredError(ValueError):
    """
    The manifest declares a ``schedule`` trigger, which nothing in this repository may
    answer.
    """

    def __str__(self) -> str:
        """
        :return: What is wrong with the manifest.
        """
        manifest = PackageLocation.ACTIONS_BUDGET.value.name
        return f"{manifest} declares a schedule; declare the event it waits for instead"
