"""
The questions asked of what the robot holds right now.

Working memory is the twin as it currently is together with the events the segmentation
has seen in it, so these questions are answered without reaching for a record of
anything. Answering them exercises understanding: everything they ask about is already
represented, and the query only has to interpret it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from krrood.entity_query_language.factories import (
    an,
    count,
    entity,
    exists,
    set_of,
    variable,
)
from krrood.entity_query_language.predicate import symbolic_function
from krrood.entity_query_language.query.query import Query
from segmind.datastructures.events import DetectionEvent, MotionEvent, PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import (
    LeftOf,
    RightOf,
    ViewDependentSpatialRelation,
    is_supported_by,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import ActiveConnection
from semantic_digital_twin.world_description.degree_of_freedom import DegreeOfFreedom
from semantic_digital_twin.world_description.geometry import Color, Shape
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Any, ClassVar, Generic, List, Tuple, Type

from experiments.questions.question import (
    AnswerType,
    BloomLevel,
    Bucket,
    Memory,
    Question,
    RequiredFact,
)

# %% what a question of this kind is asked of


@dataclass
class WorkingMemory:
    """
    What the robot holds right now: the twin as it currently is, and what the event
    segmentation has seen happen in it.
    """

    world: World
    """
    The twin the robot is acting in.
    """

    own_bodies: List[Body]
    """
    The links the robot is made of, as it was put into the world.

    Given rather than read off the kinematic structure, because an object the robot
    picks up hangs from one of its links without becoming one of them, and nothing in
    the twin tells the two apart afterwards.
    """

    point_of_view: HomogeneousTransformationMatrix
    """
    Where the scene is looked at from, which is what makes left and right mean anything.
    """

    events: List[DetectionEvent] = field(default_factory=list)
    """
    What the event segmentation has detected so far, oldest first.
    """

    @property
    def own_degrees_of_freedom(self) -> List[DegreeOfFreedom]:
        """
        The degrees of freedom the robot can move along.

        ..note:: Read off the connections between two of its own links that are actively
            controlled, so a fixed connection contributes none and neither does the one
            an object it is holding hangs by.
        """
        own = set(self.own_bodies)
        return [
            degree_of_freedom
            for connection in self.world.connections
            if isinstance(connection, ActiveConnection)
            and connection.parent in own
            and connection.child in own
            for degree_of_freedom in connection.active_dofs
        ]

    @property
    def objects(self) -> List[Body]:
        """
        The bodies around the robot that have a shape, which is what it can be asked
        about as an object.
        """
        own = set(self.own_bodies)
        return [body for body in self.world.bodies_with_collision if body not in own]

    @property
    def object_shapes(self) -> List[Shape]:
        """
        Every shape every object around the robot is made of, object by object.
        """
        return [shape for body in self.objects for shape in body.collision.shapes]


@dataclass
class WorkingMemoryQuestion(
    Question[WorkingMemory, AnswerType], Generic[AnswerType], ABC
):
    """
    A question answered from what the robot holds right now.
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

    def solutions(self, source: WorkingMemory) -> List[Any]:
        """
        Every solution this question's query has over the live twin.

        :param source: The working memory the question is put to.
        """
        return list(self.query(source).evaluate())


# %% which side of another object something is on


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

    def query(self, source: WorkingMemory) -> Query:
        """
        Every object the twin holds.

        :param source: The working memory the question is put to.
        """
        body = variable(Body, domain=source.objects)
        return an(entity(body))

    def ground_truth(self, source: WorkingMemory) -> List[Body]:
        """
        The objects the twin holds, read off it directly.

        :param source: The working memory holding what is actually there.
        """
        return source.objects


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

    def query(self, source: WorkingMemory) -> Query:
        """
        The colour of every shape every object is made of.

        :param source: The working memory the question is put to.
        """
        shape = variable(Shape, domain=source.object_shapes)
        return an(entity(shape.color))

    def ground_truth(self, source: WorkingMemory) -> List[Color]:
        """
        The colours the twin holds, read off it directly.

        :param source: The working memory holding what is actually there.
        """
        return [shape.color for shape in source.object_shapes]


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

    def query(self, source: WorkingMemory) -> Query:
        """
        Where every object stands in the world.

        :param source: The working memory the question is put to.
        """
        body = variable(Body, domain=source.objects)
        return an(entity(body.global_pose))

    def ground_truth(self, source: WorkingMemory) -> List[Pose]:
        """
        The places the twin holds, read off it directly.

        :param source: The working memory holding what is actually there.
        """
        return [body.global_pose for body in source.objects]


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

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "What surface is the %s standing on?" % self.subject.name.name

    def query(self, source: WorkingMemory) -> Query:
        """
        Every object the subject stands on.

        :param source: The working memory the question is put to.
        """
        surface = variable(Body, domain=source.objects)
        return an(entity(surface).where(is_supported_by(self.subject, surface)))

    def ground_truth(self, source: WorkingMemory) -> List[Body]:
        """
        What the subject stands on, read off the twin directly.

        :param source: The working memory holding what is actually there.
        """
        return [
            surface
            for surface in source.objects
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

    def query(self, source: WorkingMemory) -> Query:
        """
        The subject, if it is on that side of the other object.

        :param source: The working memory the question is put to.
        """
        body = variable(Body, domain=[self.subject])
        return an(
            entity(body).where(
                is_on_side_of(body, self.other, self.side, source.point_of_view)
            )
        )

    def ask(self, source: WorkingMemory) -> bool:
        """
        Whether the subject is on that side of the other object.

        :param source: The working memory the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: WorkingMemory) -> bool:
        """
        Which side the subject really is on, read off the twin directly.

        :param source: The working memory holding what is actually there.
        """
        relation = self.side.relation(
            self.subject.center_of_mass,
            self.other.center_of_mass,
            source.point_of_view,
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

    def query(self, source: WorkingMemory) -> Query:
        """
        Every motion the segmentation reported.

        :param source: The working memory the question is put to.
        """
        motion = variable(MotionEvent, domain=source.events)
        return an(entity(motion))

    def ask(self, source: WorkingMemory) -> bool:
        """
        Whether anything moved.

        :param source: The working memory the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: WorkingMemory) -> bool:
        """
        Whether the event log holds a motion, read off it directly.

        :param source: The working memory holding what actually happened.
        """
        return any(isinstance(event, MotionEvent) for event in source.events)


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

    def query(self, source: WorkingMemory) -> Query:
        """
        What every reported motion was about.

        :param source: The working memory the question is put to.
        """
        motion = variable(MotionEvent, domain=source.events)
        return an(entity(motion.tracked_object))

    def ground_truth(self, source: WorkingMemory) -> List[Body]:
        """
        The objects the event log says moved, read off it directly.

        :param source: The working memory holding what actually happened.
        """
        return [
            event.tracked_object
            for event in source.events
            if isinstance(event, MotionEvent)
        ]


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
    An object the robot moved is one it moved and had picked up, so both kinds of event
    have to be there.
    """

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Did you move them?"

    def query(self, source: WorkingMemory) -> Query:
        """
        What every reported motion of an object the robot had picked up was about.

        :param source: The working memory the question is put to.
        """
        motion = variable(MotionEvent, domain=source.events)
        pick_up = variable(PickUpEvent, domain=source.events)
        return an(
            entity(motion.tracked_object).where(
                exists(pick_up, pick_up.tracked_object == motion.tracked_object)
            )
        )

    def ground_truth(self, source: WorkingMemory) -> List[Body]:
        """
        The objects the event log says the robot moved, read off it directly.

        :param source: The working memory holding what actually happened.
        """
        picked_up = {
            event.tracked_object
            for event in source.events
            if isinstance(event, PickUpEvent)
        }
        return [
            event.tracked_object
            for event in source.events
            if isinstance(event, MotionEvent) and event.tracked_object in picked_up
        ]


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

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Was the %s recently picked up?" % self.subject.name.name

    def query(self, source: WorkingMemory) -> Query:
        """
        Every reported pick-up of the subject.

        :param source: The working memory the question is put to.
        """
        pick_up = variable(PickUpEvent, domain=source.events)
        return an(entity(pick_up).where(pick_up.tracked_object == self.subject))

    def ask(self, source: WorkingMemory) -> bool:
        """
        Whether the subject was picked up.

        :param source: The working memory the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: WorkingMemory) -> bool:
        """
        Whether the event log holds a pick-up of the subject, read off it directly.

        :param source: The working memory holding what actually happened.
        """
        return any(
            isinstance(event, PickUpEvent) and event.tracked_object is self.subject
            for event in source.events
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

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Is the %s currently in your hand?" % self.subject.name.name

    def query(self, source: WorkingMemory) -> Query:
        """
        The subject, if it hangs from one of the robot's own links.

        :param source: The working memory the question is put to.
        """
        held = variable(Body, domain=[self.subject])
        own = variable(Body, domain=source.own_bodies)
        return an(
            entity(held).where(
                exists(own, held.parent_kinematic_structure_entity == own)
            )
        )

    def ask(self, source: WorkingMemory) -> bool:
        """
        Whether the robot is holding the subject.

        :param source: The working memory the question is put to.
        """
        return bool(self.solutions(source))

    def ground_truth(self, source: WorkingMemory) -> bool:
        """
        What the twin has the subject hanging from, read off it directly.

        :param source: The working memory holding what is actually there.
        """
        return self.subject.parent_kinematic_structure_entity in source.own_bodies


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

    @property
    def english(self) -> str:
        """
        The question as a person would ask it.
        """
        return "Where is your %s located?" % self.body_name.name

    def query(self, source: WorkingMemory) -> Query:
        """
        Where the named link stands in the world.

        :param source: The working memory the question is put to.
        """
        own = variable(Body, domain=source.own_bodies)
        return an(entity(own.global_pose).where(own.name == self.body_name))

    def ask(self, source: WorkingMemory) -> Pose:
        """
        Where the named link is.

        :param source: The working memory the question is put to.
        """
        (place,) = self.solutions(source)
        return place

    def ground_truth(self, source: WorkingMemory) -> Pose:
        """
        Where the twin puts the named link, read off it directly.

        :param source: The working memory holding what is actually there.
        """
        return source.world.get_body_by_name(self.body_name).global_pose


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
    def parts(self, source: WorkingMemory) -> List[Any]:
        """
        The robot's own parts of the kind this question counts.

        :param source: The working memory the question is put to.
        """

    def ask(self, source: WorkingMemory) -> int:
        """
        The number the query counted.

        :param source: The working memory the question is put to.
        """
        (solution,) = self.solutions(source)
        (number,) = solution.values()
        return number

    def ground_truth(self, source: WorkingMemory) -> int:
        """
        How many the twin holds, counted off it directly.

        :param source: The working memory holding what is actually there.
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

    def parts(self, source: WorkingMemory) -> List[Body]:
        """
        The robot's own links.

        :param source: The working memory the question is put to.
        """
        return source.own_bodies

    def query(self, source: WorkingMemory) -> Query:
        """
        How many links the robot has.

        :param source: The working memory the question is put to.
        """
        own = variable(Body, domain=self.parts(source))
        return set_of(count(own))


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

    def parts(self, source: WorkingMemory) -> List[DegreeOfFreedom]:
        """
        The degrees of freedom the robot can move along.

        :param source: The working memory the question is put to.
        """
        return source.own_degrees_of_freedom

    def query(self, source: WorkingMemory) -> Query:
        """
        How many degrees of freedom the robot has.

        :param source: The working memory the question is put to.
        """
        degree_of_freedom = variable(DegreeOfFreedom, domain=self.parts(source))
        return set_of(count(degree_of_freedom))
