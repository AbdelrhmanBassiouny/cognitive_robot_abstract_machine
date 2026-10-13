"""
The ways a workflow, or the budget manifest itself, can break the Actions budget.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from basstler.locations import PackageLocation

if TYPE_CHECKING:
    from basstler.workflows import Concurrency, Trigger, TriggerEvent

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

    condition: str
    """
    The condition the job has to carry.
    """

    def error_message(self) -> str:
        return f"job {self.job} does not skip a push to a fork: if: {self.condition}"


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

    condition: str
    """
    The condition the job has to carry.
    """

    def error_message(self) -> str:
        return f"job {self.job} runs for any label: if: {self.condition}"


# %% manifest errors


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
