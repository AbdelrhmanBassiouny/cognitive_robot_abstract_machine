from __future__ import annotations

from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property

from typing_extensions import Any, Optional, List, Tuple

from krrood.entity_query_language.backends import StatedRelation
from segmind.datastructures.object_tracker import (
    ObjectEventTracker,
    ObjectTrackerFactory,
)
from segmind.exceptions import EventNamesNoObject
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.spatial_types.numeric import NumericPose
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.world_entity import (
    Body,
    KinematicStructureEntity,
    Region,
)


@dataclass
class DetectionEvent(ABC):
    timestamp: datetime = field(default_factory=datetime.now)
    """
    The time at which the event occurred, defaults to current time.
    """

    @abstractmethod
    def __eq__(self, other):
        pass

    @abstractmethod
    def __hash__(self):
        pass

    @abstractmethod
    def __str__(self):
        pass

    def __repr__(self):
        return self.__str__()


@dataclass(kw_only=True)
class EventWithTrackedObjects(DetectionEvent, ABC):
    """
    An abstract event involving one or more tracked objects.

    Provides the primary :attr:`tracked_object` and an optional :attr:`with_object`,
    along with ORM frozen copies and per-object tracker access.
    """

    tracked_object: Body
    """The primary object involved in this event."""

    with_object: Optional[KinematicStructureEntity] = None
    """
    The secondary object involved in this event, if any.

    Usually a :class:`~semantic_digital_twin.world_description.world_entity.Body`; a
    hole-related event (e.g. contact with an
    :class:`~semantic_digital_twin.semantic_annotations.semantic_annotations.Aperture`)
    sets this to that aperture's own
    :class:`~semantic_digital_twin.world_description.world_entity.Region` root instead,
    since an aperture is a virtual opening rather than a collidable body.
    """

    @property
    def tracked_objects(self) -> List[KinematicStructureEntity]:
        """
        :return: the primary object, plus the secondary object when present.
        """
        return (
            [self.tracked_object]
            if self.with_object is None
            else [self.tracked_object, self.with_object]
        )

    @cached_property
    def object_tracker(self) -> ObjectEventTracker:
        """
        :return: the event tracker for :attr:`tracked_object`.
        """
        return ObjectTrackerFactory.get_tracker(self.tracked_object)

    @cached_property
    def with_object_tracker(self) -> Optional[ObjectEventTracker]:
        """
        :return: the event tracker for :attr:`with_object`, or ``None`` if absent.
        """
        return (
            ObjectTrackerFactory.get_tracker(self.with_object)
            if self.with_object is not None
            else None
        )

    def update_object_trackers_with_event(self, factory: ObjectTrackerFactory) -> None:
        """
        Register this event with the tracker of every involved object.

        :param factory: factory used to look up per-object trackers.
        """
        for obj in self.tracked_objects:
            factory.get_tracker(obj).add_event(self)

    def __str__(self) -> str:
        names = " - ".join(str(obj.name) for obj in self.tracked_objects)
        return f"{self.__class__.__name__}: {names} - {self.timestamp}"

    def __eq__(self, other) -> bool:
        return (
            other.__class__ == self.__class__
            and self.tracked_objects == other.tracked_objects
            and self.timestamp == other.timestamp
        )

    def __hash__(self) -> int:
        return hash((self.__class__, tuple(self.tracked_objects), self.timestamp))


# %% what an event says now holds


@dataclass(frozen=True)
class Effect:
    """
    What an event says about the object it is about once it has happened, in the
    world's own vocabulary: the relations that hold of it from then on, the ones that
    stop holding, and the ones it is evidence about without settling.

    Each is stated about the object without the object standing in it, so what an
    event says can be applied to whatever was believed of the object before it.
    Everything an event says nothing about is left exactly as it was.
    """

    begins: Tuple[StatedRelation, ...] = ()
    """
    The relations that hold of the object once the event has happened.
    """

    ends: Tuple[StatedRelation, ...] = ()
    """
    The relations that stop holding of it, each read as covering every relation
    believed *before* the event that it states: one stating no operand ends every
    relation of its kind. What the event itself begins is never ended by it.
    """

    checks: Tuple[StatedRelation, ...] = ()
    """
    The relations the event is a reason to look at again rather than to settle: every
    believed relation one of these covers is asked of the object as it now stands, and
    kept only where it still holds.
    """

    def applied_to(
        self, held: Tuple[StatedRelation, ...], subject: Any
    ) -> Tuple[StatedRelation, ...]:
        """
        What holds of the object after this effect, given what was believed of it
        before.

        :param held: The relations believed to hold before the event.
        :param subject: The object the event is about, as it stands once the event has
            happened, which is what a relation the effect checks is asked of.
        """
        kept = [
            relation
            for relation in held
            if not self._ends(relation) and self._still_holds(relation, subject)
        ]
        return (*kept, *(begun for begun in self.begins if begun not in kept))

    def _ends(self, relation: StatedRelation) -> bool:
        """
        :param relation: One relation believed before the event.
        """
        return any(ended.covers(relation) for ended in self.ends)

    def _still_holds(self, relation: StatedRelation, subject: Any) -> bool:
        """
        :param relation: One relation believed before the event.
        :param subject: The object the event is about, as it stands now.
        :return: Whether the belief survives being checked, which every belief this
            effect does not check does.
        """
        if not any(checked.covers(relation) for checked in self.checks):
            return True
        return bool(relation.about(subject)())


@dataclass(kw_only=True)
class EventWithEffect(EventWithTrackedObjects, ABC):
    """
    An event that says what holds of its :attr:`tracked_object` once it has happened.

    An event is what was seen to happen, at a time, between the things it names; its
    effect is what is true of the world from then on. For an event named after the
    relation it detects the two nearly coincide, and for one named after what happened
    -- a pick-up, an insertion -- they do not, which is why the effect is stated on
    the event rather than read off its name.
    """

    @abstractmethod
    def effect(self) -> Effect:
        """
        What this event says holds of the object it is about, and what stops holding.
        """

    def _entity_it_names(self) -> KinematicStructureEntity:
        """
        The entity this event saw its object involved with.

        :raises EventNamesNoObject: If the event names none.
        """
        if self.with_object is None:
            raise EventNamesNoObject(event=str(self))
        return self.with_object

    def _region_it_names(self) -> Region:
        """
        The region this event saw its object involved with.

        :raises EventNamesNoObject: If the event names none, or names something that is
            not a region.
        """
        if not isinstance(self.with_object, Region):
            raise EventNamesNoObject(event=str(self))
        return self.with_object


SUPPORTED_BY_ANYTHING = StatedRelation(relation_type=SupportedBy)
"""
Resting on anything at all: every support believed before the event, whatever it
named, which an event that says what the object now rests on ends, and a pick-up ends
without saying what it rests on instead.
"""

INSIDE_ANY_REGION = StatedRelation(relation_type=InsideRegion)
"""
Lying in any region at all: every containment believed before the event, which a
pick-up is a reason to check.
"""


@dataclass(kw_only=True)
class ComesToRestEvent(EventWithEffect, ABC):
    """
    An event after which the object rests on what the event names, and on nothing else.
    """

    def effect(self) -> Effect:
        """
        The object rests on what this event names, instead of whatever it rested on
        before.
        """
        return Effect(
            begins=(StatedRelation.of(SupportedBy, self._entity_it_names()),),
            ends=(SUPPORTED_BY_ANYTHING,),
        )


@dataclass(unsafe_hash=True)
class SupportEvent(ComesToRestEvent):
    """
    The SupportEvent class is used to represent an event that involves an object that is supported by another object.
    """


@dataclass(unsafe_hash=True)
class LossOfSupportEvent(EventWithEffect):
    """
    The LossOfSupportEvent class is used to represent an event that involves an object that was supported by another
    object and then lost support.
    """

    def effect(self) -> Effect:
        """
        The object no longer rests on what this event names; what else it may rest on
        is left as it was.
        """
        return Effect(ends=(StatedRelation.of(SupportedBy, self._entity_it_names()),))


@dataclass(unsafe_hash=True)
class MotionEvent(EventWithTrackedObjects, ABC):
    """
    Used to represent an event that involves an object that was stationary and then moved or
    vice versa.
    """

    start_pose: Pose = field(default_factory=Pose)
    """
    The pose of the object at the start of the event.
    """
    current_pose: Pose = field(default_factory=Pose)
    """
    The pose of the object at the end of the event.
    """


@dataclass(init=False, unsafe_hash=True)
class TranslationEvent(MotionEvent):
    """
    Represents an event where an object moves from one location to another.
    """

    ...


@dataclass(init=False, unsafe_hash=True)
class RotationEvent(MotionEvent):
    """
    Represents an event where an object rotates around a center point.
    """

    ...


@dataclass(init=False, unsafe_hash=True)
class StopTranslationEvent(MotionEvent):
    """
    Represents an event where an object stops moving.
    """

    ...


@dataclass(init=False, unsafe_hash=True)
class StopRotationEvent(MotionEvent):
    """
    Represents an event where an object stops rotating.
    """

    ...


@dataclass(unsafe_hash=True)
class AbstractContactEvent(EventWithTrackedObjects, ABC):
    """
    Represents an event where two objects are in contact with each other.
    """

    contact_bodies: list[Body] = field(init=False, default_factory=list)
    """
    The bodies that are in contact with each other.
    """

    latest_contact_bodies: list[Body] = field(init=False, default_factory=list)
    """
    The bodies that were in contact with each other in the previous time step.
    """

    bounding_box: VolumetricBoundingBox = field(init=False)
    """
    Bounding box of the object.
    """

    pose: NumericPose = field(init=False)
    """
    Pose of the object, read out into numbers so a detector thread can record it.
    """

    with_object_bounding_box: Optional[VolumetricBoundingBox] = field(
        init=False, default=None
    )
    """
    Bounding box of the second object in contact.
    """

    with_object_pose: Optional[NumericPose] = field(init=False, default=None)
    """
    Pose of the second object in contact, read out into numbers.
    """

    def __post_init__(self):
        # combined_mesh (not tracked_object.collision.combined_mesh directly) so this
        # also works when with_object is a hole's Region root, which exposes its
        # geometry via .area rather than .collision.
        self.bounding_box = VolumetricBoundingBox.from_mesh(
            self.tracked_object.combined_mesh,
            origin=self.tracked_object.numeric_global_transform,
        )
        self.pose = self.tracked_object.numeric_global_pose

        if self.with_object is not None:
            self.with_object_bounding_box = VolumetricBoundingBox.from_mesh(
                self.with_object.combined_mesh,
                origin=self.with_object.numeric_global_transform,
            )
            self.with_object_pose = self.with_object.numeric_global_pose


@dataclass(init=False, unsafe_hash=True)
class ContactEvent(AbstractContactEvent):
    """
    Represents an event where two objects are in contact with each other.
    """

    ...


@dataclass(init=False, unsafe_hash=True)
class LossOfContactEvent(AbstractContactEvent):
    """
    Represents an event where two objects are no longer in contact with each other.
    """

    ...


@dataclass(unsafe_hash=True)
class PickUpEvent(EventWithEffect):
    """
    Represents an event where an object is picked up by another object.
    """

    def effect(self) -> Effect:
        """
        Picked up, the object is held rather than supported, so it rests on nothing
        whatever it rested on before. Whether it still lies in a region it was believed
        in is not settled by the pick-up but checked against where the object now is: a
        piece lifted clear of a hole is no longer in it, one nudged within it still is.
        """
        return Effect(ends=(SUPPORTED_BY_ANYTHING,), checks=(INSIDE_ANY_REGION,))


@dataclass(unsafe_hash=True)
class PlacingEvent(ComesToRestEvent):
    """
    Represents an event where an object is placed on another object.
    """


@dataclass(unsafe_hash=True)
class InsertionEvent(EventWithEffect):
    """
    Represents an event where an object is inserted into another object.
    """

    inserted_into_objects: List[KinematicStructureEntity] = field(default_factory=list)
    """
    List of objects into which the object was inserted.

    A hole-related insertion sets this to the hole's own ``Region`` root (see
    :class:`~semantic_digital_twin.semantic_annotations.semantic_annotations.Aperture`),
    not a ``Body``, which is why this is stated over their common base.
    """

    through_hole: Optional[Aperture] = None
    """
    The aperture :attr:`~EventWithTrackedObjects.with_object` (its own ``Region`` root)
    was detected passing through.

    Set directly by the detector that builds this event, which already has the
    aperture in hand (via ``SegmindContext.holes``) rather than derived from
    ``with_object`` here: a hole's root is a virtual ``Region``, not a ``Body``, and has
    no reliable way to look its owning annotation back up on its own.
    """

    def effect(self) -> Effect:
        """
        The object lies in the region it was inserted into, and rests on nothing it
        rested on before it went in.
        """
        return Effect(
            begins=(StatedRelation.of(InsideRegion, self._region_it_names()),),
            ends=(SUPPORTED_BY_ANYTHING,),
        )

    def __str__(self) -> str:
        with_object_name = " - " + " - ".join(
            [str(obj.name) for obj in self.inserted_into_objects]
        )
        return f"{self.__class__.__name__}: {self.tracked_object.name}{with_object_name} - {self.timestamp}"


@dataclass(unsafe_hash=True)
class ContainmentEvent(EventWithTrackedObjects):
    """
    Represents an event where an object is contained in another object.
    """

    ...


@dataclass(unsafe_hash=True)
class LossOfContainmentEvent(EventWithTrackedObjects):
    """
    Represents an event where an object is no longer contained in another object.
    """

    ...
