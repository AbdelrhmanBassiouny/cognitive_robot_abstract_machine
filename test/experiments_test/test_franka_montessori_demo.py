"""
Unit tests for pure helper functions in
:mod:`experiments.montessori.franka_montessori_demo` that don't need a running
simulation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from experiments.montessori.franka_montessori_demo import _partition_events_by_attempt
from segmind.datastructures.events import PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

# %% _partition_events_by_attempt

BASE_TIME = datetime(2026, 1, 1, 12, 0, 0)
ONE_SECOND = timedelta(seconds=1)


def _event_at(offset_seconds: float) -> PickUpEvent:
    return PickUpEvent(
        tracked_object=Body(name=PrefixedName("tracked_body")),
        timestamp=BASE_TIME + timedelta(seconds=offset_seconds),
    )


def test_partition_events_by_attempt_assigns_each_event_to_its_own_time_window():
    attempt_start_times = [
        BASE_TIME,
        BASE_TIME + ONE_SECOND,
        BASE_TIME + 2 * ONE_SECOND,
    ]
    first_attempt_event = _event_at(0.5)
    second_attempt_event = _event_at(1.5)
    third_attempt_event = _event_at(2.5)

    buckets = _partition_events_by_attempt(
        [third_attempt_event, first_attempt_event, second_attempt_event],
        attempt_start_times,
    )

    assert buckets == [
        [first_attempt_event],
        [second_attempt_event],
        [third_attempt_event],
    ]


def test_partition_events_by_attempt_assigns_boundary_timestamp_to_the_later_attempt():
    attempt_start_times = [BASE_TIME, BASE_TIME + ONE_SECOND]
    boundary_event = _event_at(1.0)

    buckets = _partition_events_by_attempt([boundary_event], attempt_start_times)

    assert buckets == [[], [boundary_event]]


def test_partition_events_by_attempt_clamps_events_before_the_first_attempt():
    attempt_start_times = [BASE_TIME, BASE_TIME + ONE_SECOND]
    early_event = _event_at(-0.5)

    buckets = _partition_events_by_attempt([early_event], attempt_start_times)

    assert buckets == [[early_event], []]


def test_partition_events_by_attempt_assigns_events_after_the_last_attempt_to_it():
    attempt_start_times = [BASE_TIME, BASE_TIME + ONE_SECOND]
    late_event = _event_at(100.0)

    buckets = _partition_events_by_attempt([late_event], attempt_start_times)

    assert buckets == [[], [late_event]]


def test_partition_events_by_attempt_with_a_single_attempt_keeps_every_event():
    attempt_start_times = [BASE_TIME]
    events = [_event_at(0.0), _event_at(5.0)]

    buckets = _partition_events_by_attempt(events, attempt_start_times)

    assert buckets == [events]
