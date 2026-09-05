"""
What one run of a scenario recorded: the conditions it ran under, its trials, and
everything that happened in each of them.

One model for simulation and the robot alike, so a question asked of the history reaches
every run the same way regardless of where it ran.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from coraplex.datastructures.enums import ExecutionType
from coraplex.plans.plan import Plan
from segmind.datastructures.events import DetectionEvent
from typing_extensions import TYPE_CHECKING, List, Optional, Sequence

from experiments.scenarios.trial import TrialOutcome

if TYPE_CHECKING:
    from experiments.scenarios.scenario import Condition, Perturbation, Scenario
    from experiments.scenarios.trial import Trial

# %% how a failure was typed and what was done about it


class FailureType(StrEnum):
    """
    Base for the enum the failure taxonomy names its types with.

    Left without members here so that the taxonomy owns what the types are, while an
    episode can already record one. ORMatic stores an enum member as the path to its own
    class, so a member added in a subclass needs no change to this field.
    """


class FailureResolution(StrEnum):
    """
    What was done after an attempt failed.
    """

    RETRIED = "retried"
    CHANGED = "changed"
    ABANDONED = "abandoned"


class InsertionOutcome(StrEnum):
    """
    How one attempt to insert a shape ended.
    """

    FELL_THROUGH = "fell_through"
    DID_NOT_FALL_THROUGH = "did_not_fall_through"


# %% what happened inside one trial


@dataclass
class Tick:
    """
    One tick of a trial's event monitor, and what it detected.
    """

    moment: float
    """
    Seconds between the start of the trial and this tick.
    """

    events: List[DetectionEvent] = field(default_factory=list)
    """
    The segmind events detected in this tick.
    """


@dataclass
class AnsweredPredicate:
    """
    One predicate of a query, and the backend that answered it.
    """

    predicate_name: str
    """
    The predicate, named as the query spells it.
    """

    backend_name: str
    """
    The backend the predicate was routed to, named as its class is.
    """


@dataclass
class RecordedQuery:
    """
    One query asked during a trial, with how it was routed and what it answered.
    """

    text: str
    """
    The query as it was asked.
    """

    answer: str
    """
    The answer as it was rendered for a reader.
    """

    latency: float
    """
    Seconds the query took to answer.
    """

    moment: float
    """
    Seconds between the start of the trial and the moment the query was asked.
    """

    answered_predicates: List[AnsweredPredicate] = field(default_factory=list)
    """
    Which backend answered each predicate of the query.
    """


@dataclass
class InsertionAttempt:
    """
    One attempt to insert a shape, how it ended, and what was made of that.
    """

    shape_name: str
    """
    The shape the attempt was made with.
    """

    plan: Plan
    """
    The realized plan of this attempt, expanded down to its motions.
    """

    outcome: InsertionOutcome
    """
    How the attempt ended.
    """

    predicted_failure: Optional[FailureType] = None
    """
    The failure predicted before the attempt ran, or None if none was predicted.
    """

    observed_failure: Optional[FailureType] = None
    """
    The failure read off what happened, or None if the attempt did not fail.
    """

    resolution: Optional[FailureResolution] = None
    """
    What was done after the attempt failed, or None if it did not fail.
    """


@dataclass
class RecordedTrial:
    """
    One trial of an episode's scenario, as it was recorded.

    Kept apart from :class:`~experiments.scenarios.trial.Trial`, which a run holds while
    it is running and which carries the live conditions and perturbations acting on its
    world. This is what goes into the database.
    """

    episode: Episode
    """
    The episode this trial belongs to.
    """

    outcome: TrialOutcome
    """
    Whether the trial reached the scenario's goal.
    """

    duration: float
    """
    How long the trial took, in seconds.
    """

    ticks: List[Tick] = field(default_factory=list)
    """
    The event monitor's ticks, in the order they happened.
    """

    queries: List[RecordedQuery] = field(default_factory=list)
    """
    Every query asked while the trial ran, in the order they were asked.
    """

    insertion_attempts: List[InsertionAttempt] = field(default_factory=list)
    """
    Every insertion attempted while the trial ran, in the order they were made.
    """

    @classmethod
    def from_trial(cls, trial: Trial, episode: Episode) -> RecordedTrial:
        """
        Take what a finished trial recorded of itself.

        What the trial's own runner cannot see - the monitor's ticks, the queries asked
        and the insertions attempted - is added by whatever observed it.

        :param trial: The trial that has finished.
        :param episode: The episode the trial belongs to.
        """
        return cls(episode=episode, outcome=trial.outcome, duration=trial.duration)


# %% the episode itself


@dataclass
class Episode:
    """
    One run of a scenario under one set of conditions, and where its trials are found.
    """

    scenario_name: str
    """
    The scenario every trial of this episode ran.
    """

    execution_type: ExecutionType
    """
    Whether the episode ran in a simulator or on the robot.
    """

    condition_names: List[str] = field(default_factory=list)
    """
    The knowledge sources switched for the run, each named as its class is.
    """

    perturbation_names: List[str] = field(default_factory=list)
    """
    The changes applied to every trial's world, each named as its class is.
    """

    identifier: str = field(default_factory=lambda: uuid.uuid4().hex)
    """
    What addresses this episode outside the database, where its video, its simulation
    data and its transcript are kept.
    """

    recorded_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    """
    When the episode began.
    """

    @classmethod
    def from_run(
        cls,
        scenario: Scenario,
        conditions: Sequence[Condition] = (),
        perturbations: Sequence[Perturbation] = (),
    ) -> Episode:
        """
        Describe the run a scenario is about to make.

        The conditions and perturbations are recorded by name because they act on a live
        world and so are not themselves records.

        :param scenario: The scenario every trial runs.
        :param conditions: The knowledge sources switched for every trial.
        :param perturbations: The changes applied to every trial's world.
        """
        return cls(
            scenario_name=scenario.name,
            execution_type=scenario.execution_type,
            condition_names=[type(condition).__name__ for condition in conditions],
            perturbation_names=[
                type(perturbation).__name__ for perturbation in perturbations
            ],
        )
