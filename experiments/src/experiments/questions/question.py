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
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
from coraplex.datastructures.enums import ExecutionType
from krrood.adapters.json_serializer import (
    DataclassJSONSerializer,
    SubclassJSONSerializer,
)
from krrood.exceptions import DataclassException
from krrood.entity_query_language.backends import QueryBackend
from krrood.entity_query_language.core.variable import InstantiatedVariable
from krrood.entity_query_language.predicate import Predicate
from krrood.entity_query_language.query.query import Query
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import is_supported_by
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    Pose,
    SpatialType,
)
from semantic_digital_twin.world_description.world_entity import Body
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.utils import get_generic_type_parameters
from typing_extensions import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

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


# %% what a scene holds


def moving_parts_of(robot: AbstractRobot) -> List[Body]:
    """
    The robot's bodies apart from its root.

    A fixed robot's description bolts its arms to what it stands on, so its root body is
    the table its scene is set on rather than a part of the robot.

    :param robot: The robot whose parts they are.
    """
    return [body for body in robot.bodies if body is not robot.root]


def objects_of_the_scene(robot: AbstractRobot) -> List[Body]:
    """
    The bodies the robot can be asked about as objects, read off the twin directly.

    ..note:: A body the robot is holding is one of its own by the twin's account, so it
        is answered by the embodiment bucket rather than counted here.

    :param robot: The robot whose scene it is.
    """
    return [
        body
        for body in robot._world.bodies
        if body.has_collision() and body not in robot.bodies
    ]


def surfaces_of_the_scene(robot: AbstractRobot) -> List[Body]:
    """
    The bodies something in the robot's scene can stand on, read off the twin directly:
    every body with a shape that is not one of the robot's moving parts.

    :param robot: The robot whose scene it is.
    """
    moving_parts = moving_parts_of(robot)
    return [
        body
        for body in robot._world.bodies
        if body.has_collision() and body not in moving_parts
    ]


# %% the scene as whoever set it up knows it

HOW_FAR_A_PLACE_MAY_DIFFER = 0.01
"""
How far from where it was put a thing may stand and still count as standing where it was
put, in metres.

A scene comes to rest under gravity between being stood and being asked about, and a
piece put down resting on its surface travels well under a millimetre doing so. A
centimetre is inside the smallest change anyone makes to one of these scenes, so it
separates settling from something having happened.
"""


def placeless(pose: Pose) -> Point3:
    """
    Where a pose puts something, as three numbers in the frame the pose was measured in.

    Taken off the frame it was measured in, since a scene's account of itself outlives
    the world that frame is a body of.

    :param pose: The pose to read.
    """
    stands_at = pose.to_position().to_np()
    return Point3(float(stands_at[0]), float(stands_at[1]), float(stands_at[2]))


@dataclass
class PlacedObject:
    """
    One object as whoever set the scene up put it there.
    """

    name: PrefixedName
    """
    What the scene calls it.
    """

    place: Optional[Point3] = None
    """
    Where it was put, in the world root frame, or None where the run acted on it and
    what the physics then did with it is not its to say.

    Where rather than how it stands: a scene says where it put a thing, and how far a
    piece ended up turned is the settling's to say.

    ..note:: Held without the frame it is measured in, since a place outlives the world
        it was measured in and a frame is a body of that world.
    """

    standing_on: Optional[PrefixedName] = None
    """
    What it was put on, or None where the run cannot say what holds it up.
    """


@dataclass
class SceneAsSetUp:
    """
    The scene as whoever set it up knows it: which objects stand in it, where each was
    put, and which one is in the robot's hand.

    What a question is scored against, and stated rather than read: the twin a question
    is answered from is the very thing an answer could be wrong about, so a true answer
    taken from it agrees with every answer whatever the twin holds.
    """

    objects: List[PlacedObject] = field(default_factory=list)
    """
    The objects standing in the scene, which is every object but the one in the hand.
    """

    object_in_the_hand: Optional[PrefixedName] = None
    """
    The object the robot was left holding, or None where it holds nothing.
    """

    how_far_a_place_may_differ: float = HOW_FAR_A_PLACE_MAY_DIFFER
    """
    How far a thing may stand from where it was put and still count as being there, in
    metres.
    """

    @property
    def names(self) -> List[PrefixedName]:
        """
        What the scene calls each object standing in it.
        """
        return [placed.name for placed in self.objects]

    @property
    def places(self) -> List[Optional[Point3]]:
        """
        Where each object standing in the scene was put, in the order they are held.
        """
        return [placed.place for placed in self.objects]

    def object_called(self, name: PrefixedName) -> Optional[PlacedObject]:
        """
        The object of that name, or None where the scene holds none.

        :param name: What the scene calls it.
        """
        for placed in self.objects:
            if placed.name == name:
                return placed
        return None

    def knows_what_holds_up(self, name: PrefixedName) -> bool:
        """
        Whether the scene says what holds one of its objects up, which it does for the
        object in the hand -- nothing does -- and for anything it put on a surface and
        did not act on afterwards.

        :param name: What the scene calls the object.
        """
        if name == self.object_in_the_hand:
            return True
        placed = self.object_called(name)
        return placed is not None and placed.standing_on is not None

    def holding_up(self, name: PrefixedName) -> List[PrefixedName]:
        """
        What the scene put under one of its objects, and nothing at all for the object
        in the hand.

        :param name: What the scene calls the object.
        """
        if name == self.object_in_the_hand:
            return []
        return [self.object_called(name).standing_on]

    def knows_where(self, name: PrefixedName) -> bool:
        """
        Whether the scene says where one of its objects stands.

        :param name: What the scene calls the object.
        """
        placed = self.object_called(name)
        return placed is not None and placed.place is not None

    def forget_where(self, name: PrefixedName) -> None:
        """
        Give up saying where an object stands and what holds it up, which is what
        someone else moving it leaves the run knowing about it.

        :param name: What the scene calls the object.
        """
        placed = self.object_called(name)
        if placed is None:
            return
        placed.place = None
        placed.standing_on = None

    @classmethod
    def read_from(cls, robot: AbstractRobot) -> SceneAsSetUp:
        """
        The scene as the twin has it, which is the account a run that stood nothing
        itself can give of the scene it was handed.

        ..warning:: Read off the very twin the questions are answered from, so it is an
            account of what was set up only where it is taken before anything acts on
            the scene.

        :param robot: The robot whose scene it is.
        """
        surfaces = surfaces_of_the_scene(robot)
        return cls(
            objects=[
                PlacedObject(
                    name=body.name,
                    place=placeless(body.global_pose),
                    standing_on=next(
                        (
                            surface.name
                            for surface in surfaces
                            if surface is not body and is_supported_by(body, surface)
                        ),
                        None,
                    ),
                )
                for body in objects_of_the_scene(robot)
            ]
        )


# %% a true answer that says for itself whether an answer agrees with it


class TrueAnswer(ABC):
    """
    A true answer stated in the currency whoever knows it states it in, which therefore
    says for itself whether an answer agrees with it.

    What a question is scored against wherever the true answer is not a value of the
    kind the question answers with: a scene names the objects standing in it while the
    question answers with the bodies the twin holds, and how far a place may differ from
    where a thing was put is the scene's to say rather than a numerical accident.
    """

    @abstractmethod
    def agrees_with(self, answered: Any) -> bool:
        """
        Whether an answer is this true answer.

        :param answered: What the question answered.
        """


@dataclass
class BodiesNamed(TrueAnswer):
    """
    The true answer is the things the scene calls these, in any order.
    """

    names: List[PrefixedName]
    """
    What the scene calls each of them.
    """

    def agrees_with(self, answered: List[Body]) -> bool:
        """
        Whether the bodies answered are called exactly these, each as often.

        Compared by name rather than by identity: a body is the twin's own account of
        what stands somewhere, and a scene that was set up knows only what it called the
        things it put there.

        :param answered: The bodies the question answered.
        """
        return sorted(str(body.name) for body in answered) == sorted(
            str(name) for name in self.names
        )


@dataclass
class PlacesPutAt(TrueAnswer):
    """
    The true answer is these places, in any order, each within the spread a scene allows
    a thing to have travelled by.
    """

    places: List[Optional[Point3]]
    """
    Where each thing was put, with None for one whose place the scene does not state.
    """

    how_far_a_place_may_differ: float
    """
    How far an answered place may lie from the place it stands for, in metres.
    """

    def agrees_with(self, answered: List[Pose]) -> bool:
        """
        Whether as many places were answered as things were put, each stated place among
        them once.

        A place the scene does not state is matched by whichever answered place is left
        over, so a thing someone moved is still counted without pretending to know where
        it went.

        :param answered: The places the question answered.
        """
        if len(answered) != len(self.places):
            return False
        left = list(answered)
        for place in [stated for stated in self.places if stated is not None]:
            found = next(
                (index for index, other in enumerate(left) if self.near(other, place)),
                None,
            )
            if found is None:
                return False
            left.pop(found)
        return True

    def near(self, answered: Pose, place: Point3) -> bool:
        """
        Whether two places are the same place, to within the spread this allows.

        :param answered: The place the question answered.
        :param place: The place a thing was put.
        """
        return bool(
            np.allclose(
                answered.to_position().to_np(),
                place.to_np(),
                atol=self.how_far_a_place_may_differ,
            )
        )


@dataclass
class SceneNotStated(DataclassException):
    """
    Raised when a question scored against the scene it was asked of is asked for its
    true answer without anyone having said what that scene was set up to be.
    """

    question: str
    """
    The question that was asked, as a person would ask it.
    """

    def error_message(self) -> str:
        return "Nothing says what the scene '%s' was asked of was set up to be." % (
            self.question
        )

    def suggest_correction(self) -> str:
        return (
            "Build the question through 'asked_of', handing it the scene whoever set it "
            "up says it stood."
        )


@dataclass
class ScoredAgainstTheSceneAsSetUp:
    """
    A question whose true answer is what the scene was set up to be rather than what the
    twin its query reads holds.
    """

    scene: Optional[SceneAsSetUp] = field(default=None, kw_only=True)
    """
    The scene as whoever set it up knows it, or None where nobody has said -- which a
    question read back out of a record made before anyone did comes back as.
    """

    def stated_scene(self) -> SceneAsSetUp:
        """
        The scene this question is scored against.

        :raises SceneNotStated: If nobody has said what the scene was set up to be.
        """
        if self.scene is None:
            raise SceneNotStated(question=self.english)
        return self.scene


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
class Question(
    SubclassJSONSerializer, Generic[SourceType, AnswerType], SubClassSafeGeneric, ABC
):
    """
    One question of the frozen set, asked of one memory.

    ..note:: The memory a question is asked of is its bound source type, and the level it
        exercises follows from that memory rather than being stated per question.

    ..note:: Inherits :class:`~krrood.adapters.json_serializer.SubclassJSONSerializer` so
        a specific question instance - not only which subclass it is - can be persisted
        as the question that produced a scored, recorded query.
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

    backend: ClassVar[Type[QueryBackend]]
    """
    The kind of query backend the memory this question is asked of answers it with,
    which is what a reported latency is attributed to.
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

    def predicates_asked(self, source: SourceType) -> List[Callable[..., Any]]:
        """
        The predicates this question's query applies, in the order the query holds them.

        What a reported latency is attributed to, together with the backend that
        answered them.

        :param source: The memory the question is put to.
        """
        query = self.query(source)
        query.build()
        return [
            descendant._type_
            for descendant in query._descendants_
            if isinstance(descendant, InstantiatedVariable)
            and self.is_a_predicate(descendant._type_)
        ]

    @staticmethod
    def is_a_predicate(applied: Any) -> bool:
        """
        Whether what a query applies to the things it ranges over is a predicate: one of
        the predicate classes, or a function the query language made symbolic.

        :param applied: What the query applies.
        """
        if isinstance(applied, type):
            return issubclass(applied, Predicate)
        return callable(applied)

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

        A true answer stated in a currency of its own says for itself whether the answer
        is it.

        :param answered: What a question answered, or one element of it.
        :param true: What the representation actually holds, or one element of it.
        """
        if isinstance(true, TrueAnswer):
            return true.agrees_with(answered)
        if isinstance(answered, SpatialType):
            return np.allclose(answered.to_np(), true.to_np())
        if isinstance(answered, list):
            return len(answered) == len(true) and all(
                cls.values_agree(one, other) for one, other in zip(answered, true)
            )
        return answered == true

    def to_json(self) -> Dict[str, Any]:
        """
        Serialize this question's own fields, which is what a recorded, scored query
        needs to keep - not only which subclass answered it, but which instance, since a
        long-term-memory question's own fields (which episode it is about) are part of
        what it asked.
        """
        return DataclassJSONSerializer.to_json(self)

    @classmethod
    def _from_json(cls, data: Dict[str, Any], **kwargs) -> Question:
        return DataclassJSONSerializer.from_json(data, clazz=cls, **kwargs)


# %% what a scene fills in


@dataclass
class QuestionedThings:
    """
    What a scene fills in for the questions of the set: the things the ones about a
    single thing single out, and the account of itself they are all scored against.
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

    scene: SceneAsSetUp
    """
    The scene as whoever set it up knows it, which is what its questions are scored
    against.
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
