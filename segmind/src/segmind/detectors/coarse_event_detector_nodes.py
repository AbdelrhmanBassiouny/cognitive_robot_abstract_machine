from abc import ABC
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import List, TypeVar

from giskardpy.motion_statechart.context import MotionStatechartContext
from krrood.entity_query_language.factories import variable, and_, entity, inference, ConditionType, not_, exists
from krrood.entity_query_language.predicate import symbolic_function
from krrood.entity_query_language.query.query import Entity
from segmind.datastructures.events import (
    SupportEvent,
    DetectionEvent,
    PlacingEvent, TranslationEvent, LossOfSupportEvent, PickUpEvent, StopTranslationEvent, ContactEvent,
    ContainmentEvent, InsertionEvent, EventWithOneTrackedObject, EventWithTwoTrackedObjects, )
from segmind.detectors.base import AbstractDetector, SegmindContext
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import Type, Iterable

TDetectionEvent = TypeVar('TDetectionEvent', bound=DetectionEvent)


@symbolic_function
def event_time_difference(first_event: TDetectionEvent, second_event: TDetectionEvent) -> timedelta:
    """
    Computes the absolute time difference between two events.

    :param first_event: The first event with a timestamp.
    :param second_event: The second event with a timestamp.
    :return: The absolute time difference between the two events.
    """
    return abs(first_event.timestamp - second_event.timestamp)


def interaction_event_detected_before(event_type: Type[EventWithTwoTrackedObjects], first_object: Body,
                                      second_object: Body | None,
                                      events_to_consider: Iterable[DetectionEvent]) -> ConditionType:
    """
    Checks if an interaction event of the given type was detected before the interaction between two bodies.

    :param event_type: The type of interaction event to check.
    :param first_object: The first body involved in the interaction.
    :param second_object: The second body involved in the interaction.
    :param events_to_consider: The events to consider for the interaction event detection.
    :return: True if an interaction event of the given type was detected before the interaction, False otherwise.
    """
    similar_event = variable(event_type, events_to_consider)
    return exists(similar_event, and_(similar_event.tracked_object == first_object,
                similar_event.with_object == second_object))


@dataclass
class AbstractInteractionDetector(AbstractDetector, ABC):
    """
    Abstract base class for interaction-based detectors.

    Provides shared functionality for monitoring interactions of
    bodies and generating events when detected.
    """

    shift_threshold: timedelta = timedelta(seconds=15)
    """
    The threshold for the time difference between two events to be considered an interaction.
    """

    def _find_interaction_events(
            self,
            segmind_context: SegmindContext,
            primary_event_type: Type[EventWithOneTrackedObject],
            secondary_event_type: Type[EventWithTwoTrackedObjects],
            event_type: Type[EventWithTwoTrackedObjects],
    ) -> Entity[EventWithTwoTrackedObjects]:
        """
        Scans logged events for correlated pairs of primary and secondary event types
        and emits a detection event for each new, unseen pairing.

        For each secondary event, this method searches for a primary event on the same
        tracked object whose timestamp is within :attr:`shift_threshold`.

        :param segmind_context: The shared context holding the event logger and
            previously seen interaction pairs.
        :param primary_event_type: The event type to use as the primary signal
            (e.g. ``StopTranslationEvent`` for placing, ``TranslationEvent`` for pickup).
        :param secondary_event_type: The event type to correlate against the primary
            (e.g. ``SupportEvent`` for placing, ``LossOfSupportEvent`` for pickup).
        :param event_type: The event type to produce for each unique pair.
        :return: List of newly detected interaction events.
        """
        events = segmind_context.logger.get_events()
        primary_event = variable(primary_event_type, events)
        secondary_event = variable(secondary_event_type, events)
        primary_object = primary_event.tracked_object
        secondary_object = secondary_event.with_object
        return entity(inference(
            event_type)(tracked_object=primary_object, with_object=secondary_object)).where(
            secondary_event.tracked_object == primary_event.tracked_object,
            event_time_difference(primary_event,
                                  secondary_event) <= self.shift_threshold,
            not_(interaction_event_detected_before(event_type,
                                                   primary_object,
                                                   secondary_object,
                                                   events))
        ).tolist()


@dataclass
class PlacingDetector(AbstractInteractionDetector):
    """
    Represents a class detection mechanism for identifying and managing new
    placing events from observed system interactions.

    This class is typically used to analyze specific event types, such as stop
    motion and support events, and identify correlations that form the basis
    of new placing events. By ensuring that placing events are uniquely paired,
    the class helps maintain consistency and prevent duplication of events.
    """

    def update_context_and_events(self, context: MotionStatechartContext, segmind_context: SegmindContext,
                                  obj: List[Body]) -> List[DetectionEvent]:
        """
        Updates the system context with new placing event instances based on past
        actions logged in the system. It analyzes and filters specific event types
        to detect new events that can be generated. This function ensures distinct
        events are created by maintaining exclusivity through a pairing mechanism.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param obj: List of bodies to analyze for potential placing events.
        :return: List of generated placing events based on observed interactions.
        """
        return self._find_interaction_events(
            segmind_context,
            primary_event_type=StopTranslationEvent,
            secondary_event_type=SupportEvent,
            event_type=PlacingEvent,
        )


@dataclass
class PickUpDetector(AbstractInteractionDetector):
    """
    Detects and processes interactions suggesting an object has been picked up.

    The PickUpDetector class determines if a "pickup" event has occurred by analyzing
    contextual events such as TranslationEvent and LossOfSupportEvent. It ensures
    that such events are detected and processed by checking their timestamps and
    associating them with corresponding objects. The resulting detected events are
    then returned. This class interfaces with a logger to gather the needed event
    data and uses a context to manage event pairs and thresholds.
    """

    def update_context_and_events(self, context: MotionStatechartContext, segmind_context: SegmindContext,
                                  obj: List[Body]) -> List[DetectionEvent]:
        """
        Updates the context and generates a list of events based on translation events and loss
        of support events. The method identifies pairs of related events that are close in
        timestamp, determines if they are exclusive, and creates a new event when conditions
        are met.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param obj: List of bodies to analyze for potential pickup events.
        :return: List of generated pickup events based on observed interactions.
        """
        return self._find_interaction_events(
            segmind_context,
            primary_event_type=TranslationEvent,
            secondary_event_type=LossOfSupportEvent,
            event_type=PickUpEvent,
        )

    @dataclass(eq=False, repr=False)
    class InsertionDetector(AbstractInteractionDetector):
        """
        Detects insertion events based on object interaction context.

        The InsertionDetector class is used to analyze the interaction between tracked
        objects and identify insertion events. It tracks specific events such as
        contacts and containment, and generates an InsertionEvent when specific
        conditions are met. The class leverages a context that holds relevant
        event logs and tracked objects.
        """

        def update_context_and_events(self, context: MotionStatechartContext, segmind_context: SegmindContext,
                                      tracked_objs: List[Body]) -> List[DetectionEvent]:
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
            contact_events = [i for i in segmind_context.logger.get_events() if isinstance(i, ContactEvent)]
            contact_events_with_holes = [i for i in contact_events if i.with_object in segmind_context.holes]
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
                        )
                    )
                    break

            return events
