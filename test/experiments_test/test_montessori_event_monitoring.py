import threading

import numpy as np
from giskardpy.motion_statechart.context import MotionStatechartContext

from krrood.patterns.method_patch import MethodPatch

from experiments.montessori.event_monitoring import (
    build_shape_monitor,
    ControlCycleTicking,
)
from experiments.montessori.semantics import MontessoriShape, ShapeSortingHole
from experiments.montessori.world import MontessoriWorld, TABLE_POSITION, TABLE_SCALE
from segmind.datastructures.events import InsertionEvent, PickUpEvent
from segmind.detectors.atomic_event_detectors_nodes import (
    ContactDetector,
    LossOfContactDetector,
)
from segmind.detectors.base import SegmindContext
from segmind.episode_segmenter import EpisodeSegmenterExecutor
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix


def _shape_and_hole(montessori: MontessoriWorld, key: str):
    shape = next(
        s
        for s in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if s.name.name == f"{key}_shape"
    )
    hole = next(
        h
        for h in montessori.world.get_semantic_annotations_by_type(ShapeSortingHole)
        if h.name.name == key
    )
    return shape, hole


def test_detect_holes_returns_every_shape_sorting_hole_not_the_loose_shapes():
    montessori = MontessoriWorld(shapes_are_movable=True)
    context = MotionStatechartContext(world=montessori.world)
    executor = EpisodeSegmenterExecutor(context=context)
    segmind_context = context.require_extension(SegmindContext)

    executor.detect_holes()

    assert set(segmind_context.holes) == set(
        montessori.world.get_semantic_annotations_by_type(ShapeSortingHole)
    )


def test_shape_falling_through_its_hole_is_detected_as_pick_up_and_insertion():
    """
    Moves the square hole's cube shape off the table, over its hole, and down through it
    to rest, ticking a :class:`MontessoriEventMonitor` by hand throughout (rather than
    starting its background thread) for a fully deterministic sequence of events.
    """
    montessori = MontessoriWorld(shapes_are_movable=True)
    shape, hole = _shape_and_hole(montessori, "square_hole")
    monitor = build_shape_monitor(montessori, shape)

    table_top_z = float(TABLE_POSITION.z) + TABLE_SCALE.z / 2
    resting_low_z = shape.root.collision.combined_mesh.bounds[0][2]
    start_position = shape.root.global_transform.to_position()
    hole_position = hole.root.global_transform.to_position()

    def move_to(x: float, y: float, z: float) -> None:
        # The coordinates are read off global_transform above, so they are the world
        # root's, which the origin setter needs stated to transform them into the
        # connection's parent frame.
        shape.root.parent_connection.origin = (
            HomogeneousTransformationMatrix.from_xyz_rpy(
                x, y, z, reference_frame=montessori.world.root
            )
        )
        monitor.tick()

    # Settle on the table first, so there is a real SupportEvent(table) to be lost.
    for _ in range(5):
        monitor.tick()

    # Lift the shape off the table and carry it to hover above the hole.
    for t in np.linspace(0.0, 1.0, 6):
        move_to(
            float(start_position.x)
            + t * (float(hole_position.x) - float(start_position.x)),
            float(start_position.y)
            + t * (float(hole_position.y) - float(start_position.y)),
            float(start_position.z)
            + t * (float(hole_position.z) + 0.05 - float(start_position.z)),
        )

    # Lower it through the hole down to its resting position on the table.
    for z in np.linspace(
        float(hole_position.z) + 0.05, table_top_z - resting_low_z, 10
    ):
        move_to(float(hole_position.x), float(hole_position.y), float(z))

    # Let StopTranslationDetector's pose window (see MotionDetector.window_size)
    # register the shape as stationary again.
    for _ in range(8):
        monitor.tick()

    pick_up_events = [
        event
        for event in monitor.events
        if isinstance(event, PickUpEvent) and event.tracked_object is shape.root
    ]
    insertion_events = [
        event
        for event in monitor.events
        if isinstance(event, InsertionEvent) and event.tracked_object is shape.root
    ]

    assert len(pick_up_events) == 1
    assert len(insertion_events) == 1
    assert insertion_events[0].through_hole is hole


def test_the_monitor_tracks_the_shape_leaving_the_gripper():
    """
    A shape that slips out of the fingers mid-transport is why an insertion failed, so
    plain contact with the robot has to be watched, not only contact with the hole.
    """
    montessori = MontessoriWorld(shapes_are_movable=True)
    shape, _ = _shape_and_hole(montessori, "square_hole")

    monitor = build_shape_monitor(montessori, shape)

    installed = {type(detector) for detector in monitor.detectors}
    assert {ContactDetector, LossOfContactDetector} <= installed
    assert all(
        detector.tracked_object is shape.root
        for detector in monitor.detectors
        if isinstance(detector, (ContactDetector, LossOfContactDetector))
    )


# %% when the monitor gets to look at the world
class RunsControlCycles:
    """
    Stands in for the class whose control cycle the monitor is ticked from.

    Patching is what installs the ticking, so the test needs a class it can patch
    without building a compiled motion statechart to tick.
    """

    def __init__(self):
        self.cycles = 0

    def tick(self) -> None:
        self.cycles += 1


class TicksItRecords:
    """
    Stands in for the monitor, recording which thread each tick happened on.
    """

    def __init__(self):
        self.tick_threads = []

    def tick(self) -> None:
        self.tick_threads.append(threading.get_ident())


def _ticking_of(monitor, tick_rate_hz=1000.0):
    """
    Ticking driven by :class:`RunsControlCycles` rather than by a real executor.

    :param monitor: The monitor to tick.
    :param tick_rate_hz: Rate to limit the monitor's ticks to.
    """
    ticking = ControlCycleTicking(
        tick_rate_hz=tick_rate_hz,
        patched_method=MethodPatch(owner=RunsControlCycles, name="tick"),
    )
    ticking.drive(monitor)
    return ticking


class TestTheMonitorIsTickedOnTheThreadThatPlans:
    """
    Every detector tick reads the world, and reading the world builds CasADi objects
    (:meth:`Body.global_pose` wraps forward kinematics in a
    ``HomogeneousTransformationMatrix``).

    CasADi releases the GIL and counts its node references without atomics, so a monitor
    ticking on a thread of its own frees nodes the planning thread is still
    dereferencing, and the process dies inside CasADi.
    """

    def test_it_ticks_on_the_thread_that_ran_the_control_cycle(self):
        monitor = TicksItRecords()
        ticking = _ticking_of(monitor)
        try:
            RunsControlCycles().tick()
        finally:
            ticking.stop()

        assert monitor.tick_threads == [threading.get_ident()]

    def test_it_starts_no_thread_of_its_own(self):
        monitor = TicksItRecords()
        threads_before = threading.active_count()

        ticking = _ticking_of(monitor)
        try:
            RunsControlCycles().tick()
        finally:
            ticking.stop()

        assert threading.active_count() == threads_before

    def test_it_still_runs_the_control_cycle_it_ticks_from(self):
        runs_cycles = RunsControlCycles()
        ticking = _ticking_of(TicksItRecords())
        try:
            runs_cycles.tick()
        finally:
            ticking.stop()

        assert runs_cycles.cycles == 1

    def test_it_stops_ticking_once_stopped(self):
        monitor = TicksItRecords()
        _ticking_of(monitor).stop()

        RunsControlCycles().tick()

        assert monitor.tick_threads == []

    def test_a_tick_of_the_monitors_own_executor_does_not_tick_it_again(self):
        """
        The monitor drives a
        :class:`~segmind.episode_segmenter.EpisodeSegmenterExecutor`, which is an
        :class:`~giskardpy.executor.Executor` too, so its own control cycle goes through
        the very method the ticking patches.
        """
        monitor = TicksItRecords()
        ticks_a_nested_cycle = RunsControlCycles()
        monitor.tick = lambda: (
            TicksItRecords.tick(monitor),
            ticks_a_nested_cycle.tick(),
        )
        ticking = _ticking_of(monitor)
        try:
            RunsControlCycles().tick()
        finally:
            ticking.stop()

        assert len(monitor.tick_threads) == 1

    def test_it_ticks_no_faster_than_its_rate(self):
        """
        A control cycle runs at 50 Hz and a detector tick costs far more than 20 ms, so
        ticking on every cycle would spend the run detecting instead of sorting.
        """
        monitor = TicksItRecords()
        ticking = _ticking_of(monitor, tick_rate_hz=0.001)
        try:
            runs_cycles = RunsControlCycles()
            for _ in range(5):
                runs_cycles.tick()
        finally:
            ticking.stop()

        assert len(monitor.tick_threads) == 1


class TicksOnAClockItControls:
    """
    Stands in for a monitor whose tick takes real time, without taking any.
    """

    def __init__(self, clock, tick_duration):
        self.clock = clock
        self.tick_duration = tick_duration
        self.ticks = 0

    def tick(self) -> None:
        self.ticks += 1
        self.clock.advance(self.tick_duration)


class AdvancesOnlyWhenTold:
    """
    A monotonic clock that moves only when a tick says it did.
    """

    def __init__(self):
        self.now = 0.0

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


class TestTicksAreSpacedByTheGapBetweenThem:
    """
    A tick costs about 99 ms and a control cycle runs every 20 ms, so measuring the rate
    from one tick's *start* lets a tick that overran its own interval be followed
    immediately by the next one, and the monitor takes over the thread that is trying to
    plan.
    """

    def test_a_tick_that_overran_its_interval_still_waits_before_the_next(self):
        clock = AdvancesOnlyWhenTold()
        monitor = TicksOnAClockItControls(clock, tick_duration=1.0)
        ticking = ControlCycleTicking(
            tick_rate_hz=10.0,
            patched_method=MethodPatch(owner=RunsControlCycles, name="tick"),
            clock=clock,
        )
        ticking.drive(monitor)
        try:
            runs_cycles = RunsControlCycles()
            runs_cycles.tick()
            runs_cycles.tick()
        finally:
            ticking.stop()

        assert monitor.ticks == 1

    def test_the_next_tick_comes_once_the_gap_has_passed(self):
        clock = AdvancesOnlyWhenTold()
        monitor = TicksOnAClockItControls(clock, tick_duration=1.0)
        ticking = ControlCycleTicking(
            tick_rate_hz=10.0,
            patched_method=MethodPatch(owner=RunsControlCycles, name="tick"),
            clock=clock,
        )
        ticking.drive(monitor)
        try:
            runs_cycles = RunsControlCycles()
            runs_cycles.tick()
            clock.advance(0.1)
            runs_cycles.tick()
        finally:
            ticking.stop()

        assert monitor.ticks == 2


# %% telling a run what was just detected
class RecordsWhatItIsTold:
    """
    Stands in for whatever a run reports its detections to, keeping each handover apart
    so a test can see what a single tick produced.
    """

    def __init__(self):
        self.handovers = []

    def receive(self, events) -> None:
        self.handovers.append(list(events))


class TestTheListenerHearsWhatEachTickDetected:
    """
    A timeline of what is happening now cannot wait for the attempt to finish, so the
    monitor hands its detections over as it makes them.
    """

    def test_everything_detected_is_handed_over_exactly_once_and_in_order(self):
        montessori = MontessoriWorld(shapes_are_movable=True)
        shape, _ = _shape_and_hole(montessori, "square_hole")
        listener = RecordsWhatItIsTold()
        monitor = build_shape_monitor(montessori, shape, listener=listener)

        for _ in range(5):
            monitor.tick()

        handed_over = [event for batch in listener.handovers for event in batch]
        assert handed_over == monitor.events

    def test_the_settling_shape_is_detected_doing_something(self):
        """
        Guards the test above: an empty handover list would satisfy it just as well.
        """
        montessori = MontessoriWorld(shapes_are_movable=True)
        shape, _ = _shape_and_hole(montessori, "square_hole")
        listener = RecordsWhatItIsTold()
        monitor = build_shape_monitor(montessori, shape, listener=listener)

        for _ in range(5):
            monitor.tick()

        assert listener.handovers

    def test_a_tick_that_detected_nothing_hands_nothing_over(self):
        montessori = MontessoriWorld(shapes_are_movable=True)
        shape, _ = _shape_and_hole(montessori, "square_hole")
        listener = RecordsWhatItIsTold()
        monitor = build_shape_monitor(montessori, shape, listener=listener)

        for _ in range(5):
            monitor.tick()

        assert all(listener.handovers)

    def test_a_run_that_reports_to_nobody_still_detects(self):
        montessori = MontessoriWorld(shapes_are_movable=True)
        shape, _ = _shape_and_hole(montessori, "square_hole")
        monitor = build_shape_monitor(montessori, shape)

        for _ in range(5):
            monitor.tick()

        assert monitor.events
