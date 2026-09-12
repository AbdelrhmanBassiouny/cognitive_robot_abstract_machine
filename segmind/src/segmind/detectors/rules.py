"""
The rules the composite detectors conclude their events from.

Stating a detector as a rule rather than a scan is what lets an event it produced
explain itself: the conditions it satisfied and the atomic events it consumed are read
back off the rule that ran (see
:meth:`~segmind.datastructures.events.DetectionEvent.participating_events`).
"""

from __future__ import annotations

from datetime import timedelta

from krrood.entity_query_language.factories import (
    and_,
    ConditionType,
    entity,
    exists,
    inference,
    not_,
    variable,
)
from krrood.entity_query_language.predicate import symbolic_function
from krrood.entity_query_language.query.query import Entity
from semantic_digital_twin.semantic_annotations.semantic_annotations import Aperture
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
)
from typing_extensions import Iterable, List, Type

from segmind.datastructures.events import (
    ContactEvent,
    ContainmentEvent,
    DetectionEvent,
    EventWithTrackedObjects,
    InsertionEvent,
)

# %% conditions the rules are stated with


@symbolic_function
def event_time_difference(
    first_event: DetectionEvent, second_event: DetectionEvent
) -> timedelta:
    """
    How far apart in time two events happened.

    :param first_event: One of the two events.
    :param second_event: The other one.
    :return: The absolute difference between their timestamps.
    """
    return abs(first_event.timestamp - second_event.timestamp)


@symbolic_function
def objects_inserted_into(
    containing_object: KinematicStructureEntity,
) -> List[KinematicStructureEntity]:
    """
    What an insertion says the tracked object ended up inside, in the list form the
    event states it in.

    :param containing_object: The entity the tracked object came to be contained in.
    :return: That entity alone, as a list.
    """
    return [containing_object]


def interaction_event_detected_before(
    event_type: Type[EventWithTrackedObjects],
    tracked_object: KinematicStructureEntity,
    with_object: KinematicStructureEntity,
    events_to_consider: Iterable[DetectionEvent],
) -> ConditionType:
    """
    A condition that holds when the same interaction between the same two entities is
    already among the events considered.

    Negated, it is what keeps one interaction from being concluded again on every tick
    for as long as the atomic events evidencing it stay logged.

    :param event_type: The kind of interaction to look for.
    :param tracked_object: The entity the interaction is about.
    :param with_object: The entity that one interacted with.
    :param events_to_consider: The events searched for an earlier such interaction.
    :return: The condition, satisfied when such an interaction was detected before.
    """
    similar_event = variable(event_type, events_to_consider)
    return exists(
        similar_event,
        and_(
            similar_event.tracked_object == tracked_object,
            similar_event.with_object == with_object,
        ),
    )


# %% the rules


def interaction_rule(
    event_type: Type[EventWithTrackedObjects],
    primary_event_type: Type[EventWithTrackedObjects],
    secondary_event_type: Type[EventWithTrackedObjects],
    logged_events: Iterable[DetectionEvent],
    shift_threshold: timedelta,
) -> Entity[EventWithTrackedObjects]:
    """
    An interaction concluded from two events about the same object close in time.

    :param event_type: The interaction to conclude, e.g.
        :class:`~segmind.datastructures.events.PickUpEvent`.
    :param primary_event_type: The event the interaction takes its tracked object from,
        e.g. :class:`~segmind.datastructures.events.TranslationEvent` for a pick-up.
    :param secondary_event_type: The event correlated against the primary one, which the
        interaction takes the entity it is with from, e.g.
        :class:`~segmind.datastructures.events.LossOfSupportEvent` for a pick-up.
    :param logged_events: The events the rule ranges over.
    :param shift_threshold: How far apart the two events may be and still be one
        interaction.
    :return: The interactions found, one per pair of entities.
    """
    primary_event = variable(primary_event_type, logged_events)
    secondary_event = variable(secondary_event_type, logged_events)
    tracked_object = primary_event.tracked_object
    with_object = secondary_event.with_object
    return (
        entity(
            inference(event_type)(
                tracked_object=tracked_object, with_object=with_object
            )
        )
        .where(
            secondary_event.tracked_object == primary_event.tracked_object,
            event_time_difference(primary_event, secondary_event) <= shift_threshold,
            not_(
                interaction_event_detected_before(
                    event_type, tracked_object, with_object, logged_events
                )
            ),
        )
        .distinct(tracked_object, with_object)
    )


def insertion_rule(
    logged_events: Iterable[DetectionEvent],
    holes: Iterable[Aperture],
    shift_threshold: timedelta,
) -> Entity[InsertionEvent]:
    """
    An insertion concluded from an object touching a hole and then being contained in
    something, close in time.

    Shaped like :func:`interaction_rule`, but with the hole bound as well: a hole contact
    names the aperture's own :class:`~semantic_digital_twin.world_description.world_entity.Region`
    root, so the aperture the object went through is the one whose root the contact
    names.

    :param logged_events: The events the rule ranges over.
    :param holes: The apertures registered in the scene.
    :param shift_threshold: How far apart the contact and the containment may be and
        still be one insertion.
    :return: The insertions found, one per pair of entities.
    """
    contact_event = variable(ContactEvent, logged_events)
    containment_event = variable(ContainmentEvent, logged_events)
    hole = variable(Aperture, holes)
    tracked_object = contact_event.tracked_object
    with_object = contact_event.with_object
    return (
        entity(
            inference(InsertionEvent)(
                tracked_object=tracked_object,
                with_object=with_object,
                inserted_into_objects=objects_inserted_into(
                    containment_event.with_object
                ),
                through_hole=hole,
            )
        )
        .where(
            hole.root == with_object,
            containment_event.tracked_object == tracked_object,
            event_time_difference(contact_event, containment_event) <= shift_threshold,
            not_(
                interaction_event_detected_before(
                    InsertionEvent, tracked_object, with_object, logged_events
                )
            ),
        )
        .distinct(tracked_object, with_object)
    )
