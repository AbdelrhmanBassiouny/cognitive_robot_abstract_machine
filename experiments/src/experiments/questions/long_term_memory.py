"""
The questions asked of what past runs recorded.

Long-term memory is the episodes in the database, reached through the same query language
a live world is reached through. Answering these exercises remembering: the facts are not
in front of the robot any more, and the query has to get them back out of the store.

..note:: Every one of these crosses a to-many collection an episode holds -- a trial's
    ticks, and a tick's events -- which the generated interface reaches through an
    association table. Nothing in this repository proves the query language translates a
    join across one, and this is the first work that needs it, so the tests here are what
    answers that question.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass

from krrood.entity_query_language.factories import (
    an,
    contains,
    entity,
    variable,
)
from krrood.entity_query_language.query.query import Query
from segmind.datastructures.events import (
    DetectionEvent,
    EventWithTrackedObjects,
    ManipulatesBodies,
    MotionEvent,
    PickUpEvent,
)
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Any, ClassVar, Generic, List, Tuple

from experiments.episodes.episode import RecordedTrial, Tick
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.questions.question import (
    AnswerType,
    BloomLevel,
    Bucket,
    Memory,
    Question,
    RememberedThings,
    RequiredFact,
)

# %% what a question of this kind is asked of


@dataclass
class LongTermMemoryQuestion(
    Question[LongTermMemory, AnswerType], Generic[AnswerType], ABC
):
    """
    A question answered from the episodes past runs recorded.
    """

    memory: ClassVar[Memory] = Memory.LONG_TERM
    """
    Long-term memory, which is what makes this a remembering question.
    """

    bloom_level: ClassVar[BloomLevel] = BloomLevel.REMEMBERING
    """
    Nothing asked here is in front of the robot any more, so answering it is recall.
    """

    episode_identifier: str
    """
    Which run the question is about.
    """

    @classmethod
    def asked_of(cls, things: RememberedThings) -> List[LongTermMemoryQuestion]:
        """
        How this question is put to a recorded run, which is once and about the run as a
        whole unless it singles something out.

        :param things: What the run fills in for the questions about one thing.
        """
        return [cls(episode_identifier=things.episode_identifier)]

    def solutions(self, source: LongTermMemory) -> List[Any]:
        """
        Every solution this question's query has over the recorded episodes.

        :param source: The long-term memory the question is put to.
        """
        return source.answer(self.query(source))

    def recorded_events(self, source: LongTermMemory) -> List[DetectionEvent]:
        """
        Every event the run recorded, in the order its ticks were taken.

        What ground truth is read from: the trials come back as the objects the run wrote,
        so the answer is traversed off them rather than asked for through the query the
        question is scored on.

        :param source: The long-term memory holding what actually happened.
        """
        return [
            event
            for trial in source.recall_trials(self.episode_identifier)
            for tick in trial.ticks
            for event in tick.events
        ]


# %% scene


@dataclass
class ObjectsSeenInTheEpisode(LongTermMemoryQuestion[List[Body]]):
    """
    Which objects the robot saw during one past run.
    """

    bucket: ClassVar[Bucket] = Bucket.SCENE
    """
    The same scene question, asked of a run that is over.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.MOTION_EVENTS,)
    """
    An object is one the segmentation reported something about, so what the run recorded
    of its events is what makes it answerable.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "What objects did you see in episode %s?" % self.episode_identifier

    def query(self, source: LongTermMemory) -> Query:
        """
        What every event of that run's ticks was about.

        :param source: The long-term memory the question is put to.
        """
        trial = variable(RecordedTrial, domain=[])
        tick = variable(Tick, domain=[])
        event = variable(EventWithTrackedObjects, domain=[])
        return an(
            entity(event.tracked_object).where(
                trial.episode.identifier == self.episode_identifier,
                contains(trial.ticks, tick),
                contains(tick.events, event),
            )
        )

    def ground_truth(self, source: LongTermMemory) -> List[Body]:
        """
        The objects the recorded events name, traversed off them directly.

        :param source: The long-term memory holding what actually happened.
        """
        return [event.tracked_object for event in self.recorded_events(source)]


# %% temporal and agency


@dataclass
class AnythingMovedInTheEpisode(LongTermMemoryQuestion[bool]):
    """
    Whether anything moved during one past run.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    A question about what happened, asked after it happened.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.MOTION_EVENTS,)
    """
    Nothing but the motion the run recorded.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Did any object move in episode %s?" % self.episode_identifier

    def query(self, source: LongTermMemory) -> Query:
        """
        Every motion that run recorded.

        :param source: The long-term memory the question is put to.
        """
        trial = variable(RecordedTrial, domain=[])
        tick = variable(Tick, domain=[])
        motion = variable(MotionEvent, domain=[])
        return an(
            entity(motion).where(
                trial.episode.identifier == self.episode_identifier,
                contains(trial.ticks, tick),
                contains(tick.events, motion),
            )
        )

    def ask(self, source: LongTermMemory) -> bool:
        """
        Whether anything moved.

        :param source: The long-term memory the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: LongTermMemory) -> bool:
        """
        Whether the run recorded a motion, traversed off what it wrote.

        :param source: The long-term memory holding what actually happened.
        """
        return any(
            isinstance(event, MotionEvent) for event in self.recorded_events(source)
        )


@dataclass
class ObjectsThatMovedInTheEpisode(LongTermMemoryQuestion[List[Body]]):
    """
    Which objects moved during one past run.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    Which things the recorded motion was about.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.MOTION_EVENTS,)
    """
    Nothing but the motion the run recorded.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Which objects moved in episode %s?" % self.episode_identifier

    def query(self, source: LongTermMemory) -> Query:
        """
        What every recorded motion of that run was about.

        :param source: The long-term memory the question is put to.
        """
        trial = variable(RecordedTrial, domain=[])
        tick = variable(Tick, domain=[])
        motion = variable(MotionEvent, domain=[])
        return an(
            entity(motion.tracked_object).where(
                trial.episode.identifier == self.episode_identifier,
                contains(trial.ticks, tick),
                contains(tick.events, motion),
            )
        )

    def ground_truth(self, source: LongTermMemory) -> List[Body]:
        """
        The objects the recorded motions name, traversed off them directly.

        :param source: The long-term memory holding what actually happened.
        """
        return [
            event.tracked_object
            for event in self.recorded_events(source)
            if isinstance(event, MotionEvent)
        ]


@dataclass
class ObjectsTheRobotMovedInTheEpisode(LongTermMemoryQuestion[List[Body]]):
    """
    Which of the objects that moved during one past run the robot moved itself.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    The agency half of the bucket, asked after the fact.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.MOTION_EVENTS,
        RequiredFact.PICK_UP_EVENTS,
    )
    """
    An object the robot moved is one it moved and had picked up, so both kinds of event
    have to have been recorded.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Which objects did you move in episode %s?" % self.episode_identifier

    def query(self, source: LongTermMemory) -> Query:
        """
        What every recorded motion of an object that run acted on was about.

        ..note:: Spelled as a join rather than through ``exists``, which answers this
            shape with every object that moved whether the robot acted on it or not.

        :param source: The long-term memory the question is put to.
        """
        trial = variable(RecordedTrial, domain=[])
        tick = variable(Tick, domain=[])
        motion = variable(MotionEvent, domain=[])
        acting_tick = variable(Tick, domain=[])
        manipulation = variable(ManipulatesBodies, domain=[])
        return an(
            entity(motion.tracked_object).where(
                trial.episode.identifier == self.episode_identifier,
                contains(trial.ticks, tick),
                contains(tick.events, motion),
                contains(trial.ticks, acting_tick),
                contains(acting_tick.events, manipulation),
                contains(manipulation.manipulated_bodies, motion.tracked_object),
            )
        )

    def ground_truth(self, source: LongTermMemory) -> List[Body]:
        """
        The objects the run recorded both a pick-up and a motion of, traversed off what
        it wrote.

        :param source: The long-term memory holding what actually happened.
        """
        events = self.recorded_events(source)
        picked_up = {
            body
            for event in events
            if isinstance(event, ManipulatesBodies)
            for body in event.manipulated_bodies
        }
        return [
            event.tracked_object
            for event in events
            if isinstance(event, MotionEvent) and event.tracked_object in picked_up
        ]


@dataclass
class PickedUpInTheEpisode(LongTermMemoryQuestion[bool]):
    """
    Whether one object was picked up during one past run.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    A question about one thing that happened.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.PICK_UP_EVENTS,)
    """
    Nothing but the pick-ups the run recorded.
    """

    object_name: str
    """
    What the object the question is about was called.
    """

    @classmethod
    def asked_of(cls, things: RememberedThings) -> List[PickedUpInTheEpisode]:
        """
        Asked about the one object the run singles out.

        :param things: What the run fills in for the questions about one thing.
        """
        return [
            cls(
                episode_identifier=things.episode_identifier,
                object_name=things.object_name,
            )
        ]

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Was the %s picked up in episode %s?" % (
            self.object_name,
            self.episode_identifier,
        )

    def query(self, source: LongTermMemory) -> Query:
        """
        Every recorded pick-up of the named object in that run.

        :param source: The long-term memory the question is put to.
        """
        trial = variable(RecordedTrial, domain=[])
        tick = variable(Tick, domain=[])
        pick_up = variable(PickUpEvent, domain=[])
        return an(
            entity(pick_up).where(
                trial.episode.identifier == self.episode_identifier,
                contains(trial.ticks, tick),
                contains(tick.events, pick_up),
                pick_up.tracked_object.name.name == self.object_name,
            )
        )

    def ask(self, source: LongTermMemory) -> bool:
        """
        Whether the named object was picked up.

        :param source: The long-term memory the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: LongTermMemory) -> bool:
        """
        Whether the run recorded a pick-up of the named object, traversed off what it
        wrote.

        :param source: The long-term memory holding what actually happened.
        """
        return any(
            isinstance(event, PickUpEvent)
            and event.tracked_object.name.name == self.object_name
            for event in self.recorded_events(source)
        )


# %% self-model


@dataclass
class NumberOfDegreesOfFreedomInTheRecordedWorld(LongTermMemoryQuestion[int]):
    """
    How many joints there were in the world one past run happened in.

    The world's rather than the robot's, and named so: an environment has degrees of
    freedom of its own, and an episode records the world without recording which of its
    links were the robot's, so the robot's own count is not separable from it. Asking
    both is what the self-model bucket wants, and the robot's half waits on the same
    thing the embodiment bucket does.
    """

    bucket: ClassVar[Bucket] = Bucket.SELF_MODEL
    """
    The bucket the robot's own count belongs to, which this is as much of as a recorded
    run can answer.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.KINEMATIC_STRUCTURE,
        RequiredFact.DEGREES_OF_FREEDOM,
    )
    """
    Answered from the world the run was recorded with, which is where both live.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "How many joints did you have in episode %s?" % self.episode_identifier

    def query(self, source: LongTermMemory) -> Query:
        """
        The degrees of freedom the world that run happened in had.

        Selects them rather than counting them in the query, the way the live spelling
        does: long-term memory answers with the objects a run wrote, so an aggregate has
        no way back through it.

        :param source: The long-term memory the question is put to.
        """
        trial = variable(RecordedTrial, domain=[])
        degree_of_freedom = variable(DegreeOfFreedom, domain=[])
        return an(
            entity(degree_of_freedom).where(
                trial.episode.identifier == self.episode_identifier,
                contains(trial.episode.world.degrees_of_freedom, degree_of_freedom),
            )
        )

    def ask(self, source: LongTermMemory) -> int:
        """
        How many degrees of freedom came back.

        :param source: The long-term memory the question is put to.
        """
        return len(self.solutions(source))

    def ground_truth(self, source: LongTermMemory) -> int:
        """
        How many degrees of freedom the recorded world holds, counted off it directly.

        :param source: The long-term memory holding what actually happened.
        """
        trial, *rest = source.recall_trials(self.episode_identifier)
        return len(trial.episode.world.degrees_of_freedom)
