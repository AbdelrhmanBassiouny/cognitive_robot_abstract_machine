"""
The ways a workflow can break the Actions budget, and the ways writing a budget file can
fail.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# %% budget violations


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
class ScheduledWorkflow(BudgetViolation):
    """
    The workflow runs on a schedule, which nothing in this repository may.
    """

    def error_message(self) -> str:
        return "runs on a schedule; trigger it on the event it is waiting for instead"


@dataclass
class MissingPullRequestCancellation(BudgetViolation):
    """
    The workflow runs on every push to a pull request without cancelling the run for the
    commit before.
    """

    def error_message(self) -> str:
        return "runs on every pull-request push without cancel-in-progress concurrency"


@dataclass
class MissingJobTimeout(BudgetViolation):
    """
    A job that takes a runner declares no ``timeout-minutes``, so a hang holds the
    runner for GitHub's six-hour default.
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
    A job's ``timeout-minutes`` is above the workflow's ceiling.
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
    The workflow's ceiling.
    """

    def error_message(self) -> str:
        return (
            f"job {self.job} times out after {self.timeout_minutes} minutes, "
            f"above the ceiling of {self.ceiling_minutes}"
        )


@dataclass
class MissingForkGuard(BudgetViolation):
    """
    A first job of a workflow answering ``push`` does not skip a push to a fork.
    """

    job: str
    """
    The job's key.
    """

    condition: str
    """
    The condition the job has to carry.
    """

    def error_message(self) -> str:
        return f"job {self.job} does not skip a push to a fork: if: {self.condition}"


@dataclass
class MissingLabelGuard(BudgetViolation):
    """
    A first job of a workflow answering ``labeled`` runs for any label, without
    comparing the one added.
    """

    job: str
    """
    The job's key.
    """

    def error_message(self) -> str:
        return f"job {self.job} runs for any label; compare github.event.label.name"


@dataclass
class TooManyJobsOnEveryPush(BudgetViolation):
    """
    A workflow running on every push takes runners for more jobs a run than its ceiling
    allows.
    """

    jobs: int
    """
    The most jobs one run takes runners for.
    """

    ceiling: int
    """
    The workflow's ceiling.
    """

    def error_message(self) -> str:
        return (
            f"runs up to {self.jobs} jobs on every push, above the ceiling of "
            f"{self.ceiling}; narrow its triggers or raise its jobs_per_push_run"
        )


@dataclass
class UncountableJobs(BudgetViolation):
    """
    A workflow running on every push has jobs whose number is only known at run time, so
    its ceiling cannot be checked.
    """

    def error_message(self) -> str:
        return (
            "runs on every push with a matrix computed at run time or a reusable "
            "workflow from another repository, so its jobs cannot be counted"
        )


# %% budget file errors


@dataclass
class BudgetFileExists(FileExistsError):
    """
    A budget file is already where a new one would be written.

    Once written, the file is reviewed by hand, so writing over it would bless whatever
    the workflows do now.
    """

    path: Path
    """
    The existing file.
    """

    def __str__(self) -> str:
        """
        :return: What is in the way.
        """
        return f"{self.path} already exists; edit it instead of writing a new one"
