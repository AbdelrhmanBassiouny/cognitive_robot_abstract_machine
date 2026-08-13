"""
Tests for the record a running sort keeps of itself.

The point of the record is that it can be read *while* the demo runs, so every test here
reads it partway through rather than only at the end.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

import pytest
from giskardpy.qp.exceptions import SolverReturnedFailureError
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from experiments.montessori.insertion_diagnosis import InsertionFailureReason
from experiments.montessori.sorting_progress import (
    CompletedAttempt,
    SortingProgress,
    UntrackedShapeError,
)
from experiments.montessori.sorting_results import InsertionOutcome

from .dataset.montessori_board import (
    SHAPE_KEY,
    SHAPE_OBJECT_NAME,
    board_with_one_hole,
    cube_at,
    move_shape_to,
)

ABOVE_THE_BOARD = Point3(0.0, 0.0, 0.08)
"""
Where a shape rests when it has not gone through.
"""

BELOW_THE_BOARD = Point3(0.0, 0.0, -0.1)
"""
Where a shape rests once it has fallen through its hole.
"""

STARTED_AT = datetime(2026, 8, 13, 12, 0, 0)
"""
When every attempt in these tests begins.
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
        shape = cube_at(world, ABOVE_THE_BOARD)
    return world, board, hole, shape


@pytest.fixture()
def progress(scene):
    """
    A progress record that has already begun tracking the scene's shape.
    """
    world, board, _, shape = scene
    record = SortingProgress()
    record.begin_shape(shape, board, world)
    return record


def attempt(shape, number=1, fell_through=None, events=None, raised_exception=None):
    """
    One finished attempt on the scene's shape.

    :param shape: The shape the attempt was made on.
    :param number: The attempt's 1-based index.
    :param fell_through: The ground-truth verdict, or None when the attempt raised.
    :param events: Segmind events detected during the attempt.
    :param raised_exception: The exception the attempt raised, if any.
    """
    return CompletedAttempt(
        shape_key=SHAPE_KEY,
        attempt_number=number,
        started_at=STARTED_AT,
        ended_at=STARTED_AT + timedelta(seconds=30),
        plan=None,
        events=events or [],
        fell_through=fell_through,
        raised_exception=raised_exception,
        gripper_bodies=[],
    )


# %% what a shape looks like before anything is tried
class TestTrackingAShape:
    def test_a_tracked_shape_is_named_after_the_piece_not_after_its_hole(
        self, progress
    ):
        """
        A row naming the shape ``square_hole`` reads as though the piece being picked up
        were the hole it is aimed at; the piece names itself, and the hole is its own
        column.
        """
        [tracked] = progress.shapes

        assert tracked.name == SHAPE_OBJECT_NAME
        assert tracked.shape_key == SHAPE_KEY
        assert tracked.target_hole == SHAPE_KEY

    def test_a_tracked_shape_carries_the_pose_it_is_aimed_at(self, progress, scene):
        """
        The insertion pose is what "where were you trying to insert it" answers with, so
        it is the pose the action itself aims at, not the hole's own origin.
        """
        world, board, _, shape = scene
        [tracked] = progress.shapes

        assert tracked.target_pose.to_position_quaternion_list() == (
            board.insertion_target_for(shape, world).to_position_quaternion_list()
        )

    def test_a_tracked_shape_starts_out_not_inserted(self, progress):
        assert progress.shapes[0].is_inserted is False

    def test_a_tracked_shape_reports_its_category(self, progress):
        assert progress.shapes[0].shape_category == "cube"


# %% recording attempts as they finish
class TestRecordingAttempts:
    def test_a_successful_attempt_is_recorded_as_succeeded(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(attempt(shape, fell_through=True))

        [recorded] = progress.attempts
        assert recorded.succeeded is True
        assert recorded.failure_reason is None

    def test_a_failed_attempt_carries_the_reason_it_failed(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(
            attempt(
                shape,
                fell_through=None,
                raised_exception=SolverReturnedFailureError(solver_status=None),
            )
        )

        [recorded] = progress.attempts
        assert recorded.succeeded is False
        assert recorded.failure_reason == InsertionFailureReason.UNDIAGNOSED
        assert "SolverReturnedFailureError" in recorded.failure_detail

    def test_an_attempt_is_named_by_its_piece_and_number(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(attempt(shape, number=2, fell_through=False))

        assert progress.attempts[0].name == "%s attempt 2" % SHAPE_OBJECT_NAME

    def test_an_attempt_repeats_the_hole_and_pose_it_aimed_at(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(attempt(shape, fell_through=False))

        assert progress.attempts[0].target_hole == SHAPE_KEY
        assert progress.attempts[0].target_pose is not None

    def test_each_attempt_counts_towards_its_shape(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(attempt(shape, number=1, fell_through=False))
        progress.record_attempt(attempt(shape, number=2, fell_through=False))

        assert progress.shapes[0].attempt_count == 2

    def test_the_shapes_reason_is_the_last_attempts(self, progress, scene):
        """
        A shape is described by why it finally failed, not by why an earlier retry did.
        """
        _, _, _, shape = scene
        progress.record_attempt(attempt(shape, number=1, fell_through=False, events=[]))
        progress.record_attempt(
            attempt(
                shape,
                number=2,
                fell_through=False,
                events=[
                    PickUpEvent(tracked_object=shape.root, timestamp=STARTED_AT),
                    InsertionEvent(tracked_object=shape.root, timestamp=STARTED_AT),
                ],
            )
        )

        assert (
            progress.shapes[0].failure_reason == InsertionFailureReason.WEDGED_IN_HOLE
        )

    def test_an_attempt_on_a_shape_that_was_never_begun_is_refused(self, scene):
        """
        Nothing is known about such a shape — not the piece's name, not the hole it was
        aimed at — so recording it would silently invent both.
        """
        _, _, _, shape = scene
        never_begun = SortingProgress()

        with pytest.raises(UntrackedShapeError):
            never_begun.record_attempt(attempt(shape, fell_through=False))


# %% what segmind saw, per attempt
class TestRecordingEvents:
    def test_events_are_recorded_against_their_attempt(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(
            attempt(
                shape,
                number=3,
                fell_through=True,
                events=[PickUpEvent(tracked_object=shape.root, timestamp=STARTED_AT)],
            )
        )

        [recorded] = progress.events
        assert recorded.event_type == "PickUpEvent"
        assert recorded.shape_key == SHAPE_KEY
        assert recorded.attempt_number == 3

    def test_an_event_is_labelled_with_the_piece_it_was_detected_for(
        self, progress, scene
    ):
        _, _, _, shape = scene
        progress.record_attempt(
            attempt(
                shape,
                fell_through=True,
                events=[PickUpEvent(tracked_object=shape.root, timestamp=STARTED_AT)],
            )
        )

        assert progress.events[0].name == "%s PickUpEvent" % SHAPE_OBJECT_NAME

    def test_a_detected_pick_up_shows_on_the_shape(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(
            attempt(
                shape,
                fell_through=False,
                events=[PickUpEvent(tracked_object=shape.root, timestamp=STARTED_AT)],
            )
        )

        assert progress.shapes[0].was_picked_up is True
        assert progress.shapes[0].was_detected_inserted is False

    def test_a_detected_insertion_shows_on_the_shape(self, progress, scene):
        _, _, _, shape = scene
        progress.record_attempt(
            attempt(
                shape,
                fell_through=True,
                events=[
                    InsertionEvent(tracked_object=shape.root, timestamp=STARTED_AT)
                ],
            )
        )

        assert progress.shapes[0].was_detected_inserted is True


# %% the shape's own outcome
class TestFinishingAShape:
    def test_finishing_records_the_outcome(self, progress):
        progress.finish_shape(SHAPE_KEY, InsertionOutcome.FELL_THROUGH)

        assert progress.shapes[0].outcome == InsertionOutcome.FELL_THROUGH

    def test_an_unfinished_shape_has_no_outcome_yet(self, progress):
        assert progress.shapes[0].outcome is None


# %% reading the world
class TestRefreshingFromTheWorld:
    def test_refreshing_sees_a_shape_that_has_fallen_through(self, progress, scene):
        world, board, _, shape = scene
        move_shape_to(world, shape, BELOW_THE_BOARD)

        progress.refresh_world_state(board, world)

        assert progress.shapes[0].is_inserted is True

    def test_refreshing_sees_a_shape_that_came_back_out(self, progress, scene):
        world, board, _, shape = scene
        move_shape_to(world, shape, BELOW_THE_BOARD)
        progress.refresh_world_state(board, world)

        move_shape_to(world, shape, ABOVE_THE_BOARD)
        progress.refresh_world_state(board, world)

        assert progress.shapes[0].is_inserted is False


# %% read while writing
class TestConcurrentReads:
    def test_reading_attempts_while_they_are_recorded_never_tears(
        self, progress, scene
    ):
        """
        The viewer reads this from an HTTP thread while the demo keeps writing to it, so
        a read must always answer with a whole list rather than a half-written one.
        """
        _, _, _, shape = scene
        recorded_counts = []
        stop = threading.Event()

        def keep_reading():
            while not stop.is_set():
                recorded_counts.append(len(list(progress.attempts)))

        reader = threading.Thread(target=keep_reading)
        reader.start()
        for number in range(1, 51):
            progress.record_attempt(attempt(shape, number=number, fell_through=False))
        stop.set()
        reader.join(timeout=30)

        assert progress.shapes[0].attempt_count == 50
        assert max(recorded_counts) <= 50
