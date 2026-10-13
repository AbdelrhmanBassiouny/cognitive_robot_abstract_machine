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
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from basstler.class_property import classproperty
from basstler.exceptions import (
    BudgetViolation,
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
from basstler.locations import PackageLocation
from basstler.workflows import (
    ActivityType,
    Concurrency,
    Trigger,
    TriggerEvent,
    Workflow,
)

# %% vocabulary


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

    @property
    def label_condition(self) -> str | None:
        """
        :return: The condition that skips a first job when a label other than
            :attr:`required_label` was added, or none when no label is required.
        """
        if self.required_label is None:
            return None
        return (
            "github.event.action != 'labeled' || "
            f"github.event.label.name == '{self.required_label}'"
        )

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

    @classproperty
    def fork_push_condition(cls) -> str:
        """
        The condition that skips a job on a push to a fork, which only re-tests code the
        upstream repository has already tested. Read off the event, so no repository is
        named.
        """
        return "github.event_name != 'push' || !github.event.repository.fork"

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
                MissingForkGuard(
                    workflow=workflow.file_name,
                    job=job.identifier,
                    condition=self.fork_push_condition,
                )
                for job in workflow.first_jobs
                if self.fork_push_condition not in job.condition
            )
            if self.skips_push_on_fork
            else ()
        )
        unguarded_label = tuple(
            MissingLabelGuard(
                workflow=workflow.file_name,
                job=job.identifier,
                condition=budget.label_condition,
            )
            for budget in self.triggers
            if budget.label_condition is not None
            for job in workflow.first_jobs
            if budget.label_condition not in job.condition
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
