"""
This repository's workflow files, parsed once into something with names.

A workflow is YAML, so everything in it is reachable as nested string keys - and every
reader that reaches for one spells the same keys again. Parsing it here means a job, a
step, a trigger and the action a step uses are named once, and a reader asks the model
rather than the mapping.

It is also what lets the tooling read a fact the workflows already state rather than
restating it: the libraries the matrix runs a job for are declared in ``ci.yml``, so
nothing here has to list them a second time and go stale when one is added.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

REPOSITORY_ROOT = Path(__file__).parent.parent.parent
"""
The checkout these workflows belong to, from this module's own location.
"""

WORKFLOW_DIRECTORY = REPOSITORY_ROOT / ".github" / "workflows"
"""
Where GitHub looks for a workflow, and so where one is read from.
"""

CALLED_JOB_SEPARATOR = " / "
"""
What GitHub puts between a job that calls a reusable workflow and the called workflow's
own job, when it names the check the pair reports.
"""


def every_workflow_file() -> tuple[Path, ...]:
    """
    Every workflow GitHub runs from this checkout.

    The top level only, which is where GitHub looks: the per-library directories beside
    them hold files it never starts.

    :return: The workflow files, in name order.
    """
    return tuple(sorted(WORKFLOW_DIRECTORY.glob("*.yml")))


# %% the files, and what is in them


class WorkflowFile(StrEnum):
    """
    The workflows this tooling dispatches, reuses or is checked against.

    A file name rather than a numeric identifier: it is what the dispatch endpoint takes,
    and it stays readable in a repository that has never dispatched one.
    """

    CONTINUOUS_INTEGRATION = "ci.yml"
    """
    The matrix a candidate's verdict comes from, and where the libraries are declared.
    """

    REUSABLE_LIBRARY_JOB = "ci_reusable.yml"
    """
    One library's tests over one tree, called by the matrix and by a probe alike.
    """

    INTEGRATION_PROBE = "integration-probe.yml"
    """
    One library's tests over one assembled prefix, dispatched to localise a red.
    """

    INTEGRATION_REFRESH = "integration-refresh.yml"
    """
    The scheduled rebuild that publishes the integration branch.
    """

    @property
    def path(self) -> Path:
        """:return: Where this workflow is read from."""
        return WORKFLOW_DIRECTORY / str(self)

    def read(self) -> WorkflowDocument:
        """:return: The parsed workflow."""
        return WorkflowDocument.at(self.path)


class TriggerEvent(StrEnum):
    """
    The events a workflow can answer to, as its trigger block names them.
    """

    SCHEDULE = "schedule"
    """
    A cron entry, evaluated in UTC.
    """

    PULL_REQUEST = "pull_request"
    """
    A pull request opened, updated, or - what a rebuild answers to - taken out of draft.
    """

    WORKFLOW_DISPATCH = "workflow_dispatch"
    """
    Started by hand or by an API call, which is how a probe is asked for.
    """

    WORKFLOW_CALL = "workflow_call"
    """
    Run as a job of another workflow, which is what makes one reusable.
    """

    WORKFLOW_RUN = "workflow_run"
    """
    Another workflow's run reaching an end, named by that workflow's name rather than
    by its file.

    Its run always starts on the default branch, whichever branch the run it answers to
    was about - so the workflow answering has to be the copy published there.
    """


class ActivityType(StrEnum):
    """
    The particular activities of an event a workflow narrows itself to.

    An event declared bare answers to all of them, so naming one is how a workflow says
    it wants a pull request at one moment of its life rather than at every push to it.
    """

    READY_FOR_REVIEW = "ready_for_review"
    """
    A draft taken out of draft, which is when a branch becomes integrable at all.
    """

    COMPLETED = "completed"
    """
    A run that has finished, however it finished.

    Narrowing to it rather than to a conclusion, because a red candidate is as much an
    answer to act on as a green one.
    """


class GitHubContext(StrEnum):
    """
    The context expressions a workflow reads a fact about its own run out of.
    """

    DEFAULT_BRANCH = "github.event.repository.default_branch"
    """
    The branch a repository hands out by default, which is where a published pipeline
    lives.
    """

    REFERENCE = "github.ref"
    """
    What the run was started on, which is the tooling a dispatch is trying out.
    """

    REPOSITORY = "github.repository"
    """
    The repository the run belongs to.
    """

    PULL_REQUEST_HEAD_REPOSITORY = "github.event.pull_request.head.repo.full_name"
    """
    Where a pull request's branch lives, which is a fork's own repository when the pull
    request came from one.
    """


class Action(StrEnum):
    """
    The published actions a step can use, without its version suffix.

    A step names one as ``<action>@<version>``, so a reader looking for the checkout
    matches on the half that does not move.
    """

    CHECKOUT = "actions/checkout"
    """
    Puts a tree in the runner's working directory.
    """

    SETUP_PYTHON = "actions/setup-python"
    """
    Puts an interpreter on the path.
    """


class CheckoutInput(StrEnum):
    """
    What :attr:`Action.CHECKOUT` can be told.
    """

    REFERENCE = "ref"
    """
    The tree to put in the runner's working directory.
    """


class ReusableJobInput(StrEnum):
    """
    What the reusable library job can be told, beyond which library to run.
    """

    REFERENCE = "ref"
    """
    The tree to check out and test, which is what lets a caller judge one it did not
    itself start on.
    """


class MatrixKey(StrEnum):
    """
    The keys a matrix entry is read through.
    """

    LIBRARY = "lib"
    """
    Which library the entry runs the tests of.
    """


# %% the model


@dataclass(frozen=True)
class StepArgument:
    """
    An argument a step passes on to what it runs, taking its value from a variable.
    """

    variable: str
    """
    The variable holding the value.
    """

    argument: str
    """
    What names the value to whatever the step runs.
    """


@dataclass(frozen=True)
class PassedArgument(StepArgument):
    """
    An argument a step always passes, quoted so an empty or spaced value stays one
    argument.
    """

    def __str__(self) -> str:
        return f'{self.argument} "${{{self.variable}}}"'


@dataclass(frozen=True)
class OptionalArgument(StepArgument):
    """
    An argument a step passes only when the variable carrying its value is set.

    The shell's alternate-value expansion is what drops it otherwise, so an input nobody
    filled in never reaches the command as a flag with no value behind it.
    """

    def __str__(self) -> str:
        return f"${{{self.variable}:+{PassedArgument(self.variable, self.argument)}}}"


@dataclass(frozen=True)
class WorkflowInput:
    """
    One input a workflow declares, asked for what it says rather than read as a mapping.
    """

    name: str
    """
    What a caller names it.
    """

    declared: Mapping[str, Any]
    """
    The input as the file declares it.
    """

    @property
    def default(self) -> Any:
        """:return: What it is given when a caller names none."""
        return self.declared.get("default")

    @property
    def is_required(self) -> bool:
        """:return: Whether a caller has to name it."""
        return bool(self.declared.get("required", False))

    @property
    def description(self) -> str:
        """:return: What it is for, as a caller is shown it."""
        return str(self.declared.get("description", ""))


@dataclass(frozen=True)
class WorkflowStep:
    """
    One step of a job, asked for what it does rather than read as a mapping.
    """

    declared: Mapping[str, Any]
    """
    The step as the file declares it.
    """

    @property
    def uses(self) -> str:
        """:return: The action or workflow this step runs, empty when it runs a script."""
        return str(self.declared.get("uses", ""))

    @property
    def script(self) -> str:
        """:return: The shell this step runs, empty when it uses an action."""
        return str(self.declared.get("run", ""))

    @property
    def identifier(self) -> str:
        """:return: The step's own ``id``, empty when nothing refers to it."""
        return str(self.declared.get("id", ""))

    @property
    def condition(self) -> str:
        """:return: What decides whether this step runs at all, empty when nothing does."""
        return str(self.declared.get("if", ""))

    @property
    def tolerates_its_own_failure(self) -> bool:
        """
        Whether this step failing leaves the job running.

        A step declared this way is asking a question rather than doing the work: what it
        answered is read from its outcome by whatever runs next.

        :return: Whether the job carries on past it.
        """
        return bool(self.declared.get("continue-on-error", False))

    @property
    def inputs(self) -> Mapping[str, Any]:
        """:return: What the step passes to whatever it uses."""
        return self.declared.get("with", {})

    @property
    def environment(self) -> Mapping[str, Any]:
        """:return: The variables this step is given."""
        return self.declared.get("env", {})

    def runs(self, action: Action) -> bool:
        """:param action: The action to test for.
        :return: Whether this step uses it, whatever version it pins."""
        return self.uses.startswith(str(action))

    def variable(self, named: str) -> str:
        """:param named: The variable wanted.
        :return: What this step gives it, empty when it gives it nothing."""
        return str(self.environment.get(named, ""))

    def given(self, named: str) -> str:
        """:param named: The input wanted.
        :return: What this step passes for it, empty when it passes nothing."""
        return str(self.inputs.get(named, ""))

    def passes(self, argument: StepArgument) -> bool:
        """:param argument: The argument to test for.
        :return: Whether this step's shell passes it that way."""
        return str(argument) in self.script


@dataclass(frozen=True)
class WorkflowJob:
    """
    One job of a workflow, asked for its steps and for what it calls.
    """

    identifier: str
    """
    The job's key, which is how the rest of the file refers to it.
    """

    declared: Mapping[str, Any]
    """
    The job as the file declares it.
    """

    @property
    def steps(self) -> tuple[WorkflowStep, ...]:
        """:return: Its steps in order, none when it calls a reusable workflow instead."""
        return tuple(WorkflowStep(step) for step in self.declared.get("steps", ()))

    @property
    def name(self) -> str:
        """
        What a check reported for this job is called: its declared name where it has
        one, and otherwise its key.

        :return: The job's name.
        """
        return str(self.declared.get("name", self.identifier))

    @property
    def calls(self) -> str:
        """:return: The reusable workflow this job is, empty when it has its own steps."""
        return str(self.declared.get("uses", ""))

    def reports(self, check_name: str) -> bool:
        """
        Whether a check of that name came from this job.

        A job with steps of its own reports one check under its own name; one that calls
        a reusable workflow reports the called workflow's jobs beneath it, each named
        after both.

        :param check_name: A check reported against some commit.
        :return: Whether this job is what reported it.
        """
        return check_name == self.name or check_name.startswith(
            f"{self.name}{CALLED_JOB_SEPARATOR}"
        )

    @property
    def inputs(self) -> Mapping[str, Any]:
        """:return: What it passes to the workflow it calls."""
        return self.declared.get("with", {})

    @property
    def condition(self) -> str:
        """:return: What decides whether this job runs, empty when nothing does."""
        return str(self.declared.get("if", ""))

    @property
    def matrix_entries(self) -> tuple[Mapping[str, Any], ...]:
        """:return: The matrix this job fans out over, empty when it does not."""
        matrix = self.declared.get("strategy", {}).get("matrix", {})
        return tuple(matrix.get("include", ()))

    def step_using(self, action: Action) -> WorkflowStep:
        """:param action: The action whose step is wanted.
        :return: The first step using it.
        :raises StepNotFoundError: When no step uses it."""
        for step in self.steps:
            if step.runs(action):
                return step
        raise StepNotFoundError(action=action)

    def step(self, step_identifier: str) -> WorkflowStep:
        """:param step_identifier: The step's own ``id``.
        :return: That step.
        :raises StepNotFoundError: When the job has no such step."""
        for found in self.steps:
            if found.identifier == step_identifier:
                return found
        raise StepNotFoundError(action=step_identifier)

    def script_of(self, step_identifier: str) -> str:
        """:param step_identifier: The step's own ``id``.
        :return: The shell that step runs.
        :raises StepNotFoundError: When the job has no such step."""
        return self.step(step_identifier).script


@dataclass(frozen=True)
class WorkflowDocument:
    """
    One parsed workflow, so a reader names what it wants rather than indexing into it.
    """

    declared: Mapping[str, Any]
    """
    The whole document as the file declares it.
    """

    @classmethod
    def at(cls, path: Path) -> WorkflowDocument:
        """:param path: The workflow file to read.
        :return: Its parsed contents."""
        return cls.from_text(path.read_text())

    @classmethod
    def from_text(cls, text: str) -> WorkflowDocument:
        """:param text: A workflow file's contents, from wherever it was read - a
            checkout, or a tree a build is being judged as.
        :return: Its parsed contents."""
        return cls(yaml.safe_load(text))

    @cached_property
    def triggers(self) -> Mapping[str, Any]:
        """
        Read under ``True`` rather than ``"on"``, because YAML reads a bare ``on`` key as
        the boolean and every reader that forgets it looks in an empty mapping.

        :return: The events this workflow answers to.
        """
        return self.declared[True]

    def answers_to(self, event: TriggerEvent) -> bool:
        """:param event: The event to test for.
        :return: Whether this workflow answers to it."""
        return str(event) in self.triggers

    def trigger(self, event: TriggerEvent) -> Mapping[str, Any]:
        """:param event: The event whose declaration is wanted.
        :return: How this workflow answers to it, empty when it is declared bare."""
        return self.triggers[str(event)] or {}

    @property
    def dispatch_inputs(self) -> Mapping[str, WorkflowInput]:
        """:return: What a dispatch has to be told."""
        return self.inputs_for(TriggerEvent.WORKFLOW_DISPATCH)

    def inputs_for(self, event: TriggerEvent) -> Mapping[str, WorkflowInput]:
        """:param event: The event whose inputs are wanted.
        :return: What a run started that way is given, by name."""
        return {
            name: WorkflowInput(name=name, declared=declared or {})
            for name, declared in self.trigger(event).get("inputs", {}).items()
        }

    def activity_types(self, event: TriggerEvent) -> tuple[ActivityType, ...]:
        """
        :param event: The event whose activities are wanted.
        :return: The activities this workflow narrows that event to, empty when it
            answers to all of them.
        """
        return tuple(
            ActivityType(named) for named in self.trigger(event).get("types", ())
        )

    def watched_workflows(self, event: TriggerEvent) -> tuple[str, ...]:
        """
        :param event: The event whose watched workflows are wanted.
        :return: The workflows this one answers to the runs of, by the name each of them
            declares, empty when the event names none.
        """
        return tuple(str(named) for named in self.trigger(event).get("workflows", ()))

    def branches(self, event: TriggerEvent) -> tuple[str, ...]:
        """
        :param event: The event whose branch filter is wanted.
        :return: The branch patterns this workflow narrows that event to, empty when it
            answers about every branch.
        """
        return tuple(
            str(pattern) for pattern in self.trigger(event).get("branches", ())
        )

    @property
    def name(self) -> str:
        """:return: What this workflow is called, which is how another one names it."""
        return str(self.declared["name"])

    @property
    def run_name(self) -> str:
        """:return: What this workflow names its runs, empty when it names them nothing."""
        return str(self.declared.get("run-name", ""))

    @property
    def jobs(self) -> tuple[WorkflowJob, ...]:
        """:return: Every job this workflow declares, in the order it declares them."""
        return tuple(self.job(identifier) for identifier in self.declared["jobs"])

    def job(self, identifier: str) -> WorkflowJob:
        """:param identifier: The job's key.
        :return: That job.
        :raises JobNotFoundError: When the workflow has no such job."""
        jobs = self.declared["jobs"]
        if identifier not in jobs:
            raise JobNotFoundError(identifier=identifier, declared=tuple(jobs))
        return WorkflowJob(identifier=identifier, declared=jobs[identifier])

    def job_whose_script_holds(self, wanted: str) -> WorkflowJob:
        """:param wanted: Something exactly one job's shell contains.
        :return: The job whose shell contains it.
        :raises JobNotFoundError: When no job does."""
        for identifier in self.declared["jobs"]:
            found = self.job(identifier)
            if any(wanted in step.script for step in found.steps):
                return found
        raise JobNotFoundError(identifier=wanted, declared=tuple(self.declared["jobs"]))

    @property
    def job_fanning_out_over_a_matrix(self) -> WorkflowJob:
        """
        Found by having a matrix rather than by name, since what makes it the one is that
        it runs once per entry.

        :return: The job that fans out.
        :raises JobNotFoundError: When no job does.
        """
        for identifier in self.declared["jobs"]:
            found = self.job(identifier)
            if found.matrix_entries:
                return found
        raise JobNotFoundError(
            identifier="a job fanning out over a matrix",
            declared=tuple(self.declared["jobs"]),
        )


# %% refusals


@dataclass
class WorkflowReadError(Exception):
    """
    Base class for a workflow that does not hold what a reader asked it for.
    """

    def __str__(self) -> str:
        return self.error_message()

    def error_message(self) -> str:
        """:return: What was asked for and not found."""
        raise NotImplementedError


@dataclass
class StepNotFoundError(WorkflowReadError):
    """
    Raised when no step of a job does what the caller asked about.
    """

    action: Any
    """
    What was looked for.
    """

    def error_message(self) -> str:
        return f"no step of this job uses {self.action}"


@dataclass
class JobNotFoundError(WorkflowReadError):
    """
    Raised when a workflow has no job under the name asked for.
    """

    identifier: str
    """
    What was looked for.
    """

    declared: Sequence[str]
    """
    The jobs the workflow does declare.
    """

    def error_message(self) -> str:
        return (
            f"no job {self.identifier!r} in this workflow; "
            f"it declares {', '.join(self.declared)}"
        )
