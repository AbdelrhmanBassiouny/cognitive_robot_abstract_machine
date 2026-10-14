"""
Coverage for the scaffolding demonstrations share.

The pieces exercised here are the ones a second demonstration would otherwise re-derive:
which world a run acts on, whether it has to spawn its scene, and who owns the ROS
context. None of it needs a controller.
"""

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta

import pytest
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from typing_extensions import Iterator, List

from coraplex.demonstrations import RobotDemonstration, RobotDemonstrationRosSession
from semantic_digital_twin.robots.minimal_robot import MinimalRobot
from semantic_digital_twin.world import World
from cramph.threaded_nodes import FunctionCall

from ..plan_running import robot_extensions
from cramph.context import ContextExtension, StatechartContext
from coraplex.plans.executors import PlanExecutor, SimulatedPlanExecutor
from coraplex.plans.failures import MotionExceededSimulationTimeLimit
from cramph.statechart import Statechart


class PlanDeliberatelyFailed(Exception):
    """
    Raised by a demonstration whose plan is meant to fail.
    """


@dataclass(kw_only=True)
class RecordingDemonstration(RobotDemonstration):
    """
    A demonstration that records which of its hooks ran and in which environment.
    """

    world: World
    """
    World handed to this demonstration instead of one it builds itself.
    """

    scene_already_populated: bool = False
    """
    What :meth:`is_scene_populated` reports.
    """

    fail_the_plan: bool = False
    """
    Whether the plan raises :class:`PlanDeliberatelyFailed` instead of recording.
    """

    populate_scene_calls: int = 0
    """
    How often the scene was spawned.
    """

    tear_down_calls: int = 0
    """
    How often the ROS session was released.
    """

    observed_executor: PlanExecutor | None = field(default=None)
    """
    The executor the plan was run with.
    """

    observed_log_level: int | None = field(default=None)
    """
    The level coraplex logged at while the plan ran.
    """

    segmenting_events: bool = False
    """
    Whether the events of the run are being segmented right now.
    """

    observed_segmenting_events: bool | None = field(default=None)
    """
    Whether the events of the run were being segmented while the plan ran.
    """

    def build_simulated_world(self) -> World:
        return self.world

    def is_scene_populated(self, world: World) -> bool:
        return self.scene_already_populated

    def populate_scene(self, world: World) -> None:
        self.populate_scene_calls += 1

    def build_context_extensions(self, world: World) -> List[ContextExtension]:
        return robot_extensions(world.get_semantic_annotations_by_type(MinimalRobot)[0])

    def build_statechart(self, context: StatechartContext) -> Statechart:
        statechart = Statechart(context=context)
        statechart.add_node(FunctionCall(function=lambda: self.run_plan_body(context)))
        return statechart

    @contextmanager
    def segment_events(self, world: World) -> Iterator[None]:
        self.segmenting_events = True
        yield
        self.segmenting_events = False

    def run_plan_body(self, context: StatechartContext) -> None:
        """
        Record how the plan is executed, or fail if this demonstration is meant to.

        :param context: The context the plan runs in.
        """
        if self.fail_the_plan:
            raise PlanDeliberatelyFailed()
        self.observed_segmenting_events = self.segmenting_events
        self.observed_log_level = logging.getLogger("coraplex").level

    def create_executor(self, world: World) -> PlanExecutor:
        """
        Differs from :meth:`RobotDemonstration.create_executor` in also recording the
        executor in :attr:`observed_executor`.
        """
        self.observed_executor = super().create_executor(world)
        return self.observed_executor

    def tear_down(self) -> None:
        self.tear_down_calls += 1
        super().tear_down()


# %% world acquisition


def test_simulated_run_still_builds_its_own_world(cylinder_bot_world):
    """
    A simulated run builds its own world rather than fetching one from a controller,
    even though it starts a ROS session of its own to visualize that world.
    """
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )

    acquired_world = demonstration.acquire_world()

    assert acquired_world is cylinder_bot_world
    assert demonstration.ros_session is not None
    assert demonstration.ros_node is not None

    demonstration.tear_down()


# %% scene population


def test_scene_is_spawned_when_the_world_does_not_have_it(cylinder_bot_world):
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )

    demonstration.run()

    assert demonstration.populate_scene_calls == 1


def test_scene_is_not_spawned_again_into_a_world_that_has_it(cylinder_bot_world):
    """
    A run against a controller receives a world that may already hold this
    demonstration's objects, and must not spawn a second copy of them.
    """
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world,
        used_robot=MinimalRobot,
        scene_already_populated=True,
    )

    demonstration.run()

    assert demonstration.populate_scene_calls == 0


# %% execution environment


def test_plan_runs_in_the_demonstrations_execution_environment(cylinder_bot_world):
    """
    The plan is what the executor and collision avoidance settings exist for, so they
    have to be in force while it runs.
    """
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world,
        used_robot=MinimalRobot,
        executor_type=SimulatedPlanExecutor,
        collision_avoidance=True,
    )

    demonstration.run()

    assert type(demonstration.observed_executor) is SimulatedPlanExecutor
    assert demonstration.observed_executor.collision_avoidance is True


def test_run_returns_the_world_it_acted_on(cylinder_bot_world):
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )

    assert demonstration.run() is cylinder_bot_world


def test_a_simulated_plan_is_given_up_on_at_the_time_limit_of_its_demonstration(
    cylinder_bot_world,
):
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world,
        used_robot=MinimalRobot,
        simulation_time_per_action=timedelta(0),
    )

    with pytest.raises(MotionExceededSimulationTimeLimit) as error:
        demonstration.run()

    assert error.value.time_limit == demonstration.simulation_time_per_action


# %% event segmentation


def test_the_events_of_the_plan_are_segmented_while_it_runs(cylinder_bot_world):
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )

    demonstration.run()

    assert demonstration.observed_segmenting_events is True
    assert demonstration.segmenting_events is False


def test_the_events_of_the_plan_are_not_segmented_when_switched_off(
    cylinder_bot_world,
):
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot, event_segmentation=False
    )

    demonstration.run()

    assert demonstration.observed_segmenting_events is False


# %% debugging


def test_a_demonstration_runs_without_debugging_by_default(cylinder_bot_world):
    """
    Debugging publishes every copy of the world a candidate is tried in, which a run
    only pays for when someone is watching it.
    """
    coraplex_logger = logging.getLogger("coraplex")
    previous_level = coraplex_logger.level
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )

    try:
        demonstration.run()
        assert demonstration.observed_log_level == logging.INFO
    finally:
        coraplex_logger.setLevel(previous_level)


def test_a_demonstration_debugs_its_plan_when_asked_to(cylinder_bot_world):
    coraplex_logger = logging.getLogger("coraplex")
    previous_level = coraplex_logger.level
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot, debug=True
    )

    try:
        demonstration.run()
        assert demonstration.observed_log_level == logging.DEBUG
    finally:
        coraplex_logger.setLevel(previous_level)


# %% tear down


def test_tear_down_runs_when_the_plan_fails(cylinder_bot_world):
    """
    A demonstration that dies mid-plan still has to release what it acquired, or a real
    run leaves its ROS session behind.
    """
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot, fail_the_plan=True
    )

    with pytest.raises(PlanDeliberatelyFailed):
        demonstration.run()

    assert demonstration.tear_down_calls == 1


# %% ros context ownership


def test_session_releases_a_context_it_started():
    """
    A demonstration run on its own owns the ROS context and must give it back, so the
    process it ran in is left as it was found.
    """
    assert not rclpy.ok(), "another test left a ROS context running"
    session = RobotDemonstrationRosSession.start("context_ownership_probe")

    assert session.owns_context

    session.stop()
    assert not rclpy.ok()


def test_session_leaves_a_context_somebody_else_started(rclpy_node):
    """
    Inside a process that already has a ROS context -- a test, or a larger application
    embedding the demonstration -- the session must not shut that context down.
    """
    session = RobotDemonstrationRosSession.start("context_borrowing_probe")

    assert not session.owns_context

    session.stop()
    assert rclpy.ok()


# %% callbacks of the session's node


def test_a_callback_of_another_group_runs_while_one_is_busy(rclpy_node):
    """
    A client announces itself to its controller from a callback group of its own, which
    has to be served while the node is busy choosing what the plan does next.
    """
    session = RobotDemonstrationRosSession.start("busy_callback_probe")
    busy_callback_started = threading.Event()
    other_callback_ran_meanwhile = threading.Event()
    busy_callback_outcomes: List[bool] = []

    def stay_busy_until_the_other_callback_ran() -> None:
        busy_callback_started.set()
        busy_callback_outcomes.append(other_callback_ran_meanwhile.wait(timeout=2.0))

    def run_while_the_other_callback_is_busy() -> None:
        if busy_callback_started.is_set() and not busy_callback_outcomes:
            other_callback_ran_meanwhile.set()

    session.node.create_timer(
        0.01,
        stay_busy_until_the_other_callback_ran,
        callback_group=MutuallyExclusiveCallbackGroup(),
    )
    session.node.create_timer(
        0.01,
        run_while_the_other_callback_is_busy,
        callback_group=MutuallyExclusiveCallbackGroup(),
    )
    busy_callback_started.wait(timeout=5.0)
    other_callback_ran_meanwhile.wait(timeout=5.0)
    session.stop()

    assert busy_callback_outcomes[0]
