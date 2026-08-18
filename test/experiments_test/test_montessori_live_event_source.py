"""
Tests for what a running Montessori sort tells the viewer's timeline.

Events are handed in rather than detected, so no simulation has to run.
"""

from __future__ import annotations

import threading
from datetime import datetime

import pytest
from cramera.live.run_clock import RunClock
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from experiments.montessori.live_event_source import MontessoriLiveEventSource

from .dataset.montessori_board import board_with_one_hole, cube_at
from .dataset.wound_clock import WoundClock

DETECTED_AT = datetime(2026, 8, 13, 12, 0, 0)
"""
When every event in these tests was noticed.
"""


@pytest.fixture()
def scene():
    """
    A board with one hole and a cube resting on top of it.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board, hole = board_with_one_hole(world, Point3(0.0, 0.0, 0.05))
        shape = cube_at(world, Point3(0.0, 0.0, 0.08))
    return board, hole, shape


@pytest.fixture()
def run_time():
    return WoundClock()


@pytest.fixture()
def source(run_time):
    return MontessoriLiveEventSource(clock=RunClock(monotonic_seconds=run_time.read))


# %% one event, as the timeline reads it
class TestOneDetectionOnTheWire:
    def test_the_event_is_reported_under_its_own_type(self, source, scene):
        _, _, shape = scene

        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])

        assert source.events()[0].kind == "PickUpEvent"

    def test_the_instant_the_event_was_noticed_survives(self, source, scene):
        _, _, shape = scene

        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])

        assert source.events()[0].detected_at == DETECTED_AT

    def test_the_thing_it_happened_to_is_named(self, source, scene):
        _, _, shape = scene

        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])

        assert source.events()[0].participants == [str(shape.root.name)]

    def test_an_event_relating_two_things_names_both_of_them(self, source, scene):
        _, hole, shape = scene

        source.receive(
            [
                InsertionEvent(
                    tracked_object=shape.root,
                    with_object=hole.root,
                    timestamp=DETECTED_AT,
                )
            ]
        )

        assert source.events()[0].participants == [
            str(shape.root.name),
            str(hole.root.name),
        ]


# %% the record the timeline polls
class TestWhatTheTimelineKeepsSeeing:
    def test_events_from_several_ticks_all_stay_readable(self, source, scene):
        _, _, shape = scene

        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])
        source.receive(
            [InsertionEvent(tracked_object=shape.root, timestamp=DETECTED_AT)]
        )

        assert [event.kind for event in source.events()] == [
            "PickUpEvent",
            "InsertionEvent",
        ]

    def test_a_reader_cannot_change_what_the_source_keeps(self, source, scene):
        """
        The timeline is answered on an HTTP thread while the run keeps detecting; handing
        out the list itself would let one side rewrite the other's.
        """
        _, _, shape = scene
        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])

        source.events().clear()

        assert len(source.events()) == 1

    def test_a_run_that_has_detected_nothing_reports_nothing(self, source):
        assert source.events() == []

    def test_the_title_names_the_run_the_events_came_from(self, source):
        assert source.title() == "Montessori sorting"


class TestReceivingWhileTheTimelinePolls:
    def test_every_event_survives_arriving_while_it_is_being_read(self, source, scene):
        """
        Detections are handed over on the planning thread and read on an HTTP one, so
        the two must not lose each other's work.
        """
        _, _, shape = scene
        batches = 200
        stop_reading = threading.Event()

        def keep_reading():
            while not stop_reading.is_set():
                source.events()

        reader = threading.Thread(target=keep_reading)
        reader.start()
        try:
            for _ in range(batches):
                source.receive(
                    [PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)]
                )
        finally:
            stop_reading.set()
            reader.join()

        assert len(source.events()) == batches


# %% the axis the timeline plots the detections along
class TestWhereInTheRunEachDetectionFell:
    def test_a_detection_is_stamped_with_how_far_the_run_had_got(
        self, source, scene, run_time
    ):
        _, _, shape = scene
        run_time.advance(7.5)

        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])

        assert source.events()[0].seconds_into_run == 7.5

    def test_time_the_run_spent_paused_is_left_out_of_the_stamp(
        self, source, scene, run_time
    ):
        """
        The wall clock keeps going while the run stands still, so a stamp taken from it
        would put the mark further along the timeline than the run ever got.
        """
        _, _, shape = scene
        run_time.advance(4.0)
        source.clock.pause()
        run_time.advance(60.0)
        source.clock.resume()
        run_time.advance(1.0)

        source.receive([PickUpEvent(tracked_object=shape.root, timestamp=DETECTED_AT)])

        assert source.events()[0].seconds_into_run == 5.0

    def test_the_timeline_is_told_where_the_run_has_got_to(self, source, run_time):
        run_time.advance(11.0)

        assert source.clock_reading().elapsed == 11.0

    def test_the_timeline_is_told_that_a_paused_run_is_going_nowhere(self, source):
        source.clock.pause()

        assert source.clock_reading().running is False
