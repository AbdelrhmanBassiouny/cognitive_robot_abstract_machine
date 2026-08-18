"""
Unit tests for pure helper functions in
:mod:`experiments.montessori.franka_montessori_demo` that don't need a running
simulation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from coraplex.datastructures.enums import Arms
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramera.live.run_control import RunCommand

from experiments.montessori import franka_montessori_demo
from experiments.montessori.event_monitoring import WatchesNothing
from experiments.montessori.franka_montessori_demo import (
    _open_recording,
    _open_results_database,
    _parse_arguments,
    _partition_events_by_attempt,
)
from experiments.montessori.results_database import (
    DATABASE_URI_ENVIRONMENT_VARIABLE,
    IN_MEMORY_DATABASE_URI,
    ResultsDatabase,
)
from experiments.montessori.results_recording import (
    RecordsIterationsToADatabase,
    RecordsNothing,
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

    def fail(action, montessori, context, monitor, progress, attempt):
        raise failure

    monkeypatch.setattr(franka_montessori_demo, "_insert_shape", fail)
    monkeypatch.setattr(
        franka_montessori_demo, "_build_insert_action", lambda shape, montessori: None
    )

    fell_through, _, raised = franka_montessori_demo._insert_shape_or_none(
        shape=shape,
        montessori=None,
        context=None,
        attempt=1,
        monitor=None,
        progress=SortingProgress(),
    )

    assert fell_through is None
    assert raised is failure


# %% the plan is followed while it performs


class PerformsNothing:
    """
    A plan node that records having been performed instead of moving a robot.
    """

    def __init__(self, plan):
        self.plan = plan
        self.performed = False

    def perform(self):
        """
        Stand in for the motion the real node would execute.
        """
        self.performed = True


class InsertionToPerform:
    """
    An insertion action reduced to the shape whose attempt its plan is followed under.
    """

    def __init__(self, montessori_shape):
        self.montessori_shape = montessori_shape


class ClockThatNeverMoves:
    """
    An execution context whose simulated clock stands still, so the timing diagnostic
    the performed plan logs has something to read.
    """

    @staticmethod
    def simulation_clock() -> float:
        """
        The simulated time, which never advances here.
        """
        return 0.0


def test_the_plan_is_followed_before_it_is_performed(monkeypatch):
    """
    An attempt's actions are only recorded once it is over, so the record has to be
    handed the plan while it can still be asked what the robot is doing.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board, _ = board_with_one_hole(world, Point3(0.0, 0.0, 0.05))
        shape = cube_at(world, Point3(0.0, 0.0, 0.08))
    progress = SortingProgress()
    progress.begin_shape(shape, board, world)
    performing = sequential([ParkArmsAction(Arms.BOTH)]).plan
    followed_before_performing = []

    def hand_back_the_plan(action, context):
        node = PerformsNothing(performing)
        followed_before_performing.append(node)
        return node

    monkeypatch.setattr("coraplex.plans.factories.execute_single", hand_back_the_plan)
    franka_montessori_demo._perform_attempt_plan(
        InsertionToPerform(shape), ClockThatNeverMoves(), progress, 3
    )

    [node] = followed_before_performing
    assert node.performed is True
    assert [performed.attempt_number for performed in progress.actions] == [3]
    assert [performed.action_type for performed in progress.actions] == [
        ParkArmsAction.__name__
    ]


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


# %% trading event detection for a smooth run
def test_watching_for_events_is_on_unless_turned_off():
    assert _parse_arguments([]).event_monitor is True


def test_watching_for_events_can_be_turned_off():
    assert _parse_arguments(["--no-event-monitor"]).event_monitor is False


def test_a_run_that_is_not_watching_builds_no_monitor(monkeypatch):
    """
    A detector tick blocks the thread running the motion for about 99 ms, five times a
    control cycle's own budget, so a run that only wants to be watched must be able to
    skip detection rather than pay for it and stutter.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board_with_one_hole(world, Point3(0.0, 0.0, 0.05))
        shape = cube_at(world, Point3(0.0, 0.0, 0.08))

    def refuse(montessori, shape):
        raise AssertionError("a run that is not watching built a monitor anyway")

    monkeypatch.setattr(franka_montessori_demo, "build_shape_monitor", refuse)
    control = SortingRunControl()
    control.apply(RunCommand.RESTART)

    results = franka_montessori_demo._insert_all_shapes(
        SceneThatRefusesToBeSorted([shape]),
        context=None,
        progress=SortingProgress(),
        control=control,
        watch_events=False,
    )

    assert results == []


def test_a_monitor_that_watches_nothing_reports_nothing():
    watches_nothing = WatchesNothing()
    watches_nothing.start()
    watches_nothing.tick()
    watches_nothing.stop()

    assert watches_nothing.events == []


# %% keeping the results
def test_a_run_records_its_results_unless_told_not_to():
    assert _parse_arguments([]).record is True


def test_recording_can_be_turned_off():
    """
    A run that only wants to watch the sort has no use for a database, and asking for
    none is better than pointing it at one that happens to refuse writes.
    """
    assert _parse_arguments(["--no-record"]).record is False


def test_a_run_told_not_to_record_keeps_nothing(tmp_path):
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))
    arguments = _parse_arguments(["--no-record"])

    assert isinstance(_open_recording(arguments, database), RecordsNothing)


def test_a_run_that_records_opens_the_database_it_was_given(tmp_path):
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))

    recording = _open_recording(_parse_arguments([]), database)

    assert isinstance(recording, RecordsIterationsToADatabase)
    recording.close()


# %% which database a run ends up with
def test_no_database_is_named_on_the_command_line_by_default():
    """
    The run resolves its own database, so it can say where the URI came from.
    """
    assert _parse_arguments([]).database_uri is None


def test_the_environment_names_the_database_without_a_command_line_flag(
    monkeypatch, tmp_path
):
    """
    Setting the variable in a shell profile is how a host points every run at its own
    database, and no run should have to repeat it on the command line.
    """
    uri = "sqlite:///%s" % (tmp_path / "results.db")
    monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, uri)

    assert _open_results_database(_parse_arguments([])).uri == uri


def test_a_database_that_is_not_running_becomes_one_in_memory(monkeypatch):
    monkeypatch.setenv(
        DATABASE_URI_ENVIRONMENT_VARIABLE,
        "postgresql+psycopg://nobody:wrong@127.0.0.1:1/franka_montessori_sorting_results",
    )

    assert _open_results_database(_parse_arguments([])).uri == IN_MEMORY_DATABASE_URI


def test_the_command_line_still_overrides_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv(DATABASE_URI_ENVIRONMENT_VARIABLE, "sqlite:///ignored.db")
    uri = "sqlite:///%s" % (tmp_path / "results.db")

    resolved = _open_results_database(_parse_arguments(["--database-uri", uri]))

    assert resolved.uri == uri
