"""
Tests for what the event logger does with a callback registered for a kind of event:
it is called once for every event of that kind or of a kind derived from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from segmind.datastructures.events import (
    DetectionEvent,
    PickUpEvent,
    SupportEvent,
    TranslationEvent,
)
from segmind.datastructures.object_tracker import ObjectTrackerFactory
from segmind.event_logger import EventCallbacks, EventLogger
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List

# %% what a callback receives


@dataclass
class NotedEvents:
    """
    Keeps every event it is called with, in order.
    """

    events: List[DetectionEvent] = field(default_factory=list)
    """
    The events, as they arrived.
    """

    def note(self, event: DetectionEvent) -> None:
        self.events.append(event)


def a_body() -> Body:
    return Body(name=PrefixedName("event_callbacks_test", "cube"))


def test_a_callback_for_the_base_kind_is_registered_once_per_kind_of_event():
    """
    The registration spreads to every kind of event derived from the one named; a kind
    derived along two paths used to be given the callback twice.
    """
    callbacks = EventCallbacks()
    condition, callback = (lambda event: True), (lambda event: None)

    callbacks[DetectionEvent] = [(condition, callback)]

    for kind in (DetectionEvent, SupportEvent, PickUpEvent, TranslationEvent):
        assert callbacks[kind] == [(condition, callback)]


def test_a_callback_for_the_base_kind_is_called_once_per_event():
    noted = NotedEvents()
    logger = EventLogger()
    logger.add_callback(DetectionEvent, noted.note)
    body = a_body()
    events = [
        SupportEvent(tracked_object=body),
        PickUpEvent(tracked_object=body),
    ]

    for event in events:
        logger.log_event(event, ObjectTrackerFactory())

    assert noted.events == events


def test_a_second_registration_for_a_kind_adds_to_the_first():
    noted_first, noted_second = NotedEvents(), NotedEvents()
    logger = EventLogger()
    logger.add_callback(DetectionEvent, noted_first.note)
    logger.add_callback(SupportEvent, noted_second.note)
    event = SupportEvent(tracked_object=a_body())

    logger.log_event(event, ObjectTrackerFactory())

    assert noted_first.events == [event]
    assert noted_second.events == [event]
