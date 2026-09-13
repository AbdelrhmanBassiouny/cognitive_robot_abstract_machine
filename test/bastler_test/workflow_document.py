"""
A GitHub Actions workflow, parsed once into something with names.

A workflow is YAML, so everything in it is reachable as nested string keys, and every
assertion that reaches for one spells the same keys again. Parsing it here means a job,
a step, a trigger and the permissions a run holds are named once and a test asks the
model rather than the mapping.

Deliberately sized to what these tests check, not a general workflow model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml


class WorkflowKey(StrEnum):
    """
    The top-level keys of a workflow document.
    """

    JOBS = "jobs"
    """
    The jobs it runs, keyed by identifier.
    """

    CONCURRENCY = "concurrency"
    """
    How runs of it queue against each other.
    """

    PERMISSIONS = "permissions"
    """
    What the run's own token may do.
    """


TRIGGERS_KEY = True
"""
Where the trigger block is found once the document is parsed.

An unquoted ``on:`` is YAML's boolean ``true``, which is the shape the file on disk
actually has - so this is the key rather than the word "on".
"""


class ConcurrencyKey(StrEnum):
    """
    The concurrency block's own keys.
    """

    CANCEL_IN_PROGRESS = "cancel-in-progress"
    """
    Whether a superseded run is cancelled rather than queued behind the new one.
    """


class JobKey(StrEnum):
    """
    The keys of one job.
    """

    STEPS = "steps"
    """
    What the job runs, in order.
    """

    CONDITION = "if"
    """
    What has to hold for the job to run at all.
    """

    ENVIRONMENT = "environment"
    """
    The deployment environment the job runs against, whose protection rules are exactly
    what the site's publishing route avoids.
    """


class StepKey(StrEnum):
    """
    The keys of one step.
    """

    USES = "uses"
    """
    The action the step runs, when it runs one.
    """

    INPUTS = "with"
    """
    What that action is given.
    """


class CheckoutInput(StrEnum):
    """
    The inputs the checkout step is given.
    """

    REFERENCE = "ref"
    """
    The branch or commit to check out, which this workflow deliberately leaves unset.
    """

    FETCH_DEPTH = "fetch-depth"
    """
    How much history to fetch; zero for all of it.
    """


class TriggerEvent(StrEnum):
    """
    The events this workflow answers to.
    """

    PULL_REQUEST = "pull_request"
    """
    A pull request moving between the states a dashboard classifies items by.
    """

    PUSH = "push"
    """
    A change landing on a watched branch under a watched path.
    """

    WORKFLOW_DISPATCH = "workflow_dispatch"
    """
    Started by hand or by an API call, which is how a manifest edit is answered.
    """


class TriggerKey(StrEnum):
    """
    The keys inside one event's own block.
    """

    ACTIVITY_TYPES = "types"
    """
    Which activities of that event count.
    """

    PATHS = "paths"
    """
    Which changed paths count.
    """


class PullRequestActivity(StrEnum):
    """
    The pull request activities a dashboard's classification can change on.
    """

    OPENED = "opened"
    """
    A new item gains a pull request.
    """

    REOPENED = "reopened"
    """
    A closed one comes back.
    """

    READY_FOR_REVIEW = "ready_for_review"
    """
    A draft becomes reviewable.
    """

    CONVERTED_TO_DRAFT = "converted_to_draft"
    """
    A reviewable one goes back to draft.
    """

    CLOSED = "closed"
    """
    One merges or is closed unmerged.
    """


class Permission(StrEnum):
    """
    The permissions this workflow's token needs.
    """

    CONTENTS = "contents"
    """
    Pushing the site branch and the merged-to-done manifest correction.
    """

    PAGES = "pages"
    """
    Pointing Pages at the site branch.
    """


class PermissionLevel(StrEnum):
    """
    What a permission grants.
    """

    WRITE = "write"
    """
    Enough to push and to configure.
    """


DEPLOY_PAGES_ACTION = "actions/deploy-pages"
"""
The environment deployment a pull request run is never allowed to make.
"""


@dataclass(frozen=True)
class WorkflowStep:
    """
    One step of a job.
    """

    body: dict[str, Any]
    """
    The step's own mapping.
    """

    @property
    def uses(self) -> str:
        """:return: The action it runs, empty when it runs a script instead."""
        return self.body.get(StepKey.USES, "")

    def given(self, name: CheckoutInput) -> Any:
        """
        :param name: The input to read.
        :return: What the action was given for it, or ``None`` when it was not given.
        """
        return self.body.get(StepKey.INPUTS, {}).get(name)

    def is_given(self, name: CheckoutInput) -> bool:
        """
        :param name: The input to look for.
        :return: Whether the step names it at all.
        """
        return name in self.body.get(StepKey.INPUTS, {})


@dataclass(frozen=True)
class WorkflowJob:
    """
    One job of a workflow.
    """

    body: dict[str, Any]
    """
    The job's own mapping.
    """

    @property
    def steps(self) -> tuple[WorkflowStep, ...]:
        """:return: Its steps, in order."""
        return tuple(WorkflowStep(step) for step in self.body[JobKey.STEPS])

    @property
    def condition(self) -> str:
        """:return: What has to hold for it to run, empty when nothing does."""
        return self.body.get(JobKey.CONDITION, "")

    @property
    def deploys_to_an_environment(self) -> bool:
        """:return: Whether it names a deployment environment."""
        return JobKey.ENVIRONMENT in self.body

    def runs(self, action: str) -> bool:
        """
        :param action: The action to look for.
        :return: Whether any step runs it.
        """
        return any(action in step.uses for step in self.steps)


@dataclass(frozen=True)
class WorkflowDocument:
    """
    One parsed workflow file.
    """

    path: Path
    """
    Where it was read from.
    """

    @cached_property
    def body(self) -> dict[str, Any]:
        """:return: The parsed document."""
        return yaml.safe_load(self.path.read_text())

    @property
    def text(self) -> str:
        """:return: The file's own source, for what parsing cannot see."""
        return self.path.read_text()

    @property
    def triggers(self) -> dict[str, Any]:
        """:return: The events it fires on."""
        return self.body[TRIGGERS_KEY]

    def answers_to(self, event: TriggerEvent) -> bool:
        """
        :param event: The event to look for.
        :return: Whether the workflow fires on it.
        """
        return event in self.triggers

    def trigger(self, event: TriggerEvent) -> dict[str, Any]:
        """
        :param event: The event whose block is wanted.
        :return: That event's own configuration.
        """
        return self.triggers[event]

    def job(self, identifier: str) -> WorkflowJob:
        """
        :param identifier: The job to read.
        :return: That job.
        """
        return WorkflowJob(self.body[WorkflowKey.JOBS][identifier])

    @property
    def permissions(self) -> dict[str, str]:
        """:return: What the run's token may do."""
        return self.body[WorkflowKey.PERMISSIONS]

    @property
    def cancels_superseded_runs(self) -> bool:
        """:return: Whether a superseded run is cancelled rather than queued."""
        return self.body[WorkflowKey.CONCURRENCY][ConcurrencyKey.CANCEL_IN_PROGRESS]
