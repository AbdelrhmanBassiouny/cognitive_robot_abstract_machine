"""
Unit tests for pure helper functions in
:mod:`experiments.montessori.franka_montessori_demo` that don't need a running
simulation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from cramera.live.run_control import RunCommand

from experiments.montessori import franka_montessori_demo
from experiments.montessori.franka_montessori_demo import (
    _parse_arguments,
    _partition_events_by_attempt,
)
from experiments.montessori.run_control import SortingRunControl
from experiments.montessori.sorting_progress import SortingProgress
from semantic_digital_twin.exceptions import PointOccupiedError
from segmind.datastructures.events import PickUpEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from .dataset.montessori_board import board_with_one_hole, cube_at

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


# %% attaching the viewer


def test_the_viewer_is_off_unless_asked_for():
    """
    Attaching the viewer opens a port and patches the CRAM stack, so a plain run must
    not do it.
    """
    assert _parse_arguments([]).cramera is False


def test_the_viewer_can_be_asked_for():
    assert _parse_arguments(["--cramera"]).cramera is True


# %% flags the launcher turns on by default


def test_the_mujoco_window_can_be_turned_back_off():
    """
    ``run_montessori_demo.sh`` opens it by default, so there has to be a way to say no
    without giving up the launcher.
    """
    assert _parse_arguments(["--viewer", "--no-viewer"]).viewer is False


def test_the_second_layout_can_be_turned_back_off():
    assert _parse_arguments(["--world2", "--no-world2"]).world2 is False


def test_neither_is_on_for_a_plain_module_run():
    """
    The headless batch runners invoke this module directly, so its own defaults stay as
    they were; only the launcher chooses differently.
    """
    arguments = _parse_arguments([])

    assert arguments.viewer is False
    assert arguments.world2 is False


# %% a failed attempt keeps its failure


def test_a_retryable_failure_is_returned_rather_than_only_logged(monkeypatch):
    """
    The exceptions the demo retries past are the only record of what went wrong for the
    ones that leave no reason on any plan node, so the caller has to be handed the
    exception itself, not just a None verdict.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board_with_one_hole(world, Point3(0.0, 0.0, 0.05))
        shape = cube_at(world, Point3(0.0, 0.0, 0.08))
    failure = PointOccupiedError(point=None)

    def fail(action, montessori, context):
        raise failure

    monkeypatch.setattr(franka_montessori_demo, "_insert_shape", fail)
    monkeypatch.setattr(
        franka_montessori_demo, "_build_insert_action", lambda shape, montessori: None
    )

    fell_through, _, raised = franka_montessori_demo._insert_shape_or_none(
        shape=shape, montessori=None, context=None, attempt=1
    )

    assert fell_through is None
    assert raised is failure


# %% driving the run from the viewer


class SceneThatRefusesToBeSorted:
    """
    A scene that fails the test if the sort ever looks at what is in it.

    Named for the behaviour it exercises: a run abandoned at its first checkpoint must
    not start a single shape.
    """

    def __init__(self, shapes):
        self.world = self
        self.shapes = shapes

    def get_semantic_annotations_by_type(self, annotation_type):
        """
        The shapes the sort would work through.

        :param annotation_type: The annotation type the sort asks for.
        """
        return self.shapes


def test_a_pending_restart_abandons_the_run_before_any_shape_is_started():
    """
    Restart is honoured at a checkpoint rather than mid-motion, and the first checkpoint
    of a run comes before its first shape.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board_with_one_hole(world, Point3(0.0, 0.0, 0.05))
        shape = cube_at(world, Point3(0.0, 0.0, 0.08))
    control = SortingRunControl()
    control.apply(RunCommand.RESTART)

    results = franka_montessori_demo._insert_all_shapes(
        SceneThatRefusesToBeSorted([shape]),
        context=None,
        progress=SortingProgress(),
        control=control,
    )

    assert results == []


def test_a_run_nobody_is_driving_is_never_held_up():
    """
    Every checkpoint runs on the sorting thread, so a demo started without the viewer
    must pass straight through all of them.
    """
    control = SortingRunControl()

    control.wait_while_paused()

    assert control.restart_is_pending() is False
    assert control.wants_another_iteration() is False
