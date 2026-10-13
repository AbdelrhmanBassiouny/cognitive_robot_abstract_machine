"""
The Actions budget: the rules basstler holds every workflow of a repository to, within
limits the repository sets.

The workflow files are the only statement of what each workflow does. The repository's
budget file holds only what they cannot say: the limits every workflow is held to, and
the workflows whose own limits differ. A workflow the file does not name is held to the
defaults, so a new workflow needs no entry before it is checked.
"""

from __future__ import annotations

import argparse
import dataclasses
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from basstler.class_property import classproperty
from basstler.exceptions import (
    BudgetFileExists,
    BudgetViolation,
    JobTimeoutOverCeiling,
    MissingForkGuard,
    MissingJobTimeout,
    MissingLabelGuard,
    MissingPullRequestCancellation,
    ScheduledWorkflow,
    TooManyJobsOnEveryPush,
    UncountableJobs,
)
from basstler.locations import PackageLocation, ProjectLocation
from basstler.render_common import create_template_environment
from basstler.workflows import ActivityType, TriggerEvent, Workflow

# %% vocabulary


class BudgetKey(StrEnum):
    """
    The keys of a budget file beyond the fields of :class:`WorkflowLimits`.
    """

    WORKFLOW = "workflow"
    """
    The table of workflows whose limits differ from the defaults, by file name.
    """


class BudgetTemplate(StrEnum):
    """
    The template a budget file is written from.
    """

    FILE = "actions-budget.toml.jinja"
    """
    The whole budget file.
    """


# %% the limits one workflow is held to


@dataclass(frozen=True)
class WorkflowLimits:
    """
    The limits one workflow is held to. A budget file's top level sets them for every
    workflow, and its table per workflow file changes them for that workflow alone.
    """

    job_timeout_minutes: int = 60
    """
    The most any job may declare as its ``timeout-minutes``.
    """

    jobs_per_push_run: int = 4
    """
    The most jobs a run may take runners for when the workflow runs on every push.
    """

    skips_push_on_fork: bool = True
    """
    Whether a workflow answering ``push`` has to skip it on a fork, which only re-tests
    code the upstream repository has already tested.
    """

    @classproperty
    def fork_push_condition(cls) -> str:
        """
        The condition that skips a job on a push to a fork. Read off the event, so no
        repository is named.
        """
        return "github.event_name != 'push' || !github.event.repository.fork"

    @classproperty
    def label_reference(cls) -> str:
        """
        What a job answering ``labeled`` compares to run only for the labels it is about.
        """
        return "github.event.label.name"

    def differences_from(self, other: WorkflowLimits) -> dict[str, Any]:
        """
        :param other: The limits compared against.
        :return: The limits whose value here differs from the other's, keyed by field
            name.
        """
        own, others = dataclasses.asdict(self), dataclasses.asdict(other)
        return {name: value for name, value in own.items() if others[name] != value}

    def fitting(self, workflow: Workflow) -> WorkflowLimits:
        """
        :param workflow: A workflow.
        :return: These limits, raised just as far as the workflow needs to keep to them
            where a limit can be raised.
        """
        timeouts = [job.timeout_minutes for job in workflow.jobs if job.timeout_minutes]
        jobs = workflow.jobs_per_run if workflow.runs_on_every_push else None
        return dataclasses.replace(
            self,
            job_timeout_minutes=max([self.job_timeout_minutes, *timeouts]),
            jobs_per_push_run=max(self.jobs_per_push_run, jobs or 0),
            skips_push_on_fork=self.skips_push_on_fork
            and not self._unguarded_fork_pushes(workflow),
        )

    def violations_of(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: A workflow held to these limits.
        :return: Every way it breaks them, in the order the rules are listed here.
        """
        return (
            *self._schedule_violations(workflow),
            *self._cancellation_violations(workflow),
            *self._timeout_violations(workflow),
            *self._guard_violations(workflow),
            *self._job_count_violations(workflow),
        )

    def _schedule_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: A workflow held to these limits.
        :return: The schedule violation, if the workflow runs on one.
        """
        if TriggerEvent.SCHEDULE not in workflow.events:
            return ()
        return (ScheduledWorkflow(workflow=workflow.file_name),)

    def _cancellation_violations(
        self, workflow: Workflow
    ) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: A workflow held to these limits.
        :return: The violation of a workflow that runs on every pull-request push
            without cancelling the run for the commit before.
        """
        if not any(
            trigger.runs_on_every_pull_request_push for trigger in workflow.triggers
        ):
            return ()
        if workflow.concurrency is not None and workflow.concurrency.cancel_in_progress:
            return ()
        return (MissingPullRequestCancellation(workflow=workflow.file_name),)

    def _timeout_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: A workflow held to these limits.
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

    def _unguarded_fork_pushes(self, workflow: Workflow) -> tuple[str, ...]:
        """
        :param workflow: A workflow.
        :return: The first jobs that run on a push to a fork, when the workflow answers
            ``push``.
        """
        if TriggerEvent.PUSH not in workflow.events:
            return ()
        return tuple(
            job.identifier
            for job in workflow.first_jobs
            if self.fork_push_condition not in job.condition
        )

    def _guard_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: A workflow held to these limits.
        :return: First jobs missing the fork condition or a label check.
        """
        unguarded_push = tuple(
            MissingForkGuard(
                workflow=workflow.file_name,
                job=job,
                condition=self.fork_push_condition,
            )
            for job in (
                self._unguarded_fork_pushes(workflow) if self.skips_push_on_fork else ()
            )
        )
        answers_labels = any(
            ActivityType.LABELED in trigger.activity_types
            for trigger in workflow.triggers
        )
        unguarded_label = tuple(
            MissingLabelGuard(workflow=workflow.file_name, job=job.identifier)
            for job in (workflow.first_jobs if answers_labels else ())
            if self.label_reference not in job.condition
        )
        return (*unguarded_push, *unguarded_label)

    def _job_count_violations(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: A workflow held to these limits.
        :return: The violation of a workflow running on every push with more jobs than
            allowed, or with jobs that cannot be counted.
        """
        if not workflow.runs_on_every_push:
            return ()
        jobs = workflow.jobs_per_run
        if jobs is None:
            return (UncountableJobs(workflow=workflow.file_name),)
        if jobs <= self.jobs_per_push_run:
            return ()
        return (
            TooManyJobsOnEveryPush(
                workflow=workflow.file_name,
                jobs=jobs,
                ceiling=self.jobs_per_push_run,
            ),
        )


# %% the budget file


@dataclass(frozen=True)
class ActionsBudget:
    """
    A repository's budget: the limits every workflow is held to, and the workflows
    whose own limits differ.
    """

    defaults: WorkflowLimits = field(default_factory=WorkflowLimits)
    """
    The limits of every workflow :attr:`overrides` does not name.
    """

    overrides: Mapping[str, WorkflowLimits] = field(default_factory=dict)
    """
    The limits of the workflows whose own differ from :attr:`defaults`, by file name.
    """

    @classmethod
    def from_file(cls, path: Path) -> ActionsBudget:
        """
        :param path: A budget file.
        :return: The budget it sets.
        """
        settings = tomllib.loads(path.read_text())
        overrides = settings.pop(BudgetKey.WORKFLOW, {})
        defaults = dataclasses.replace(WorkflowLimits(), **settings)
        return cls(
            defaults=defaults,
            overrides={
                file_name: dataclasses.replace(defaults, **limits)
                for file_name, limits in overrides.items()
            },
        )

    @classmethod
    def load(cls) -> ActionsBudget:
        """
        :return: The repository's own budget, or basstler's defaults when the repository
            has no budget file.
        """
        path = PackageLocation.REPOSITORY_ROOT / ProjectLocation.ACTIONS_BUDGET
        if not path.exists():
            return cls()
        return cls.from_file(path)

    @classmethod
    def baseline_for(
        cls, workflows: Iterable[Workflow], defaults: WorkflowLimits
    ) -> ActionsBudget:
        """
        :param workflows: The workflows the budget is for.
        :param defaults: The limits every workflow is held to.
        :return: A budget naming each workflow that needs a limit raised to keep to it,
            with that limit raised just as far as it needs.
        """
        fitted = {
            workflow.file_name: defaults.fitting(workflow) for workflow in workflows
        }
        return cls(
            defaults=defaults,
            overrides={
                file_name: limits
                for file_name, limits in fitted.items()
                if limits != defaults
            },
        )

    def limits_of(self, file_name: str) -> WorkflowLimits:
        """
        :param file_name: A workflow's file name.
        :return: The limits it is held to.
        """
        return self.overrides.get(file_name, self.defaults)

    def violations_of(self, workflow: Workflow) -> tuple[BudgetViolation, ...]:
        """
        :param workflow: Any workflow.
        :return: Every way it breaks this budget.
        """
        return self.limits_of(workflow.file_name).violations_of(workflow)

    def write(self, path: Path) -> None:
        """
        Write this budget as a new budget file.

        :param path: Where the file goes; nothing may exist there yet.
        """
        if path.exists():
            raise BudgetFileExists(path=path)
        template = create_template_environment().get_template(BudgetTemplate.FILE.value)
        path.write_text(
            template.render(
                defaults=dataclasses.asdict(self.defaults),
                overrides={
                    file_name: limits.differences_from(self.defaults)
                    for file_name, limits in sorted(self.overrides.items())
                },
                workflow_key=BudgetKey.WORKFLOW,
            )
        )


# %% writing the repository's budget


def main() -> None:
    """
    Write the repository's budget file, raising basstler's default limits just as far as
    each of its workflows needs today.
    """
    argparse.ArgumentParser(description=main.__doc__).parse_args()
    ActionsBudget.baseline_for(
        Workflow.every_workflow_in_the_repository(), WorkflowLimits()
    ).write(PackageLocation.REPOSITORY_ROOT / ProjectLocation.ACTIONS_BUDGET)


if __name__ == "__main__":
    main()
