"""
What one execution of a scenario produced: its outcome, how long it took, and the log of
everything that happened while it ran.
"""

from __future__ import annotations

import logging
import time
from abc import ABC
from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import List, Tuple

from coraplex.datastructures.enums import ExecutionType

from experiments.scenarios.scenario import Condition, Perturbation, StepName

logger = logging.getLogger(__name__)


class TrialOutcome(StrEnum):
    """
    Whether a trial reached the goal of the scenario it ran.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"


# %% what happened while a trial ran


@dataclass
class TrialLogEntry(ABC):
    """
    One thing that happened while a trial ran.
    """

    moment: float
    """
    Seconds between the start of the trial and this entry.
    """


@dataclass
class TrialStarted(TrialLogEntry):
    """
    The world was built and the trial began.
    """

    scenario_name: str
    """
    The scenario the trial runs.
    """

    execution_type: ExecutionType
    """
    Whether the trial runs in a simulator or on the robot.
    """


@dataclass
class ConditionApplied(TrialLogEntry):
    """
    A condition switched its knowledge source in the trial's world.
    """

    condition: Condition
    """
    The condition that was applied.
    """


@dataclass
class PerturbationApplied(TrialLogEntry):
    """
    A perturbation changed the trial's world at the step it names.
    """

    perturbation: Perturbation
    """
    The perturbation that was applied.
    """


@dataclass
class StepPerformed(TrialLogEntry):
    """
    A step of the scenario ran.
    """

    step: StepName
    """
    The step that ran.
    """


@dataclass
class TrialFinished(TrialLogEntry):
    """
    The scenario's goal was asked and the trial ended.
    """

    outcome: TrialOutcome
    """
    What the goal said about the world the trial finished in.
    """


@dataclass
class TrialLog:
    """
    Everything that happened while a trial ran, in the order it happened.
    """

    entries: List[TrialLogEntry] = field(default_factory=list)
    """
    The entries recorded so far.
    """

    started_at: float = field(default_factory=time.monotonic)
    """
    Reading of the monotonic clock the trial began at.
    """

    @property
    def elapsed_seconds(self) -> float:
        """
        Seconds between the start of the trial and now.
        """
        return time.monotonic() - self.started_at

    def record(self, entry: TrialLogEntry) -> None:
        """
        Keep an entry and report it to whoever is following the run.

        :param entry: What just happened.
        """
        self.entries.append(entry)
        logger.info("%s", entry)


# %% the trial itself


@dataclass
class Trial:
    """
    One execution of a scenario, under the conditions and perturbations of its run.
    """

    scenario_name: str
    """
    The scenario that was run.
    """

    execution_type: ExecutionType
    """
    Whether it ran in a simulator or on the robot.
    """

    conditions: Tuple[Condition, ...]
    """
    The conditions that were in force.
    """

    perturbations: Tuple[Perturbation, ...]
    """
    The perturbations that were applied.
    """

    outcome: TrialOutcome
    """
    Whether the trial reached the scenario's goal.
    """

    duration: float
    """
    How long the trial took, in seconds.
    """

    log: TrialLog
    """
    Everything that happened while it ran.
    """
