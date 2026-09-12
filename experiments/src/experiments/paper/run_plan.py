"""
The plan one trial ran, read back as the items it ran and when each of them ran.

What the plan chart is drawn from, and what settles whether the robot brought an event
about: an event an item of the plan accounts for is one the robot did, and an event no
item accounts for is one something else did to the scene while it was working.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from coraplex.plans.plan import Plan
from coraplex.plans.plan_node import ActionNode, PlanNode
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.robot_plans.mixins import ManipulatesBodies
from giskardpy.motion_statechart.data_types import LifeCycleValues
from krrood.exceptions import DataclassException
from segmind.datastructures.events import DetectionEvent, EventWithTrackedObjects
from typing_extensions import List, Optional, Tuple

from experiments.episodes.episode import RecordedTrial
from semantic_digital_twin.world_description.world_entity import Body

# %% how long an item goes on accounting for what was seen

JUST_FINISHED = 1.0
"""
How long after an item of the plan has finished it still accounts for what was seen, in
seconds.

A monitor reports what happened once it has happened: a pick-up is reported when the
object is already off the table, which is a moment after the item that lifted it has
finished. Without this the item that plainly brought the event about would be read as
having had nothing to do with it.
"""

# %% a trial whose plan was not recorded


@dataclass
class TrialRanNoPlanError(DataclassException):
    """
    Raised when a trial is asked what it was running and it recorded no plan.
    """

    episode_identifier: str
    """
    The episode the trial belongs to.
    """

    def error_message(self) -> str:
        return "A trial of episode %s recorded no plan, so there is nothing it ran." % (
            self.episode_identifier
        )

    def suggest_correction(self) -> str:
        return (
            "A run records each plan it performs on the trial, so a trial with none "
            "was recorded by a run that performed no plan or did not record it. Draw "
            "only the panels that do not read the plan, or record the episode again."
        )


# %% telling whether two bodies are the same object


class ObjectIdentity(ABC):
    """
    How two bodies are told to be the same object.

    A plan's item names the body it acts on as the world the plan was made in holds it;
    a monitor's event names the body as the world it watched holds it. Whether those are
    one object is what this settles.
    """

    @abstractmethod
    def same(self, one: Body, other: Body) -> bool:
        """
        Whether the two bodies are the same object.

        :param one: A body, as one world holds it.
        :param other: A body, as the same or another world holds it.
        """


@dataclass(frozen=True)
class SameName(ObjectIdentity):
    """
    Two bodies are the same object when the twin gives them the same name.

    By name rather than by identity, because a recalled episode reads its plan and its
    events back as separate objects.
    """

    def same(self, one: Body, other: Body) -> bool:
        return one.name == other.name


# %% the clock the records of one trial share


@dataclass(frozen=True)
class TrialClock:
    """
    Where the seconds of one trial start, so that what was recorded against the wall
    clock can be read against the run it happened in.

    A tick says how far into the trial it is; a plan item and an event say what time it
    was. This is what turns the second into the first.
    """

    origin: datetime
    """
    The instant the trial's own seconds are counted from.
    """

    def seconds_of(self, instant: datetime) -> float:
        """
        How far into the trial the given instant is.

        :param instant: The instant to place.
        """
        return (instant - self.origin).total_seconds()

    @classmethod
    def of(cls, trial: RecordedTrial) -> TrialClock:
        """
        The clock of one recorded trial, which starts when the trial began.

        :param trial: The trial to read.
        """
        return cls(origin=trial.began_at)


def plans_of(trial: RecordedTrial) -> List[Plan]:
    """
    Every plan the given trial recorded, in the order it ran them: the plans it
    performed, then the ones its insertion attempts were made with.

    :param trial: The trial to read.
    """
    return [performed.plan for performed in trial.plans] + [
        attempt.plan for attempt in trial.insertion_attempts
    ]


def ran(node: PlanNode) -> bool:
    """
    Whether the given node was ever started.

    :param node: The node to ask.
    """
    return node.status is not LifeCycleValues.NOT_STARTED


# %% one item of the plan


@dataclass(frozen=True)
class PlanItem:
    """
    One action of the plan a trial ran, placed in the seconds of that trial.
    """

    node: ActionNode
    """
    The plan's own record of the item.
    """

    start: float
    """
    Seconds between the start of the trial and the moment this item started.
    """

    duration: float
    """
    How long the item ran, in seconds.
    """

    @classmethod
    def of(cls, node: ActionNode, clock: TrialClock, trial_duration: float) -> PlanItem:
        """
        One action placed in the seconds of its trial.

        An action runs from when the first thing it is made of started to when the last
        of them ended: a plan is performed as one motion, so what carries the times is
        the motions and code the action expands into, and the action itself only where
        it was performed on its own. A part the trial ended in the middle of was still
        running when it ended, so it runs that far and no further.

        :param node: The action to place.
        :param clock: Where the trial's own seconds start.
        :param trial_duration: How long the trial ran, in seconds.
        """
        parts = [part for part in [node] + node.descendants if ran(part)]
        start = min(clock.seconds_of(part.start_time) for part in parts)
        ended = max(
            (
                trial_duration
                if part.end_time is None
                else clock.seconds_of(part.end_time)
            )
            for part in parts
        )
        return cls(node=node, start=start, duration=ended - start)

    @property
    def action(self) -> ActionDescription:
        """
        What this item did.
        """
        return self.node.action

    @property
    def status(self) -> LifeCycleValues:
        """
        The state the run left this item in: its own where it was performed on its own,
        and otherwise the state of the last of its parts to be started.
        """
        if ran(self.node):
            return self.node.status
        started = [part for part in self.node.descendants if ran(part)]
        return max(started, key=lambda part: part.start_time).status

    @property
    def manipulated_bodies(self) -> List[Body]:
        """
        The bodies of the scene this item acts on, which is none for an item that only
        moves the robot itself.
        """
        if not isinstance(self.action, ManipulatesBodies):
            return []
        return self.action.manipulated_bodies

    @property
    def label(self) -> str:
        """
        This item as it is written down the side of the plan chart: what it did, and
        what it did it to.
        """
        acted_on = self.manipulated_bodies
        if not acted_on:
            return type(self.action).__name__
        return "%s (%s)" % (
            type(self.action).__name__,
            ", ".join(body.name.name for body in acted_on),
        )

    def covers(self, moment: float, just_finished: float = JUST_FINISHED) -> bool:
        """
        Whether this item was running at the given moment of the trial, or had only just
        finished.

        :param moment: Seconds into the trial.
        :param just_finished: How long after finishing the item still counts as running.
        """
        return self.start <= moment <= self.start + self.duration + just_finished

    def acts_on(self, body: Body, identity: ObjectIdentity = SameName()) -> bool:
        """
        Whether this item acts on the given body.

        :param body: The body to look for.
        :param identity: How a body this item acts on is told to be the given one.
        """
        return any(
            identity.same(acted_on, body) for acted_on in self.manipulated_bodies
        )


# %% the plan a trial ran


@dataclass(frozen=True)
class RunPlan:
    """
    Every item of the plan one trial ran, in the order they started.
    """

    clock: TrialClock
    """
    Where the trial's own seconds start.
    """

    items: Tuple[PlanItem, ...]
    """
    The items, in the order they started.
    """

    just_finished: float = field(default=JUST_FINISHED)
    """
    How long after an item has finished it still accounts for what was seen, in seconds.
    """

    identity: ObjectIdentity = field(default_factory=SameName)
    """
    How a body an item acts on is told to be the body an event is about.
    """

    @classmethod
    def of(
        cls,
        trial: RecordedTrial,
        just_finished: float = JUST_FINISHED,
        identity: ObjectIdentity = SameName(),
    ) -> RunPlan:
        """
        Read back the plan one trial ran.

        :param trial: The trial to read.
        :param just_finished: How long after an item has finished it still accounts for
            what was seen, in seconds.
        :param identity: How a body an item acts on is told to be the body an event is
            about.
        :raises TrialRanNoPlanError: If the trial recorded no plan.
        """
        if not plans_of(trial):
            raise TrialRanNoPlanError(episode_identifier=trial.episode.identifier)
        clock = TrialClock.of(trial)
        items = [
            PlanItem.of(node, clock, trial.duration)
            for node in cls._action_nodes_of(trial)
        ]
        return cls(
            clock=clock,
            items=tuple(sorted(items, key=lambda item: item.start)),
            just_finished=just_finished,
            identity=identity,
        )

    def moment_of(self, event: DetectionEvent) -> float:
        """
        How far into the trial the given event happened.

        :param event: The event to place.
        """
        return self.clock.seconds_of(event.timestamp)

    def accounts_for(self, event: DetectionEvent) -> Optional[PlanItem]:
        """
        The item of the plan that brought the given event about, or None where no item
        did.

        An item accounts for an event when it acts on the object the event is about and
        was running when the event was seen. An event nothing accounts for is one
        something other than the robot did to the scene.

        :param event: The event to account for.
        """
        if not isinstance(event, EventWithTrackedObjects):
            return None
        moment = self.moment_of(event)
        for item in self.items:
            if item.covers(moment, self.just_finished) and item.acts_on(
                event.tracked_object, self.identity
            ):
                return item
        return None

    # %% reading the items off the trial

    @staticmethod
    def _action_nodes_of(trial: RecordedTrial) -> List[ActionNode]:
        """
        Every action the trial's plans ran, which is what the robot did rather than what
        held its plan together.

        An action ran if it was performed itself or anything it expands into was.

        :param trial: The trial to read.
        """
        return [
            node
            for plan in plans_of(trial)
            for node in plan.all_nodes
            if isinstance(node, ActionNode)
            and any(ran(part) for part in [node] + node.descendants)
        ]
