"""
A workflow file, read into the triggers, concurrency and jobs it declares.

YAML 1.1 reads a bare ``on`` key as the boolean true, so the trigger block is looked up
under both; everything else is read under the key GitHub documents.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from basstler.locations import PackageLocation, ProjectLocation

# %% vocabulary


class TriggerEvent(StrEnum):
    """
    The events a workflow in this repository answers to, as its trigger block names them.
    """

    PUSH = "push"
    """
    A push to a branch.
    """

    PULL_REQUEST = "pull_request"
    """
    A pull request event, whose activity types say which.
    """

    WORKFLOW_DISPATCH = "workflow_dispatch"
    """
    Started by hand or through the API.
    """

    WORKFLOW_CALL = "workflow_call"
    """
    Run as a job of another workflow, which is what makes a workflow reusable.
    """

    WORKFLOW_RUN = "workflow_run"
    """
    Another workflow's run reaching the activity types named.
    """

    SCHEDULE = "schedule"
    """
    A cron entry. Read so that a workflow carrying one can be reported; never declared.
    """


class ActivityType(StrEnum):
    """
    The activity types a trigger in this repository narrows its event to.
    """

    OPENED = "opened"
    """
    A pull request was opened.
    """

    REOPENED = "reopened"
    """
    A closed pull request was reopened.
    """

    SYNCHRONIZE = "synchronize"
    """
    A pull request's head branch was pushed to.
    """

    READY_FOR_REVIEW = "ready_for_review"
    """
    A draft pull request was marked ready for review.
    """

    CONVERTED_TO_DRAFT = "converted_to_draft"
    """
    A pull request was converted back to a draft.
    """

    LABELED = "labeled"
    """
    A label was added to a pull request.
    """

    CLOSED = "closed"
    """
    A pull request was closed, merged or not.
    """

    COMPLETED = "completed"
    """
    A watched workflow's run finished.
    """


DEFAULT_PULL_REQUEST_ACTIVITY_TYPES = frozenset(
    {ActivityType.OPENED, ActivityType.SYNCHRONIZE, ActivityType.REOPENED}
)
"""
What GitHub runs a ``pull_request`` workflow on when the trigger names no types.
"""


class WorkflowKey(StrEnum):
    """
    The keys of a workflow file this module reads.
    """

    TRIGGERS = "on"
    """
    The trigger block, which YAML 1.1 reads under the boolean true instead.
    """

    TYPES = "types"
    """
    A trigger's activity types.
    """

    BRANCHES = "branches"
    """
    A trigger's branch filters.
    """

    CONCURRENCY = "concurrency"
    """
    The workflow's concurrency, a bare group or a mapping.
    """

    GROUP = "group"
    """
    A concurrency mapping's group.
    """

    CANCEL_IN_PROGRESS = "cancel-in-progress"
    """
    Whether a new run in the group cancels the one in progress.
    """

    JOBS = "jobs"
    """
    The workflow's jobs, by key.
    """

    RUNS_ON = "runs-on"
    """
    The runner a job takes, absent on a job calling a reusable workflow.
    """

    TIMEOUT_MINUTES = "timeout-minutes"
    """
    How long a job may run.
    """

    NEEDS = "needs"
    """
    The jobs a job waits for.
    """

    CONDITION = "if"
    """
    A job's condition.
    """


# %% what a workflow declares


@dataclass(frozen=True)
class Trigger:
    """
    One event a workflow answers to, narrowed by its filters.
    """

    event: TriggerEvent
    """
    The event.
    """

    activity_types: frozenset[ActivityType] = frozenset()
    """
    The activity types named, or empty when the trigger names none.
    """

    branches: frozenset[str] = frozenset()
    """
    The branch filters named, or empty when the trigger names none.
    """

    @property
    def runs_on_every_push(self) -> bool:
        """
        :return: Whether this is a pull-request trigger that runs on each push to the pull
            request, which is when a newer run makes an older one worthless.
        """
        if self.event is not TriggerEvent.PULL_REQUEST:
            return False
        activity_types = self.activity_types or DEFAULT_PULL_REQUEST_ACTIVITY_TYPES
        return ActivityType.SYNCHRONIZE in activity_types

    @classmethod
    def from_workflow(cls, event: str, filters: Any) -> Trigger:
        """
        :param event: The event's key in the trigger block.
        :param filters: What the key holds: a mapping of filters, nothing for an
            unfiltered trigger, or a schedule's list of cron entries.
        :return: The trigger.
        """
        if not isinstance(filters, Mapping):
            filters = {}
        return cls(
            event=TriggerEvent(event),
            activity_types=frozenset(
                ActivityType(activity_type)
                for activity_type in filters.get(WorkflowKey.TYPES, ())
            ),
            branches=frozenset(filters.get(WorkflowKey.BRANCHES, ())),
        )


@dataclass(frozen=True)
class Concurrency:
    """
    The group a workflow's runs queue in, and whether a new run cancels the one before.
    """

    group: str
    """
    The group expression, as written.
    """

    cancel_in_progress: bool
    """
    Whether a new run in the group cancels the one in progress.
    """

    @classmethod
    def from_workflow(cls, declared: str | Mapping[str, Any]) -> Concurrency:
        """
        :param declared: The ``concurrency`` value, either a bare group or a mapping.
        :return: The concurrency.
        """
        if isinstance(declared, str):
            return cls(group=declared, cancel_in_progress=False)
        return cls(
            group=declared[WorkflowKey.GROUP],
            cancel_in_progress=declared.get(WorkflowKey.CANCEL_IN_PROGRESS, False),
        )


@dataclass(frozen=True)
class Job:
    """
    One job of a workflow, as far as the budget is concerned.
    """

    identifier: str
    """
    The job's key under ``jobs``.
    """

    runs_on_a_runner: bool
    """
    Whether the job takes a runner itself, rather than calling a reusable workflow whose
    own jobs do.
    """

    timeout_minutes: int | None
    """
    The job's ``timeout-minutes``, or none when it declares none.
    """

    needs: tuple[str, ...]
    """
    The jobs this one waits for.
    """

    condition: str
    """
    The job's ``if`` condition, or empty when it has none.
    """

    @classmethod
    def from_workflow(cls, identifier: str, declared: Mapping[str, Any]) -> Job:
        """
        :param identifier: The job's key.
        :param declared: The job's mapping.
        :return: The job.
        """
        needs = declared.get(WorkflowKey.NEEDS, ())
        return cls(
            identifier=identifier,
            runs_on_a_runner=WorkflowKey.RUNS_ON in declared,
            timeout_minutes=declared.get(WorkflowKey.TIMEOUT_MINUTES),
            needs=(needs,) if isinstance(needs, str) else tuple(needs),
            condition=str(declared.get(WorkflowKey.CONDITION, "")),
        )


@dataclass(frozen=True)
class Workflow:
    """
    A workflow file, read into what the budget holds it to.
    """

    file_name: str
    """
    The file's name, which is how the manifest refers to it.
    """

    triggers: tuple[Trigger, ...]
    """
    The events it answers to, in the order the file names them.
    """

    concurrency: Concurrency | None
    """
    Its concurrency, or none when it declares none.
    """

    jobs: tuple[Job, ...]
    """
    Its jobs, in the order the file names them.
    """

    @classmethod
    def at(cls, path: Path) -> Workflow:
        """
        :param path: The workflow file.
        :return: The workflow.
        """
        declared = yaml.safe_load(path.read_text())
        # YAML 1.1 reads a bare ``on`` key as the boolean true.
        triggers = declared.get(True, declared.get(WorkflowKey.TRIGGERS))
        if isinstance(triggers, str):
            triggers = [triggers]
        if isinstance(triggers, list):
            triggers = {event: None for event in triggers}
        concurrency = declared.get(WorkflowKey.CONCURRENCY)
        return cls(
            file_name=path.name,
            triggers=tuple(
                Trigger.from_workflow(event, filters)
                for event, filters in triggers.items()
            ),
            concurrency=(
                None if concurrency is None else Concurrency.from_workflow(concurrency)
            ),
            jobs=tuple(
                Job.from_workflow(identifier, job)
                for identifier, job in declared[WorkflowKey.JOBS].items()
            ),
        )

    @classmethod
    def every_workflow_in_the_repository(cls) -> tuple[Workflow, ...]:
        """
        :return: Every workflow GitHub runs from this checkout, in file name order.
        """
        directory = PackageLocation.REPOSITORY_ROOT / ProjectLocation.WORKFLOWS
        return tuple(cls.at(path) for path in sorted(directory.glob("*.yml")))

    @property
    def events(self) -> frozenset[TriggerEvent]:
        """
        :return: The events this workflow answers to.
        """
        return frozenset(trigger.event for trigger in self.triggers)

    def trigger(self, event: TriggerEvent) -> Trigger:
        """
        :param event: An event this workflow answers to.
        :return: Its trigger for that event.
        """
        return next(trigger for trigger in self.triggers if trigger.event is event)

    @property
    def first_jobs(self) -> tuple[Job, ...]:
        """
        :return: The jobs that wait for no other, which are the ones a skip has to be
            written on.
        """
        return tuple(job for job in self.jobs if not job.needs)
