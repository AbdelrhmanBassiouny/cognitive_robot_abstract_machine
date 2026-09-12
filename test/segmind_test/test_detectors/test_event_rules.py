"""
What the composite detectors conclude explains itself.

Each event a rule produces names the conditions that rule satisfied, the atomic events
it consumed, and reads back as a sentence.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pytest
from giskardpy.motion_statechart.context import MotionStatechartContext
from krrood.entity_query_language.explanation.explanation import explain_inference
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from typing_extensions import Any, Callable, List, Tuple, Type, TypeVar

from segmind.datastructures.events import (
    ContactEvent,
    ContainmentEvent,
    DetectionEvent,
    EventWithTrackedObjects,
    InsertionEvent,
    LossOfSupportEvent,
    PickUpEvent,
    PlacingEvent,
    StopTranslationEvent,
    SupportEvent,
    TranslationEvent,
)
from segmind.detectors.atomic_event_detectors_nodes import (
    StopTranslationDetector,
    TranslationDetector,
)
from segmind.detectors.base import AbstractDetector, SegmindContext
from segmind.detectors.coarse_event_detector_nodes import (
    PickUpDetector,
    PlacingDetector,
)
from segmind.detectors.rules import interaction_rule
from segmind.detectors.spatial_relation_detector_nodes import (
    ContainmentDetector,
    HoleContactDetector,
    InsertionDetector,
    LossOfHoleContactDetector,
    LossOfSupportDetector,
    SupportDetector,
)
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from segmind.statecharts.segmind_statechart import SegmindStatechart
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix

from .test_segmind_detectors import _build_hole_region_world

TDetectionEvent = TypeVar("TDetectionEvent", bound=DetectionEvent)

# %% running a scenario through the detectors


@dataclass
class SegmentedEpisode:
    """
    A scenario after the detectors have been ticked over it.
    """

    executor: EpisodeSegmenterExecutor
    """
    The executor whose statechart the detectors ticked in.
    """

    detector: AbstractDetector
    """
    The composite detector whose rule the scenario was built to fire.
    """

    @property
    def segmind_context(self) -> SegmindContext:
        """
        The context the detectors logged their events into.
        """
        return self.executor.context.require_extension(SegmindContext)

    @property
    def tick_period(self) -> float:
        """
        Seconds between two detector ticks.
        """
        return self.executor.context.qp_controller_config.control_dt

    def events_of(self, event_type: Type[TDetectionEvent]) -> List[TDetectionEvent]:
        """
        Every logged event of the given type, in the order they were detected.
        """
        return [
            event
            for event in self.segmind_context.logger.get_events()
            if isinstance(event, event_type)
        ]

    def the_event_of(self, event_type: Type[TDetectionEvent]) -> TDetectionEvent:
        """
        The one logged event of the given type.
        """
        [event] = self.events_of(event_type)
        return event

    def events_apart_from(
        self, event_type: Type[DetectionEvent]
    ) -> List[DetectionEvent]:
        """
        Every logged event the given type does not cover.
        """
        return [
            event
            for event in self.segmind_context.logger.get_events()
            if not isinstance(event, event_type)
        ]


@pytest.fixture
def picked_up_milk(_simple_apartment_setup) -> SegmentedEpisode:
    """
    Milk resting on a surface and then lifted clear of it.
    """
    world = _simple_apartment_setup
    executor = EpisodeSegmenterExecutor(context=MotionStatechartContext(world=world))
    milk = world.get_body_by_name("milk.stl")
    box_2 = world.get_body_by_name("box_2")
    detector = PickUpDetector()
    statechart = SegmindStatechart().build_statechart(
        [detector, SupportDetector(), TranslationDetector(), LossOfSupportDetector()]
    )
    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 0.93, reference_frame=world.root
    )
    executor.compile(statechart)
    executor.tick()

    for step in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box_2.global_pose.x,
            y=box_2.global_pose.y,
            z=box_2.global_pose.z + 0.56 + step * 0.1,
            reference_frame=world.root,
        )
        executor.tick()

    yield SegmentedEpisode(executor=executor, detector=detector)

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=world.root
    )


@pytest.fixture
def placed_milk(_simple_apartment_setup) -> SegmentedEpisode:
    """
    Milk lowered onto a surface and coming to rest on it.
    """
    world = _simple_apartment_setup
    executor = EpisodeSegmenterExecutor(context=MotionStatechartContext(world=world))
    milk = world.get_body_by_name("milk.stl")
    box_2 = world.get_body_by_name("box_2")
    detector = PlacingDetector()
    statechart = SegmindStatechart().build_statechart(
        [
            SupportDetector(),
            TranslationDetector(),
            StopTranslationDetector(),
            detector,
        ]
    )
    executor.compile(statechart)
    executor.tick()

    for step in range(5):
        milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            x=box_2.global_pose.x,
            y=box_2.global_pose.y,
            z=box_2.global_pose.z + 0.97 - step * 0.1,
            reference_frame=world.root,
        )
        executor.tick()

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=box_2.global_pose.x,
        y=box_2.global_pose.y,
        z=box_2.global_pose.z + 0.56,
        reference_frame=world.root,
    )
    for _ in range(5):
        executor.tick()

    yield SegmentedEpisode(executor=executor, detector=detector)

    milk.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        -1.7, 0, 1.07, yaw=np.pi, reference_frame=world.root
    )


@pytest.fixture
def inserted_shape() -> SegmentedEpisode:
    """
    A shape dropped through a hole and settling in the pocket below it.
    """
    world, shape, hole, hole_root, extra_candidate, landing_region = (
        _build_hole_region_world()
    )
    executor = EpisodeSegmenterExecutor(context=MotionStatechartContext(world=world))
    detector = InsertionDetector(tracked_object=shape)
    statechart = SegmindStatechart().build_statechart(
        [
            HoleContactDetector(tracked_object=shape),
            LossOfHoleContactDetector(tracked_object=shape),
            ContainmentDetector(
                tracked_object=shape, additional_candidates=[landing_region]
            ),
            detector,
        ]
    )
    executor.compile(statechart)
    executor.tick()

    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, 0, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    shape.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        0, 0, -1, reference_frame=shape.parent_connection.parent
    )
    executor.tick()

    return SegmentedEpisode(executor=executor, detector=detector)


# %% the conditions a rule satisfied


def test_the_pick_up_rule_states_the_conditions_it_satisfied(picked_up_milk):
    """
    The negated condition -- that no such pick-up was detected before -- is not among
    them: what held is its negation, and a logical operator names no condition of its
    own. It is still stated in the rule's verbalization.
    """
    explanation = explain_inference(picked_up_milk.the_event_of(PickUpEvent))
    assert explanation.get_satisfied_conditions_as_string() == (
        "(LossOfSupportEvent.tracked_object == TranslationEvent.tracked_object)"
        "\nAND (event_time_difference <= Literal(timedelta, ...))"
    )


def test_the_placing_rule_states_the_conditions_it_satisfied(placed_milk):
    explanation = explain_inference(placed_milk.the_event_of(PlacingEvent))
    assert explanation.get_satisfied_conditions_as_string() == (
        "(SupportEvent.tracked_object == StopTranslationEvent.tracked_object)"
        "\nAND (event_time_difference <= Literal(timedelta, ...))"
    )


def test_the_insertion_rule_states_the_conditions_it_satisfied(inserted_shape):
    explanation = explain_inference(inserted_shape.the_event_of(InsertionEvent))
    assert explanation.get_satisfied_conditions_as_string() == (
        "(Aperture.root == ContactEvent.with_object)"
        "\nAND (ContainmentEvent.tracked_object == ContactEvent.tracked_object)"
        "\nAND (event_time_difference <= Literal(timedelta, ...))"
    )


# %% the atomic events a rule consumed


def test_the_pick_up_rule_names_the_events_it_consumed(picked_up_milk):
    assert picked_up_milk.the_event_of(PickUpEvent).participating_events() == [
        picked_up_milk.the_event_of(TranslationEvent),
        picked_up_milk.the_event_of(LossOfSupportEvent),
    ]


def test_the_placing_rule_names_the_events_it_consumed(placed_milk):
    assert placed_milk.the_event_of(PlacingEvent).participating_events() == [
        placed_milk.the_event_of(StopTranslationEvent),
        placed_milk.the_event_of(SupportEvent),
    ]


def test_the_insertion_rule_names_the_events_it_consumed(inserted_shape):
    assert inserted_shape.the_event_of(InsertionEvent).participating_events() == [
        inserted_shape.the_event_of(ContactEvent),
        inserted_shape.the_event_of(ContainmentEvent),
    ]


def test_the_insertion_rule_states_the_entity_the_shape_ended_up_inside(inserted_shape):
    """
    Asserted by identity: an argument the rule left unresolved would be a symbolic
    attribute, whose ``==`` answers with a comparison rather than with a truth value.
    """
    insertion = inserted_shape.the_event_of(InsertionEvent)
    [inserted_into] = insertion.inserted_into_objects
    assert inserted_into is inserted_shape.the_event_of(ContainmentEvent).with_object


def test_an_event_no_rule_produced_names_no_events(picked_up_milk):
    """
    An atomic detector builds its events directly, so there is no rule behind them and
    nothing they consumed.
    """
    assert picked_up_milk.the_event_of(TranslationEvent).participating_events() == []


# %% how a rule reads


def test_the_pick_up_rule_verbalizes_as_a_sentence(picked_up_milk):
    explanation = explain_inference(picked_up_milk.the_event_of(PickUpEvent))
    assert verbalize_expression(explanation.query_root) == (
        "If there's a LossOfSupportEvent whose tracked_object is the tracked_object "
        "of a TranslationEvent, an event_time_difference, where the first_event of "
        "the event_time_difference is the TranslationEvent, and the second_event of "
        "the event_time_difference is the LossOfSupportEvent is at most "
        "datetime.timedelta(seconds=15), not (there exists a PickUpEvent such that "
        "its tracked_object is the tracked_object of the first_event of the "
        "event_time_difference, and its with_object is the with_object of the "
        "second_event of the event_time_difference), then there's a PickUpEvent "
        "whose tracked_object is the tracked_object of the first_event of the "
        "event_time_difference, and whose with_object is the with_object of the "
        "second_event of the event_time_difference"
    )


def test_the_placing_rule_verbalizes_as_a_sentence(placed_milk):
    explanation = explain_inference(placed_milk.the_event_of(PlacingEvent))
    assert verbalize_expression(explanation.query_root) == (
        "If there's a SupportEvent whose tracked_object is the tracked_object of a "
        "StopTranslationEvent, an event_time_difference, where the first_event of "
        "the event_time_difference is the StopTranslationEvent, and the "
        "second_event of the event_time_difference is the SupportEvent is at most "
        "datetime.timedelta(seconds=15), not (there exists a PlacingEvent such that "
        "its tracked_object is the tracked_object of the first_event of the "
        "event_time_difference, and its with_object is the with_object of the "
        "second_event of the event_time_difference), then there's a PlacingEvent "
        "whose tracked_object is the tracked_object of the first_event of the "
        "event_time_difference, and whose with_object is the with_object of the "
        "second_event of the event_time_difference"
    )


def test_the_insertion_rule_verbalizes_as_a_sentence(inserted_shape):
    explanation = explain_inference(inserted_shape.the_event_of(InsertionEvent))
    assert verbalize_expression(explanation.query_root) == (
        "If there's an Aperture whose root is the with_object of a ContactEvent, "
        "the tracked_object of a ContainmentEvent is the tracked_object of the "
        "ContactEvent, an event_time_difference, where the first_event of the "
        "event_time_difference is the ContactEvent, and the second_event of the "
        "event_time_difference is the ContainmentEvent is at most "
        "datetime.timedelta(seconds=15), not (there exists an InsertionEvent such "
        "that its tracked_object is the tracked_object of the first_event of the "
        "event_time_difference, and its with_object is the with_object of the "
        "first_event of the event_time_difference), then there's an InsertionEvent "
        "whose tracked_object is the tracked_object of the first_event of the "
        "event_time_difference, whose with_object is the with_object of the "
        "first_event of the event_time_difference, whose inserted_into_objects are "
        "an objects_inserted_into, where the containing_object of the "
        "objects_inserted_into is the with_object of the second_event of the "
        "event_time_difference, and whose through_hole is the Aperture"
    )


# %% what the rule costs


def pair_interactions_by_scanning(
    logged_events: List[DetectionEvent],
    primary_event_type: Type[EventWithTrackedObjects],
    secondary_event_type: Type[EventWithTrackedObjects],
    shift_threshold: timedelta,
) -> List[Tuple[EventWithTrackedObjects, EventWithTrackedObjects]]:
    """
    Pair the same events the rule pairs, by scanning them.

    The baseline the rule is timed against: what finding an interaction costs when it is
    written out as a scan over the logged events rather than stated as a rule.
    """
    primary_events_by_object = defaultdict(list)
    for event in logged_events:
        if isinstance(event, primary_event_type):
            primary_events_by_object[event.tracked_object].append(event)

    pairs = []
    already_paired = set()
    for secondary in logged_events:
        if not isinstance(secondary, secondary_event_type):
            continue
        for primary in primary_events_by_object.get(secondary.tracked_object, []):
            if abs(secondary.timestamp - primary.timestamp) >= shift_threshold:
                continue
            pair_key = (secondary.tracked_object.id, secondary.with_object.id)
            if pair_key in already_paired:
                continue
            already_paired.add(pair_key)
            pairs.append((primary, secondary))
            break
    return pairs


def fastest_run_in_seconds(work: Callable[[], Any], runs: int = 3) -> float:
    """
    The shortest wall-clock time the work took over a warmed-up set of runs.
    """
    work()
    return min(_single_run_in_seconds(work) for _ in range(runs))


def _single_run_in_seconds(work: Callable[[], Any]) -> float:
    start = time.perf_counter()
    work()
    return time.perf_counter() - start


def test_the_pick_up_rule_costs_no_more_than_a_tick_over_scanning(picked_up_milk):
    """
    Stating the pick-up as a rule may cost more than scanning for it, but not more than
    one detector tick more -- otherwise the detector could no longer keep up with the
    statechart it runs in.
    """
    atomic_events = picked_up_milk.events_apart_from(PickUpEvent)
    shift_threshold = picked_up_milk.detector.shift_threshold

    rule_seconds = fastest_run_in_seconds(
        lambda: interaction_rule(
            event_type=PickUpEvent,
            primary_event_type=TranslationEvent,
            secondary_event_type=LossOfSupportEvent,
            logged_events=atomic_events,
            shift_threshold=shift_threshold,
        ).tolist()
    )
    scanning_seconds = fastest_run_in_seconds(
        lambda: pair_interactions_by_scanning(
            atomic_events, TranslationEvent, LossOfSupportEvent, shift_threshold
        )
    )

    assert rule_seconds - scanning_seconds <= picked_up_milk.tick_period
