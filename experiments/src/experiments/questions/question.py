"""
What a question of the frozen set is.

A question names what is asked, which of the six kinds of thing it asks about, the level
of Bloom's taxonomy answering it exercises, what has to be represented for it to be
answerable at all, and the query that answers it. The same English question asked of
working memory and of long-term memory is two questions here, because the two exercise
different levels and are therefore scored apart.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from coraplex.datastructures.enums import ExecutionType
from krrood.entity_query_language.query.query import Query
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    SpatialType,
)
from semantic_digital_twin.world_description.world_entity import Body
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.utils import get_generic_type_parameters
from typing_extensions import Any, ClassVar, Generic, List, Tuple, TypeVar

# %% what a question is about, and what answering it exercises


class Bucket(StrEnum):
    """
    The six kinds of thing the question set asks about.

    Widened from four so that the control program and the robot's own body are asked
    about in the language the scene is asked about in.
    """

    SCENE = "scene"
    SUPPORT_AND_SPATIAL_RELATIONS = "support and spatial relations"
    TEMPORAL_AND_AGENCY = "temporal and agency"
    EMBODIMENT = "embodiment"
    SELF_MODEL = "self-model"
    CONTROL = "control"


class BloomLevel(StrEnum):
    """
    The level of Bloom's taxonomy that answering a question exercises.

    The evaluation frame of the paper, and deliberately bounded: inferring knowledge
    that is not already represented is above all three and is stated as out of scope.
    """

    REMEMBERING = "remembering"
    UNDERSTANDING = "understanding"
    APPLYING = "applying"


class Memory(StrEnum):
    """
    Which store a question is answered from.

    Every bucket is spelled both ways, which is what makes remembering and understanding
    separately measurable on the same English question.
    """

    WORKING = "working"
    LONG_TERM = "long-term"


class RequiredFact(StrEnum):
    """
    One thing that has to be represented for a question to be answerable at all.

    A question that declares a fact nothing recorded is scored apart from one that had
    the evidence and got the answer wrong.
    """

    OBJECT_SHAPES = "object shapes"
    OBJECT_COLOURS = "object colours"
    OBJECT_PLACES = "object places"
    SUPPORT_RELATIONS = "support relations"
    POINT_OF_VIEW = "point of view"
    MOTION_EVENTS = "motion events"
    PICK_UP_EVENTS = "pick-up events"
    ATTACHMENTS = "attachments"
    KINEMATIC_STRUCTURE = "kinematic structure"
    DEGREES_OF_FREEDOM = "degrees of freedom"


class GroundTruthSource(StrEnum):
    """
    Where the true answer to a question comes from, which depends on where the run
    happened.
    """

    TWIN = "twin"
    """
    The digital twin itself, which in simulation is exact because it is what the
    simulator was built from.
    """

    CALIBRATED_TWIN_AND_HUMAN_CHECK = "calibrated twin and human check"
    """
    The twin calibrated against the real setup, with a person confirming the answer,
    which is the best that can be had on the robot.
    """

    @classmethod
    def for_execution(cls, execution_type: ExecutionType) -> GroundTruthSource:
        """
        Where the true answers of a run executed this way come from.

        :param execution_type: Whether the run happened in a simulator or on the robot.
        """
        if execution_type is ExecutionType.SIMULATED:
            return cls.TWIN
        return cls.CALIBRATED_TWIN_AND_HUMAN_CHECK


# %% the question itself

SourceType = TypeVar("SourceType")
"""
The memory a question is asked of.
"""

AnswerType = TypeVar("AnswerType")
"""
What a question answers with.
"""


@dataclass
class Question(Generic[SourceType, AnswerType], SubClassSafeGeneric, ABC):
    """
    One question of the frozen set, asked of one memory.

    ..note:: The memory a question is asked of is its bound source type, and the level it
        exercises follows from that memory rather than being stated per question.
    """

    bucket: ClassVar[Bucket]
    """
    Which of the six kinds of thing this question asks about.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]]
    """
    What has to be represented for this question to be answerable at all.
    """

    memory: ClassVar[Memory]
    """
    Which store answers this question.
    """

    bloom_level: ClassVar[BloomLevel]
    """
    The level of Bloom's taxonomy answering this question exercises.
    """

    @property
    @abstractmethod
    def english(self) -> str:
        """
        The question as a person would ask it.
        """

    @property
    def answer_type(self) -> Any:
        """
        What kind of answer this question has, read from its bound type parameter.

        A generic alias such as ``List[Body]`` where the answer is a collection of
        things, and a plain class where it is a single value. Only one parameter is left
        to read, because the memory a question is asked of is bound by the base it
        inherits from rather than by the question itself.
        """
        (answer_type,) = get_generic_type_parameters(self, Question)
        return answer_type

    @abstractmethod
    def query(self, source: SourceType) -> Query:
        """
        The query in the entity query language that answers this question.

        :param source: The memory the question is put to.
        """

    @abstractmethod
    def solutions(self, source: SourceType) -> List[Any]:
        """
        Every solution this question's query has, in the way its memory is asked.

        :param source: The memory the question is put to.
        """

    def ask(self, source: SourceType) -> AnswerType:
        """
        Answer this question from the given memory.

        Every solution the query found, which is the answer wherever the question asks
        which things are the case; a question whose answer is one value or a judgement
        narrows it.

        :param source: The memory the question is put to.
        """
        return self.solutions(source)

    @abstractmethod
    def ground_truth(self, source: SourceType) -> AnswerType:
        """
        The true answer, read from the representation directly rather than through the
        query this question is scored on.

        :param source: The memory holding what actually happened.
        """

    @staticmethod
    def distinct(answered: List[Any]) -> List[Any]:
        """
        The things a question found, each named once and in the order they were found.

        A query yields one row per witness, so an object two remembered events are about
        comes back twice while the question asks which objects, not how often.

        :param answered: What the query found.
        """
        return list(dict.fromkeys(answered))

    def matches_ground_truth(self, source: SourceType) -> bool:
        """
        Whether this question's answer agrees with ground truth.

        A spatial answer is compared numerically rather than by identity, since two
        poses standing for the same place are two objects and the twin's own equality
        says so; a list is compared position by position, each element the same way.

        :param source: The memory the question is put to.
        """
        return self.values_agree(self.ask(source), self.ground_truth(source))

    @classmethod
    def values_agree(cls, answered: Any, true: Any) -> bool:
        """
        Whether one answered value and its true counterpart are the same thing.

        :param answered: What a question answered, or one element of it.
        :param true: What the representation actually holds, or one element of it.
        """
        if isinstance(answered, SpatialType):
            return np.allclose(answered.to_np(), true.to_np())
        if isinstance(answered, list):
            return len(answered) == len(true) and all(
                cls.values_agree(one, other) for one, other in zip(answered, true)
            )
        return answered == true


# %% what a scene fills in


@dataclass
class QuestionedThings:
    """
    What a scene fills in for the questions of the set that single out one thing.
    """

    object_asked_about: Body
    """
    The object the questions about one object are about.
    """

    object_compared_against: Body
    """
    The object the first one is placed against, which is what a spatial question needs a
    second thing for.
    """

    object_in_the_hand: Body
    """
    The object the robot is being asked whether it is holding.
    """

    own_body_asked_about: PrefixedName
    """
    The robot's own link the self-model questions are about.
    """

    point_of_view: HomogeneousTransformationMatrix
    """
    Where the scene is looked at from, which is what makes left and right mean anything.
    """


@dataclass
class RememberedThings:
    """
    What a recorded run fills in for the questions of the set that single out one thing.
    """

    episode_identifier: str
    """
    Which run the questions are about.
    """

    object_name: str
    """
    What the object the questions about one object are about was called.

    A name rather than the body itself, because the body a run recorded is read back out
    of the database and is not the object anyone still holds.
    """
