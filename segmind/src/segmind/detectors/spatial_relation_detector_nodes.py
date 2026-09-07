from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Set

from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import (
    DetectionEvent,
    SupportEvent,
    LossOfSupportEvent,
    ContainmentEvent,
    LossOfContainmentEvent, ContactEvent, LossOfContactEvent, InsertionEvent,
)

from semantic_digital_twin.reasoning.predicates import is_supported_by, is_body_in_region, InsideOf
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.world_description.world_entity import Body, KinematicStructureEntity, Region

from segmind.detectors.base import AbstractDetector, SegmindContext

HOLE_CONTACT_OVERLAP_THRESHOLD = 0.02
"""
Minimum fraction of a tracked object's own volume that must overlap a hole's Region for
:class:`HoleContactDetector` to consider it touching that hole.

A hole's Region is a thin marker flush with its opening (e.g. 5 mm thick for the
Montessori board's holes); measured against the real board, a shape centered on a hole
overlaps it at roughly 0.17, while a shape merely above or below the hole measures 0.0,
so a low threshold well under that peak is a reliable "started touching the hole"
signal without being so low that mesh-boundary noise trips it.
"""


@dataclass(eq=False, repr=False)
class HoleContactDetector(AbstractDetector):
    """
    Detects when a tracked object's volume starts overlapping one of the scene's
    registered holes (:attr:`SegmindContext.holes`).

    A hole (:class:`~semantic_digital_twin.semantic_annotations.semantic_annotations.Aperture`)
    is rooted in a virtual :class:`~semantic_digital_twin.world_description.world_entity.Region`,
    never registered with the world's collision manager, so :func:`~semantic_digital_twin.reasoning.predicates.contact`
    (which queries that manager) can never see it; this checks a fractional mesh-volume
    overlap instead, mirroring :class:`~segmind.detectors.atomic_event_detectors_nodes.ContactDetector`'s
    own new-contact bookkeeping and event shape so :class:`InsertionDetector` needs no
    change to keep watching for a "contact with a hole" :class:`~segmind.datastructures.events.ContactEvent`.
    """

    overlap_threshold: float = HOLE_CONTACT_OVERLAP_THRESHOLD
    """
    The minimum overlap fraction (see :data:`HOLE_CONTACT_OVERLAP_THRESHOLD`) for a
    tracked object to be considered touching a hole.
    """

    additional_candidates: Dict[Aperture, Region] = field(default_factory=dict)
    """
    An extra region checked alongside a given hole's own root, keyed by that hole.

    A hole's own root is often a thin marker flush with its opening (e.g. 5 mm thick
    for the Montessori board's holes); measured against a real, physically simulated
    fall (not a hand-stepped one), an object can cross a region that thin between one
    detector tick and the next without ever registering an overlap with it at all. A
    taller region built around the same hole (e.g. spanning its opening's full
    thickness) gives a much larger window during which a real fall is actually caught.
    A match against the extra region is still recorded against that hole's own root
    (see :meth:`~segmind.detectors.base.AbstractDetector.get_relation_to_holes`), so
    :class:`InsertionDetector` needs no change. Defaults to none, so every existing
    caller's behaviour is unchanged.
    """

    def update_context_and_events(
        self, context: MotionStatechartContext, segmind_context: SegmindContext, tracked_objects: List[Body]
    ) -> List[DetectionEvent]:
        """
        Detects newly established overlaps between tracked objects and holes.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objects: Bodies that should be evaluated for new hole contacts.
        :return: List of ContactEvent objects representing newly detected hole contacts.
        """
        events = []
        latest_hole_contacts = segmind_context.latest_hole_contacts
        new_contact_pairs = self.get_relation_to_holes(
            segmind_context,
            tracked_objects,
            lambda obj, hole_region: is_body_in_region(obj, hole_region) > self.overlap_threshold,
            additional_candidates=self.additional_candidates,
        )
        for obj, holes in new_contact_pairs.items():
            new_contacts = (
                holes if obj not in latest_hole_contacts else holes - latest_hole_contacts[obj]
            )
            if new_contacts:
                latest_hole_contacts.setdefault(obj, set()).update(new_contacts)
                events.extend(
                    [ContactEvent(tracked_object=obj, with_object=hole_region) for hole_region in new_contacts]
                )

        return events


@dataclass(eq=False, repr=False)
class LossOfHoleContactDetector(AbstractDetector):
    """
    Detects when a tracked object stops overlapping a hole it was previously touching
    (see :class:`HoleContactDetector`).
    """

    overlap_threshold: float = HOLE_CONTACT_OVERLAP_THRESHOLD
    """
    The minimum overlap fraction (see :data:`HOLE_CONTACT_OVERLAP_THRESHOLD`) for a
    tracked object to still be considered touching a hole.
    """

    additional_candidates: Dict[Aperture, Region] = field(default_factory=dict)
    """
    An extra region checked alongside a given hole's own root; see
    :attr:`HoleContactDetector.additional_candidates`. Must match what the paired
    :class:`HoleContactDetector` was given, so a contact recorded against one of them
    can also be recognized as lost.
    """

    def update_context_and_events(
        self, context: MotionStatechartContext, segmind_context: SegmindContext, tracked_objects: List[Body]
    ) -> List[DetectionEvent]:
        """
        Detects when previously overlapping hole contacts are no longer present.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objects: Bodies that should be evaluated for lost hole contacts.
        :return: List of LossOfContactEvent objects representing lost hole contacts.
        """
        new_contact_pairs = self.get_relation_to_holes(
            segmind_context,
            tracked_objects,
            lambda obj, hole_region: is_body_in_region(obj, hole_region) > self.overlap_threshold,
            additional_candidates=self.additional_candidates,
        )

        events = []
        for obj, holes in list(segmind_context.latest_hole_contacts.items()):
            loss_contacts = (
                holes.copy() if obj not in new_contact_pairs else holes - new_contact_pairs[obj]
            )
            if loss_contacts:
                segmind_context.latest_hole_contacts[obj] -= loss_contacts
                if not segmind_context.latest_hole_contacts[obj]:
                    segmind_context.latest_hole_contacts.pop(obj)

                events.extend(
                    [
                        LossOfContactEvent(tracked_object=obj, with_object=hole_region)
                        for hole_region in loss_contacts
                    ]
                )

        return events


@dataclass(eq=False, repr=False)
class SupportDetector(AbstractDetector):
    """
    Class for detecting and updating newly established support relationships.

    This class provides functionality to detect and update support relationships
    between physical bodies. It evaluates the given objects and generates events
    for newly established support connections. This can be useful in simulations
    or physics-based environments to monitor and handle dynamic interactions
    between objects.
    """

    def update_context_and_events(
        self, context:MotionStatechartContext, segmind_context:SegmindContext, objects_to_check: List[Body]
    ) -> List[DetectionEvent]:
        """
        Detects newly established support relationships.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param objects_to_check: Bodies that should be evaluated for new supports.
        :return: List of SupportEvent objects representing newly detected supports.
        """

        events = []
        latest_support = segmind_context.latest_support
        new_support_pairs = self.get_relation(context, objects_to_check, is_supported_by)
        for body, support in new_support_pairs.items():
            new_supports = (
                support
                if body not in latest_support
                else support - latest_support[body]
            )
            if new_supports:
                latest_support.setdefault(body, set()).update(new_supports)
                events.extend(
                    [
                        SupportEvent(tracked_object=body, with_object=s)
                        for s in new_supports
                    ]
                )

        return events


@dataclass(eq=False, repr=False)
class LossOfSupportDetector(AbstractDetector):
    """
    Detects and manages the loss of support relationships among objects.

    This class is a specialized support detector that identifies when previously
    registered support relationships are no longer present. It processes a given
    set of objects to detect and update the context with events signifying the loss
    of such support relationships. This functionality is particularly useful in
    simulation or analysis scenarios where maintaining updated context for object
    interactions is essential.
    """

    def update_context_and_events(
        self,context:MotionStatechartContext, segmind_context:SegmindContext , objects_to_check: List[Body]
    ) -> List[DetectionEvent]:
        """
        Detects when previously existing support relationships are lost.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param objects_to_check: Bodies that should be evaluated for lost supports.
        :return: List of LossOfSupportEvent objects representing removed supports.
        """

        events = []
        latest_support = segmind_context.latest_support
        new_support_pairs = self.get_relation(context, objects_to_check, is_supported_by)

        for body, support in list(latest_support.items()):
            loss_supports = support - new_support_pairs.get(body, set())

            if not loss_supports:
                continue

            segmind_context.latest_support[body] -= loss_supports
            if not segmind_context.latest_support[body]:
                segmind_context.latest_support.pop(body)

            events.extend(
                LossOfSupportEvent(tracked_object=body, with_object=s)
                for s in loss_supports
            )

        return events


@dataclass(eq=False, repr=False)
class BaseContainmentDetector(AbstractDetector):
    """
    Abstract base class for contaiment-based detectors.

    Provides shared functionality for detecting containment between
    bodies and generating events when containment relationships change.
    """

    containment_threshold: float = 0.9
    """
    The threshold for the containment ratio between two bodies to be considered containment.
    """

    additional_candidates: List[KinematicStructureEntity] = field(default_factory=list)
    """
    Extra containment candidates checked alongside ``context.world.bodies_with_collision``.

    ``bodies_with_collision`` only ever holds real, collidable ``Body`` entities; a
    caller that also wants containment checked against a virtual ``Region`` (e.g. a
    hole's own root, or a scene-specific volume such as the pocket a shape settles
    into once it has fallen through a hole) passes it here instead. Defaults to empty,
    so every existing caller's behaviour is unchanged.
    """

    def get_containment_pairs(
        self,context:MotionStatechartContext, tracked_objects: List[Body]
    ) -> Dict[Body, Set[Body]]:
        """
        Computes support relationships.

        :param tracked_objects: Bodies that should be checked.
        :return: Mapping of body → supporting bodies.
        """
        containment_pairs: Dict[Body, Set[Body]] = {}
        candidates = list(context.world.bodies_with_collision) + self.additional_candidates

        for obj in tracked_objects:
            containers = {
                candidate for candidate in candidates
                if obj is not candidate
                   and InsideOf(obj, candidate).compute_containment_ratio() > self.containment_threshold
            }
            if containers:
                containment_pairs[obj] = containers

        return containment_pairs

@dataclass(eq=False, repr=False)
class ContainmentDetector(BaseContainmentDetector):
    """
    Handles detection of containment events between objects.

    This class performs the task of identifying and updating containment relations between
    given objects. It determines when a new containment relationship is established and
    generates corresponding containment events. The purpose of this class is to provide
    event-driven responses based on the spatial interactions of objects.
    """

    def update_context_and_events(
        self, context:MotionStatechartContext, segmind_context:SegmindContext, objects_to_check: List[Body]
    ) -> List[DetectionEvent]:
        """
        Updates the tracking context with new containment relationships and generates
        containment events for identified changes. The function processes a list of
        objects, compares the current containment status against the latest tracked
        data, and generates events for any newly identified containment relationships.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param objects_to_check: List of Body objects to check for containment changes.
        :return: List of ContainmentEvent objects representing newly established containments.
        """
        new_containment_pairs = self.get_containment_pairs(context, objects_to_check)
        latest_containment = segmind_context.latest_containments
        events = []

        for obj, containment_list in new_containment_pairs.items():
            new_containments = containment_list - latest_containment.get(obj, set())

            if not new_containments:
                continue

            latest_containment.setdefault(obj, set()).update(new_containments)
            events.extend(
                ContainmentEvent(tracked_object=obj, with_object=c)
                for c in new_containments
            )

        return events


@dataclass(eq=False, repr=False)
class LossOfContainmentDetector(BaseContainmentDetector):
    """
    Detects and processes loss of containment events.

    The LossOfContainmentDetector class is responsible for identifying instances where an
    object loses containment with another object. It updates the current containment context
    and generates a list of events representing these loss of containment occurrences. This
    class extends BaseContainmentDetector and utilizes its utilities for containment
    verification and context management.

    """
    def update_context_and_events(
        self, context:MotionStatechartContext, segmind_context:SegmindContext, objects_to_check: List[Body]
    ) -> List[DetectionEvent]:
        """
        Updates the context with the latest containment pairs and generates events for
        any lost containments.

        This method checks the current state of containment pairs against the previously
        stored state in the context. If any containments have been lost, it removes
        them from the context and generates corresponding events.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param objects_to_check: List of Body objects to check for containment loss.
        :return: List of LossOfContainmentEvent objects representing the loss of containment.
        """
        new_containment_pairs = self.get_containment_pairs(context, objects_to_check)
        latest_containment = segmind_context.latest_containments
        events = []
        for obj, containment_list in list(latest_containment.items()):
            lost_containments = (
                containment_list.copy()
                if obj not in new_containment_pairs
                else containment_list - new_containment_pairs[obj]
            )
            if lost_containments:
                latest_containment[obj] -= lost_containments
                if not latest_containment[obj]:
                    latest_containment.pop(obj)
                events.extend(
                    [
                        LossOfContainmentEvent(tracked_object=obj, with_object=c)
                        for c in lost_containments
                    ]
                )

        return events



@dataclass(eq=False, repr=False)
class InsertionDetector(AbstractDetector):
    """
    Detects insertion events based on object interaction context.

    The InsertionDetector class is used to analyze the interaction between tracked
    objects and identify insertion events. It tracks specific events such as
    contacts and containment, and generates an InsertionEvent when specific
    conditions are met. The class leverages a context that holds relevant
    event logs and tracked objects.
    """

    shift_threshold: timedelta = timedelta(seconds=15.0)
    """
    The threshold for the time difference between two events to be considered an insertion.
    """

    def update_context_and_events(self, context:MotionStatechartContext, segmind_context:SegmindContext, tracked_objs: List[Body]) -> List[DetectionEvent]:
        """
        Updates context and processes tracked objects to generate a list of events.

        This method analyzes contact and containment events within the tracked objects,
        compares their timestamps with a threshold, and generates insertion events if
        specific conditions are met. It modifies the context state to track insertion
        pairs that have already been processed and ensures exclusivity during event
        generation.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objs: List of Body objects to analyze for insertion events.
        :return List of InsertionEvent objects representing detected insertions.
        """
        events = []
        hole_by_root = {hole.root: hole for hole in segmind_context.holes}
        contact_events = [i for i in segmind_context.logger.get_events() if isinstance(i, ContactEvent)]
        contact_events_with_holes = [i for i in contact_events if i.with_object in hole_by_root]
        containment_event = [i for i in segmind_context.logger.get_events() if isinstance(i, ContainmentEvent)]

        by_object = defaultdict(list)
        for i in contact_events_with_holes:
            by_object[i.tracked_object].append(i)

        for j in containment_event:
            for i in by_object.get(j.tracked_object, []):
                if abs(i.timestamp - j.timestamp) >= self.shift_threshold:
                    continue

                key = (i.tracked_object.id, i.with_object.id)
                if key in segmind_context.insertion_pairs:
                    continue

                segmind_context.insertion_pairs.add(key)

                events.append(
                    InsertionEvent(
                        tracked_object=i.tracked_object,
                        with_object=i.with_object,
                        inserted_into_objects=[j.with_object],
                        through_hole=hole_by_root[i.with_object],
                    )
                )
                break

        return events
