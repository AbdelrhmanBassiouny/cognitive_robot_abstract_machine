"""
The questions asked of what the robot holds right now.

Working memory is the twin as it currently is together with the events the segmentation
has seen in it. Nothing here is handed to a question: every variable ranges over what
the symbol graph already tracks, and what a question is about is said as a condition on
it. Answering them exercises understanding -- everything they ask about is already
represented, and the query only has to interpret it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from krrood.entity_query_language.factories import (
    an,
    contains,
    entity,
    not_,
    variable,
)
from krrood.entity_query_language.predicate import symbolic_function
from krrood.entity_query_language.query.query import Query
from krrood.symbol_graph.symbol_graph import SymbolGraph
from segmind.datastructures.events import (
    DetectionEvent,
    ManipulatesBodies,
    MotionEvent,
    PickUpEvent,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import (
    LeftOf,
    RightOf,
    ViewDependentSpatialRelation,
    is_supported_by,
)
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world_description.connections import ActiveConnection
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Any, ClassVar, Generic, List, Tuple, Type

from experiments.questions.question import (
    AnswerType,
    BloomLevel,
    Bucket,
    Memory,
    Question,
    QuestionedThings,
    RequiredFact,
)

# %% what a live question is asked of


@dataclass
class WorkingMemoryQuestion(
    Question[AbstractRobot, AnswerType], Generic[AnswerType], ABC
):
    """
    A question answered from what the robot holds right now.

    Asked of the robot rather than of a store, because the robot is whose memory it is:
    which links it is made of and what hangs off its hand are read from it, and
    everything else the question needs is already tracked and reached by a variable of
    the type it is about.
    """

    memory: ClassVar[Memory] = Memory.WORKING
    """
    Working memory, which is what makes this an understanding question.
    """

    bloom_level: ClassVar[BloomLevel] = BloomLevel.UNDERSTANDING
    """
    Everything asked here is already represented, so answering it is interpretation
    rather than recall.
    """

    def solutions(self, source: AbstractRobot) -> List[Any]:
        """
        Every solution this question's query has over the live twin.

        :param source: The robot the question is put to.
        """
        return list(self.query(source).evaluate())

    @classmethod
    def asked_of(cls, things: QuestionedThings) -> List[WorkingMemoryQuestion]:
        """
        How this question is put to a scene, which is once and about nothing in
        particular unless it singles something out.

        :param things: What the scene fills in for the questions about one thing.
        """
        return [cls()]

    def remembered_events(self, kind: Type[DetectionEvent]) -> List[DetectionEvent]:
        """
        What the segmentation has seen happen, of one kind.

        Read off the symbol graph for the same reason the queries range over it: an
        event is tracked from the moment it is made, so nothing has to be handed a log.

        :param kind: The kind of event to read.
        """
        return list(SymbolGraph().get_instances_of_type(kind))


# %% what a question says about the scene rather than hands to it


@symbolic_function
def has_a_shape(body: Body) -> bool:
    """
    Whether a body is one the robot can be asked about as an object.

    :param body: The body to judge.
    """
    return body.has_collision()


class Side(StrEnum):
    """
    One of the two sides a view-dependent question asks about.
    """

    LEFT = "left"
    RIGHT = "right"

    @property
    def relation(self) -> Type[ViewDependentSpatialRelation]:
        """
        The twin's relation that holds when something is on this side.
        """
        if self is Side.LEFT:
            return LeftOf
        return RightOf


@symbolic_function
def is_on_side_of(
    subject: Body,
    other: Body,
    side: Side,
    point_of_view: HomogeneousTransformationMatrix,
) -> bool:
    """
    Whether one body is on the given side of another, seen from the given place.

    The twin relates points rather than bodies, so this is what lets a question about
    two objects be asked in the query language.

    :param subject: The body the question is about.
    :param other: The body it is placed against.
    :param side: Which side is being asked about.
    :param point_of_view: Where the two are looked at from.
    """
    relation = side.relation(
        subject.center_of_mass, other.center_of_mass, point_of_view
    )
    return bool(relation())


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


# %% scene


@dataclass
class ObjectsSeen(WorkingMemoryQuestion[List[Body]]):
    """
    Which objects the robot has in front of it.
    """

    bucket: ClassVar[Bucket] = Bucket.SCENE
    """
    The plainest scene question there is.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.OBJECT_SHAPES,)
    """
    An object is something with a shape, so nothing else has to be there.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "What objects do you see now?"

    def query(self, source: AbstractRobot) -> Query:
        """
        Every body with a shape that is not one of the robot's own.

        :param source: The robot the question is put to.
        """
        body = variable(Body)
        return an(
            entity(body).where(has_a_shape(body), not_(contains(source.bodies, body)))
        )

    def ground_truth(self, source: AbstractRobot) -> List[Body]:
        """
        The objects the twin holds, read off it directly.

        :param source: The robot whose scene it is.
        """
        return objects_of_the_scene(source)


@dataclass
class ObjectColours(WorkingMemoryQuestion[List[Color]]):
    """
    What colour each object in front of the robot is.
    """

    bucket: ClassVar[Bucket] = Bucket.SCENE
    """
    A property of the objects the scene holds.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.OBJECT_SHAPES,
        RequiredFact.OBJECT_COLOURS,
    )
    """
    A colour is carried by a shape, so both have to be there.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "What colours are they?"

    def query(self, source: AbstractRobot) -> Query:
        """
        The shapes every object is made of.

        ..note:: The shapes rather than their colours, because a shape is not tracked as
            a symbol, so a variable cannot range over one and the colour has to be read
            off the shape the query selected.

        :param source: The robot the question is put to.
        """
        body = variable(Body)
        return an(
            entity(body.collision.shapes).where(
                has_a_shape(body), not_(contains(source.bodies, body))
            )
        )

    def ask(self, source: AbstractRobot) -> List[Color]:
        """
        The colour of every shape the query selected.

        :param source: The robot the question is put to.
        """
        return [shape.color for shapes in self.solutions(source) for shape in shapes]

    def ground_truth(self, source: AbstractRobot) -> List[Color]:
        """
        The colours the twin holds, read off it directly.

        :param source: The robot whose scene it is.
        """
        return [
            shape.color
            for body in objects_of_the_scene(source)
            for shape in body.collision.shapes
        ]


@dataclass
class ObjectPlaces(WorkingMemoryQuestion[List[Pose]]):
    """
    Where each object in front of the robot is.
    """

    bucket: ClassVar[Bucket] = Bucket.SCENE
    """
    Where the scene's objects are.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.OBJECT_SHAPES,
        RequiredFact.OBJECT_PLACES,
    )
    """
    A place is only ever the place of something, so the objects have to be there too.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Where are they?"

    def query(self, source: AbstractRobot) -> Query:
        """
        Where every object stands in the world.

        :param source: The robot the question is put to.
        """
        body = variable(Body)
        return an(
            entity(body.global_pose).where(
                has_a_shape(body), not_(contains(source.bodies, body))
            )
        )

    def ground_truth(self, source: AbstractRobot) -> List[Pose]:
        """
        The places the twin holds, read off it directly.

        :param source: The robot whose scene it is.
        """
        return [body.global_pose for body in objects_of_the_scene(source)]


# %% support and spatial relations


@dataclass
class SupportingSurfaces(WorkingMemoryQuestion[List[Body]]):
    """
    What one object is standing on.
    """

    bucket: ClassVar[Bucket] = Bucket.SUPPORT_AND_SPATIAL_RELATIONS
    """
    Support is the relation this asks about.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.OBJECT_SHAPES,
        RequiredFact.OBJECT_PLACES,
        RequiredFact.SUPPORT_RELATIONS,
    )
    """
    Support is read off where the shapes are, so all three have to be there.
    """

    subject: Body
    """
    The object the question is about.
    """

    @classmethod
    def asked_of(cls, things: QuestionedThings) -> List[SupportingSurfaces]:
        """
        Asked about the one object the scene singles out.

        :param things: What the scene fills in for the questions about one thing.
        """
        return [cls(subject=things.object_asked_about)]

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "What surface is the %s standing on?" % self.subject.name.name

    def query(self, source: AbstractRobot) -> Query:
        """
        Every object the subject stands on.

        :param source: The robot the question is put to.
        """
        surface = variable(Body)
        return an(
            entity(surface).where(
                has_a_shape(surface),
                not_(contains(source.bodies, surface)),
                is_supported_by(self.subject, surface),
            )
        )

    def ground_truth(self, source: AbstractRobot) -> List[Body]:
        """
        What the subject stands on, read off the twin directly.

        :param source: The robot whose scene it is.
        """
        return [
            surface
            for surface in objects_of_the_scene(source)
            if is_supported_by(self.subject, surface)
        ]


@dataclass
class SideOfAnotherObject(WorkingMemoryQuestion[bool]):
    """
    Whether one object is to a given side of another.
    """

    bucket: ClassVar[Bucket] = Bucket.SUPPORT_AND_SPATIAL_RELATIONS
    """
    A spatial relation between two objects.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.OBJECT_SHAPES,
        RequiredFact.OBJECT_PLACES,
        RequiredFact.POINT_OF_VIEW,
    )
    """
    Left and right are only left and right from somewhere, so where the scene is looked
    at from is part of what this needs.
    """

    subject: Body
    """
    The object the question is about.
    """

    other: Body
    """
    The object it is placed against.
    """

    side: Side
    """
    Which side is being asked about.
    """

    point_of_view: HomogeneousTransformationMatrix
    """
    Where the scene is looked at from, which is what makes left and right mean anything.

    ..note:: Part of what is asked rather than of what answers it: a robot that carries
        a camera is looked at the scene from it, and a question about a view nobody
        holds still has to say which view it means.
    """

    @classmethod
    def asked_of(cls, things: QuestionedThings) -> List[SideOfAnotherObject]:
        """
        Asked once per side, because a question answering which of the two holds needs
        either a branch in python or an aggregate the query language does not translate.

        :param things: What the scene fills in for the questions about one thing.
        """
        return [
            cls(
                subject=things.object_asked_about,
                other=things.object_compared_against,
                side=side,
                point_of_view=things.point_of_view,
            )
            for side in Side
        ]

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Is the %s %s of the %s?" % (
            self.subject.name.name,
            self.side,
            self.other.name.name,
        )

    def query(self, source: AbstractRobot) -> Query:
        """
        The subject, if it is on that side of the other object.

        :param source: The robot the question is put to.
        """
        body = variable(Body)
        return an(
            entity(body).where(
                body == self.subject,
                is_on_side_of(body, self.other, self.side, self.point_of_view),
            )
        )

    def ask(self, source: AbstractRobot) -> bool:
        """
        Whether the subject is on that side of the other object.

        :param source: The robot the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: AbstractRobot) -> bool:
        """
        Which side the subject really is on, read off the twin directly.

        :param source: The robot whose scene it is.
        """
        relation = self.side.relation(
            self.subject.center_of_mass,
            self.other.center_of_mass,
            self.point_of_view,
        )
        return bool(relation())


# %% temporal and agency


@dataclass
class AnythingMoved(WorkingMemoryQuestion[bool]):
    """
    Whether anything moved while the robot was watching.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    A question about what happened rather than about what is.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.MOTION_EVENTS,)
    """
    Nothing but the motion the segmentation reported.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Did any object recently move?"

    def query(self, source: AbstractRobot) -> Query:
        """
        Every motion the segmentation reported.

        :param source: The robot the question is put to.
        """
        motion = variable(MotionEvent)
        return an(entity(motion))

    def ask(self, source: AbstractRobot) -> bool:
        """
        Whether anything moved.

        :param source: The robot the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: AbstractRobot) -> bool:
        """
        Whether anything the segmentation saw was a motion, read off it directly.

        :param source: The robot whose memory it is.
        """
        return bool(self.remembered_events(MotionEvent))


@dataclass
class ObjectsThatMoved(WorkingMemoryQuestion[List[Body]]):
    """
    Which objects moved while the robot was watching.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    Which things the reported motion was about.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.MOTION_EVENTS,)
    """
    Nothing but the motion the segmentation reported.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Which objects recently moved?"

    def query(self, source: AbstractRobot) -> Query:
        """
        What every reported motion was about.

        :param source: The robot the question is put to.
        """
        motion = variable(MotionEvent)
        return an(entity(motion.tracked_object))

    def ask(self, source: AbstractRobot) -> List[Body]:
        """
        The objects that moved, each named once however often it moved.

        :param source: The robot the question is put to.
        """
        return self.distinct(self.solutions(source))

    def ground_truth(self, source: AbstractRobot) -> List[Body]:
        """
        The objects the segmentation says moved, read off it directly.

        :param source: The robot whose memory it is.
        """
        return self.distinct(
            [event.tracked_object for event in self.remembered_events(MotionEvent)]
        )


@dataclass
class ObjectsTheRobotMoved(WorkingMemoryQuestion[List[Body]]):
    """
    Which of the objects that moved the robot moved itself.

    This is what a single observation cannot answer at all: it needs a store that kept
    what the robot did apart from what merely happened to be going on.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    The agency half of the bucket.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.MOTION_EVENTS,
        RequiredFact.PICK_UP_EVENTS,
    )
    """
    An object the robot moved is one it moved and acted on, so both kinds of event have
    to be there.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Did you move them?"

    def query(self, source: AbstractRobot) -> Query:
        """
        What every reported motion of an object the robot had picked up was about.

        Asked of every event in which the robot acted on a body rather than only of the
        pick-ups, so an object it placed or inserted counts as one it moved.

        ..note:: Spelled as a join rather than through ``exists``, which answers this
            shape with every object that moved whether the robot acted on it or not.

        :param source: The robot the question is put to.
        """
        motion = variable(MotionEvent)
        manipulation = variable(ManipulatesBodies)
        return an(
            entity(motion.tracked_object).where(
                contains(manipulation.manipulated_bodies, motion.tracked_object)
            )
        )

    def ask(self, source: AbstractRobot) -> List[Body]:
        """
        The objects the robot moved, each named once.

        :param source: The robot the question is put to.
        """
        return self.distinct(self.solutions(source))

    def ground_truth(self, source: AbstractRobot) -> List[Body]:
        """
        The objects the segmentation says the robot moved, read off it directly.

        :param source: The robot whose memory it is.
        """
        manipulated = {
            body
            for event in self.remembered_events(ManipulatesBodies)
            for body in event.manipulated_bodies
        }
        return self.distinct(
            [
                event.tracked_object
                for event in self.remembered_events(MotionEvent)
                if event.tracked_object in manipulated
            ]
        )


@dataclass
class PickedUpRecently(WorkingMemoryQuestion[bool]):
    """
    Whether one object was picked up while the robot was watching.
    """

    bucket: ClassVar[Bucket] = Bucket.TEMPORAL_AND_AGENCY
    """
    A question about one thing that happened.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (RequiredFact.PICK_UP_EVENTS,)
    """
    Nothing but the pick-ups the segmentation reported.
    """

    subject: Body
    """
    The object the question is about.
    """

    @classmethod
    def asked_of(cls, things: QuestionedThings) -> List[PickedUpRecently]:
        """
        Asked about the one object the scene singles out.

        :param things: What the scene fills in for the questions about one thing.
        """
        return [cls(subject=things.object_asked_about)]

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Was the %s recently picked up?" % self.subject.name.name

    def query(self, source: AbstractRobot) -> Query:
        """
        Every reported pick-up of the subject.

        :param source: The robot the question is put to.
        """
        pick_up = variable(PickUpEvent)
        return an(entity(pick_up).where(pick_up.tracked_object == self.subject))

    def ask(self, source: AbstractRobot) -> bool:
        """
        Whether the subject was picked up.

        :param source: The robot the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: AbstractRobot) -> bool:
        """
        Whether the segmentation saw the subject picked up, read off it directly.

        :param source: The robot whose memory it is.
        """
        return any(
            event.tracked_object is self.subject
            for event in self.remembered_events(PickUpEvent)
        )


# %% embodiment


@dataclass
class HeldInTheHand(WorkingMemoryQuestion[bool]):
    """
    Whether the robot is holding one object right now.

    Answered from what the twin has hanging off the robot rather than from the geometry
    between its fingers: working memory is what the robot believes it is holding, which
    is what a grasp writes into the twin and what a release takes out of it again.
    """

    bucket: ClassVar[Bucket] = Bucket.EMBODIMENT
    """
    The robot's own relation to an object.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.KINEMATIC_STRUCTURE,
        RequiredFact.ATTACHMENTS,
    )
    """
    A held object hangs from the robot, so both the structure and what was attached to
    it have to be there.
    """

    subject: Body
    """
    The object the question is about.
    """

    @classmethod
    def asked_of(cls, things: QuestionedThings) -> List[HeldInTheHand]:
        """
        Asked about the object the scene put in the robot's hand.

        :param things: What the scene fills in for the questions about one thing.
        """
        return [cls(subject=things.object_in_the_hand)]

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Is the %s currently in your hand?" % self.subject.name.name

    def query(self, source: AbstractRobot) -> Query:
        """
        The subject, if it hangs from one of the robot's own links.

        :param source: The robot the question is put to.
        """
        held = variable(Body)
        return an(
            entity(held).where(
                held == self.subject,
                contains(source.bodies, held.parent_kinematic_structure_entity),
            )
        )

    def ask(self, source: AbstractRobot) -> bool:
        """
        Whether the robot is holding the subject.

        :param source: The robot the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: AbstractRobot) -> bool:
        """
        What the twin has the subject hanging from, read off it directly.

        :param source: The robot whose hand it is.
        """
        return self.subject.parent_kinematic_structure_entity in source.bodies


# %% self-model


@dataclass
class PlaceOfOwnBody(WorkingMemoryQuestion[Pose]):
    """
    Where one of the robot's own links is.
    """

    bucket: ClassVar[Bucket] = Bucket.SELF_MODEL
    """
    A question about the robot's own body.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.KINEMATIC_STRUCTURE,
        RequiredFact.OBJECT_PLACES,
    )
    """
    Where a link is follows from the structure it hangs in.
    """

    body_name: PrefixedName
    """
    The link the question is about.
    """

    @classmethod
    def asked_of(cls, things: QuestionedThings) -> List[PlaceOfOwnBody]:
        """
        Asked about the robot's own link the scene singles out.

        :param things: What the scene fills in for the questions about one thing.
        """
        return [cls(body_name=things.own_body_asked_about)]

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Where is your %s located?" % self.body_name.name

    def query(self, source: AbstractRobot) -> Query:
        """
        Where the named link stands in the world.

        :param source: The robot the question is put to.
        """
        own = variable(Body)
        return an(
            entity(own.global_pose).where(
                contains(source.bodies, own), own.name == self.body_name
            )
        )

    def ask(self, source: AbstractRobot) -> Pose:
        """
        Where the named link is.

        :param source: The robot the question is put to.
        """
        (place,) = self.solutions(source)
        return place

    def ground_truth(self, source: AbstractRobot) -> Pose:
        """
        Where the twin puts the named link, read off it directly.

        :param source: The robot whose link it is.
        """
        return source._world.get_body_by_name(self.body_name).global_pose


@dataclass
class NumberOfOwnParts(WorkingMemoryQuestion[int], ABC):
    """
    How many of one kind of part the robot is made of.
    """

    bucket: ClassVar[Bucket] = Bucket.SELF_MODEL
    """
    A question about the robot's own body.
    """

    @abstractmethod
    def parts(self, source: AbstractRobot) -> List[Any]:
        """
        The robot's own parts of the kind this question counts.

        :param source: The robot the question is put to.
        """

    def ask(self, source: AbstractRobot) -> int:
        """
        How many parts the query selected.

        ..note:: Counted off the selected parts rather than by an aggregate, so that the
            same spelling answers this over a recorded run, where every row a query
            returns is converted into a part before anything can be counted. Counted
            once each, because a part reached by two of the conditions that select it is
            one part.

        :param source: The robot the question is put to.
        """
        return len(self.distinct(self.solutions(source)))

    def ground_truth(self, source: AbstractRobot) -> int:
        """
        How many the twin holds, counted off it directly.

        :param source: The robot whose body it is.
        """
        return len(self.parts(source))


@dataclass
class NumberOfOwnBodies(NumberOfOwnParts):
    """
    How many links the robot is made of.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.KINEMATIC_STRUCTURE,
    )
    """
    Counting links needs nothing but the structure they form.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "How many links do you have?"

    def parts(self, source: AbstractRobot) -> List[Body]:
        """
        The robot's own links.

        :param source: The robot whose body it is.
        """
        return source.bodies

    def query(self, source: AbstractRobot) -> Query:
        """
        Every link the robot is made of.

        :param source: The robot the question is put to.
        """
        own = variable(Body)
        return an(entity(own).where(contains(source.bodies, own)))


@dataclass
class NumberOfOwnDegreesOfFreedom(NumberOfOwnParts):
    """
    How many joints the robot is made of.

    Counted as degrees of freedom rather than as connections, because a fixed connection
    joins two links without being a joint anything can move.
    """

    required_facts: ClassVar[Tuple[RequiredFact, ...]] = (
        RequiredFact.KINEMATIC_STRUCTURE,
        RequiredFact.DEGREES_OF_FREEDOM,
    )
    """
    The degrees of freedom hang off the connections the structure is made of.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "How many joints do you have?"

    def parts(self, source: AbstractRobot) -> List[DegreeOfFreedom]:
        """
        The degrees of freedom the robot can move along.

        ..note:: Read off the connections between two of its own links that are actively
            controlled, so a fixed connection contributes none and neither does the one
            an object it is holding hangs by.

        :param source: The robot whose body it is.
        """
        own = set(source.bodies)
        return [
            degree_of_freedom
            for connection in source._world.connections
            if isinstance(connection, ActiveConnection)
            and connection.parent in own
            and connection.child in own
            for degree_of_freedom in connection.active_dofs
        ]

    def query(self, source: AbstractRobot) -> Query:
        """
        Every degree of freedom a connection between two of the robot's links carries.

        :param source: The robot the question is put to.
        """
        connection = variable(ActiveConnection)
        degree_of_freedom = variable(DegreeOfFreedom)
        return an(
            entity(degree_of_freedom).where(
                contains(source.bodies, connection.parent),
                contains(source.bodies, connection.child),
                contains(connection.active_dofs, degree_of_freedom),
            )
        )
