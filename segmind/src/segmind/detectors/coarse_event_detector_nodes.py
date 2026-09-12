from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import List

from giskardpy.motion_statechart.context import MotionStatechartContext
from semantic_digital_twin.world_description.world_entity import Body

from segmind.datastructures.events import (
    DetectionEvent,
    LossOfSupportEvent,
    PickUpEvent,
    PlacingEvent,
    StopTranslationEvent,
    SupportEvent,
    TranslationEvent,
)
from segmind.detectors.base import AbstractDetector, SegmindContext
from segmind.detectors.rules import interaction_rule


@dataclass
class AbstractInteractionDetector(AbstractDetector):
    """
    Abstract base class for interaction-based detectors.

    Provides shared functionality for monitoring interactions of
    bodies and generating events when detected.
    """

    shift_threshold: timedelta = timedelta(seconds=15)
    """
    The threshold for the time difference between two events to be considered an interaction.
    """


@dataclass
class PlacingDetector(AbstractInteractionDetector):
    """
    Detects that an object was placed on another one.

    A placement is an object coming to a stop and being supported by something soon
    after, correlated by :func:`~segmind.detectors.rules.interaction_rule`.
    """

    def update_context_and_events(
        self,
        context: MotionStatechartContext,
        segmind_context: SegmindContext,
        tracked_objects: List[Body],
    ) -> List[DetectionEvent]:
        """
        Concludes a placing event for every object that stopped moving and came to rest
        on something within :attr:`~AbstractInteractionDetector.shift_threshold`, and
        that was not already placed on that same thing.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objects: List of bodies to analyze for potential placing events.
        :return: List of generated placing events based on observed interactions.
        """
        return interaction_rule(
            event_type=PlacingEvent,
            primary_event_type=StopTranslationEvent,
            secondary_event_type=SupportEvent,
            logged_events=segmind_context.logger.get_events(),
            shift_threshold=self.shift_threshold,
        ).tolist()


@dataclass
class PickUpDetector(AbstractInteractionDetector):
    """
    Detects that an object was picked up off whatever was supporting it.

    A pick-up is an object starting to move and losing its support soon after,
    correlated by :func:`~segmind.detectors.rules.interaction_rule`.
    """

    def update_context_and_events(
        self,
        context: MotionStatechartContext,
        segmind_context: SegmindContext,
        tracked_objects: List[Body],
    ) -> List[DetectionEvent]:
        """
        Concludes a pick-up event for every object that started moving and lost its
        support within :attr:`~AbstractInteractionDetector.shift_threshold`, and that was
        not already picked up off that same support.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objects: List of bodies to analyze for potential pickup events.
        :return: List of generated pickup events based on observed interactions.
        """
        return interaction_rule(
            event_type=PickUpEvent,
            primary_event_type=TranslationEvent,
            secondary_event_type=LossOfSupportEvent,
            logged_events=segmind_context.logger.get_events(),
            shift_threshold=self.shift_threshold,
        ).tolist()
