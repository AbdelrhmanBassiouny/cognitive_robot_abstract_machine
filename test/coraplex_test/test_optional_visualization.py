"""
Visualization is opt-in and shows the world of the executor it is added to while that
executor runs a statechart.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, EntryPoints
from pathlib import Path
from unittest.mock import Mock

import pytest
import rclpy

import coraplex.testing as testing_module
import coraplex.visualization as visualization_module
from coraplex.datastructures.enums import (
    ActionTrialVisualization,
    VisualizationBackend,
    VisualizationOption,
)
from coraplex.exceptions import (
    RvizVisualizationWithoutRosNode,
    UnknownVisualizationOption,
    VisualizationBackendUnavailable,
)
from coraplex.plans.executors import RealRobotPlanExecutor, SimulatedPlanExecutor
from coraplex.visualization import (
    RerunVisualization,
    RvizVisualization,
    WorldVisualization,
)
from cramph.context import StatechartContext
from cramph.executor import StatechartExecutor
from cramph.node import EndStatechart
from cramph.nodes_for_testing import ConstTrueNode
from cramph.statechart import Statechart
from rclpy.node import Node
from semantic_digital_twin.adapters.rerun import RerunMode
from semantic_digital_twin.robots.minimal_robot import MinimalRobot
from semantic_digital_twin.world import World

from ..plan_running import robot_extensions
from .test_demonstrations import RecordingDemonstration


# %% a visualization recording its runs
@dataclass
class VisualizationRecordingItsRuns(WorldVisualization):
    """
    A visualization recording which worlds it was started on and how often it stopped.
    """

    started_worlds: list[World] = field(default_factory=list)
    """
    The world of every start, in order.
    """

    stops: int = 0
    """
    How often a started run was stopped.
    """

    running: bool = False
    """
    Whether a run is started and not yet stopped.
    """

    @property
    def is_rendering(self) -> bool:
        return self.running

    def _start(self, world: World, cleanup: ExitStack) -> None:
        self.started_worlds.append(world)
        self.running = True
        cleanup.callback(self._record_stop)

    def _record_stop(self) -> None:
        """
        Count a stop of the started run.
        """
        self.stops += 1
        self.running = False


def an_ending_statechart(context: StatechartContext) -> Statechart:
    """
    :param context: The context the statechart is built in.
    :return: A statechart that ends once its only step succeeded.
    """
    statechart = Statechart(context=context)
    step = ConstTrueNode(name="step")
    statechart.add_node(step)
    statechart.add_node(EndStatechart.when_true(step))
    return statechart


def an_executor(
    visualization: WorldVisualization, world: World | None = None
) -> StatechartExecutor:
    """
    :param visualization: The visualization added to the executor.
    :param world: The world the executor runs in, a new one unless given.
    :return: An executor showing its world through `visualization`.
    """
    return StatechartExecutor(
        context=StatechartContext(world=World() if world is None else world),
        extensions=[visualization],
    )


@pytest.fixture
def installed_visualization(monkeypatch):
    """
    Expose :class:`VisualizationRecordingItsRuns` through the installed-plugin discovery
    boundary.
    """
    entry = Mock()
    entry.load.return_value = VisualizationRecordingItsRuns
    discover = Mock(return_value=[entry])
    monkeypatch.setattr(visualization_module, "entry_points", discover)
    return discover


# %% one run per executor
def test_a_visualization_shows_the_world_of_its_executor_while_it_runs() -> None:
    visualization = VisualizationRecordingItsRuns()
    world = World()
    executor = an_executor(visualization, world)

    executor.compile(an_ending_statechart(executor.context))
    assert visualization.started_worlds == [world]
    assert visualization.is_rendering

    executor.execute()
    assert visualization.stops == 1
    assert not visualization.is_rendering


def test_a_visualization_is_not_started_before_its_executor_compiles() -> None:
    visualization = VisualizationRecordingItsRuns()

    an_executor(visualization)

    assert visualization.started_worlds == []


def test_a_recompile_does_not_restart_the_visualization() -> None:
    visualization = VisualizationRecordingItsRuns()
    executor = an_executor(visualization)
    statechart = an_ending_statechart(executor.context)
    executor.compile(statechart)

    executor.after_recompile()

    assert len(visualization.started_worlds) == 1
    executor.execute()


def test_one_visualization_shows_each_run_of_sequential_executors() -> None:
    visualization = VisualizationRecordingItsRuns()
    worlds = [World(), World()]

    for world in worlds:
        executor = an_executor(visualization, world)
        executor.compile(an_ending_statechart(executor.context))
        executor.execute()

    assert visualization.started_worlds == worlds
    assert visualization.stops == len(worlds)


def test_a_plan_run_on_the_real_robot_is_shown_once_compiled() -> None:
    visualization = VisualizationRecordingItsRuns()
    world = World()
    executor = RealRobotPlanExecutor(world, extensions=[visualization])
    statechart = Statechart(context=executor.context)
    statechart.add_node(ConstTrueNode(name="step"))

    executor.compile(statechart)

    assert visualization.started_worlds == [world]
    visualization.stop()


def test_starting_twice_keeps_the_running_visualization() -> None:
    visualization = VisualizationRecordingItsRuns()
    world = World()

    visualization.start(world)
    visualization.start(World())

    assert visualization.started_worlds == [world]
    visualization.stop()
    visualization.stop()
    assert visualization.stops == 1


# %% selection from the environment
def test_no_backend_selection_keeps_requested_default(monkeypatch, rclpy_node) -> None:
    """
    Installing Cramera must not change an existing caller's renderer.
    """
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    selected = WorldVisualization.from_environment(
        VisualizationBackend.RVIZ, ros_node=rclpy_node
    )
    assert isinstance(selected, RvizVisualization)


def test_the_none_backend_selects_no_visualization(monkeypatch) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.NONE)
    assert WorldVisualization.from_environment(VisualizationBackend.RVIZ) is None


def test_explicit_backend_selection_uses_installed_provider(
    monkeypatch, installed_visualization
) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA)

    selected = WorldVisualization.from_environment()

    installed_visualization.assert_called_once_with(
        group=VisualizationOption.PROVIDER_GROUP,
        name=VisualizationBackend.CRAMERA.value,
    )
    assert isinstance(selected, VisualizationRecordingItsRuns)


def test_missing_provider_has_actionable_native_error(monkeypatch) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA)
    monkeypatch.setattr(visualization_module, "entry_points", Mock(return_value=[]))
    with pytest.raises(VisualizationBackendUnavailable) as caught:
        WorldVisualization.from_environment()
    assert caught.value.backend is VisualizationBackend.CRAMERA


@pytest.mark.parametrize("loaded", [World, None])
def test_an_entry_point_must_load_a_visualization_class(
    monkeypatch, installed_visualization, loaded
) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA)
    installed_visualization.return_value[0].load.return_value = loaded
    with pytest.raises(VisualizationBackendUnavailable) as caught:
        WorldVisualization.from_environment()
    assert caught.value.backend is VisualizationBackend.CRAMERA


def test_native_entry_point_collection_loads_selected_provider(monkeypatch) -> None:
    """
    The installed metadata collection supports provider lookup on Python 3.12.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA)
    providers = EntryPoints(
        [
            EntryPoint(
                name=VisualizationBackend.CRAMERA.value,
                value="test:VisualizationRecordingItsRuns",
                group=VisualizationOption.PROVIDER_GROUP,
            )
        ]
    )
    monkeypatch.setattr(
        visualization_module, "entry_points", Mock(return_value=providers)
    )
    monkeypatch.setattr(
        EntryPoint, "load", Mock(return_value=VisualizationRecordingItsRuns)
    )
    selected = WorldVisualization.from_environment()
    assert isinstance(selected, VisualizationRecordingItsRuns)


def test_unknown_environment_selection_is_rejected(monkeypatch) -> None:
    """
    Misspelled backend configuration is not silently ignored.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, "missing-backend")
    with pytest.raises(UnknownVisualizationOption) as caught:
        WorldVisualization.from_environment()
    assert caught.value.variable is VisualizationOption.BACKEND


def test_unknown_rerun_mode_is_reported(monkeypatch) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.RERUN)
    monkeypatch.setenv(VisualizationOption.RERUN_MODE, "missing-mode")
    with pytest.raises(UnknownVisualizationOption) as caught:
        WorldVisualization.from_environment()
    assert caught.value.variable is VisualizationOption.RERUN_MODE


@pytest.mark.parametrize(
    "backend", [VisualizationBackend.NONE, VisualizationBackend.RVIZ]
)
def test_backend_selection_ignores_rerun_settings(
    monkeypatch: pytest.MonkeyPatch, rclpy_node: Node, backend: VisualizationBackend
) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, backend)
    monkeypatch.setenv(VisualizationOption.RERUN_MODE, "missing-mode")
    WorldVisualization.from_environment(ros_node=rclpy_node)


def test_default_rerun_selection_reads_its_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "world.rrd"
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    monkeypatch.setenv(VisualizationOption.RERUN_MODE, RerunMode.SAVE.value)
    monkeypatch.setenv(VisualizationOption.RERUN_TARGET, str(target))
    selected = WorldVisualization.from_environment(VisualizationBackend.RERUN)
    assert isinstance(selected, RerunVisualization)
    assert selected.mode is RerunMode.SAVE
    assert selected.target == str(target)


def test_rviz_selection_receives_the_collision_setting(monkeypatch, rclpy_node) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.RVIZ)
    selected = WorldVisualization.from_environment(
        ros_node=rclpy_node, collision_visualization=True
    )
    assert isinstance(selected, RvizVisualization)
    assert selected.collision_visualization


def test_rviz_selection_publishes_through_the_given_node(
    monkeypatch, rclpy_node
) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.RVIZ)
    selected = WorldVisualization.from_environment(ros_node=rclpy_node)
    assert selected.ros_node is rclpy_node


def test_rviz_selection_needs_a_ros_node(monkeypatch) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.RVIZ)
    with pytest.raises(RvizVisualizationWithoutRosNode):
        WorldVisualization.from_environment()


def test_testing_helper_stays_headless_without_ros(monkeypatch, rclpy_node) -> None:
    """
    Installing an optional renderer does not enable it for headless tests.
    """
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    monkeypatch.setattr(testing_module, "VizMarkerPublisher", None)
    assert testing_module.selected_visualizations(rclpy_node) == []


def test_testing_helper_stays_headless_without_a_ros_node(monkeypatch) -> None:
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    assert testing_module.selected_visualizations(None) == []


def test_testing_helper_defaults_to_rviz_with_ros(monkeypatch, rclpy_node) -> None:
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    [selected] = testing_module.selected_visualizations(rclpy_node)
    assert isinstance(selected, RvizVisualization)


# %% native renderers
def test_rviz_publishes_through_its_node_while_its_executor_runs(
    cylinder_bot_world, rclpy_node
) -> None:
    visualization = RvizVisualization(ros_node=rclpy_node, collision_visualization=True)
    executor = an_executor(visualization, cylinder_bot_world)

    executor.compile(an_ending_statechart(executor.context))
    publisher = visualization.publisher
    assert publisher.node is rclpy_node
    assert publisher._collision_publisher is not None

    executor.execute()
    assert not visualization.is_rendering
    assert rclpy_node.context.ok()
    assert (
        publisher
        not in cylinder_bot_world.get_world_model_manager().model_change_callbacks
    )


def test_rviz_shows_a_world_without_an_executor(cylinder_bot_world, rclpy_node) -> None:
    visualization = RvizVisualization(ros_node=rclpy_node)

    visualization.start(cylinder_bot_world)
    publisher = visualization.publisher
    assert publisher.node is rclpy_node

    visualization.stop()
    assert not visualization.is_rendering


def test_unavailable_ros_is_reported_without_starting(monkeypatch, rclpy_node) -> None:
    """
    An explicit RViz selection requires its optional ROS publisher.
    """
    monkeypatch.setattr(visualization_module, "VizMarkerPublisher", None)
    executor = an_executor(RvizVisualization(ros_node=rclpy_node))
    with pytest.raises(VisualizationBackendUnavailable) as caught:
        executor.compile(an_ending_statechart(executor.context))
    assert caught.value.backend is VisualizationBackend.RVIZ


def test_rerun_save_uses_existing_native_recording(
    cylinder_bot_world, tmp_path
) -> None:
    """
    Recording is delegated to the unchanged native Rerun adapter.
    """
    recording = tmp_path / "world.rrd"
    selected = RerunVisualization(mode=RerunMode.SAVE, target=str(recording))
    selected.start(cylinder_bot_world)
    selected.stop()
    assert recording.stat().st_size > 0
    assert not selected.is_rendering


# %% demonstrations and action trials
def test_one_visualization_shows_every_repetition_of_a_demonstration(
    monkeypatch, cylinder_bot_world, installed_visualization
) -> None:
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA)
    shown: list[VisualizationRecordingItsRuns] = []
    create_executor = RecordingDemonstration.create_executor

    def recording_executor(demonstration, world):
        executor = create_executor(demonstration, world)
        shown.extend(
            extension
            for extension in executor.extensions
            if isinstance(extension, VisualizationRecordingItsRuns)
        )
        return executor

    monkeypatch.setattr(RecordingDemonstration, "create_executor", recording_executor)
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot, repetitions=2
    )

    demonstration.run()

    assert [
        visualization is demonstration.visualization for visualization in shown
    ] == [True] * demonstration.repetitions
    assert (
        demonstration.visualization.started_worlds
        == [cylinder_bot_world] * demonstration.repetitions
    )
    assert demonstration.visualization.stops == demonstration.repetitions
    assert demonstration.ros_session is None
    assert not rclpy.ok()


def test_a_debugging_action_trial_is_shown_apart_from_the_world_it_copies(
    cylinder_bot_world, rclpy_node
) -> None:
    robot = cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0]
    executor = SimulatedPlanExecutor(
        cylinder_bot_world,
        context_extensions=robot_extensions(robot),
        ros_node=rclpy_node,
        debug=True,
    )
    trials = executor.child_chooser.trial

    trial_executor = trials._trial_executor(trials._copy())

    [shown] = [
        extension
        for extension in trial_executor.extensions
        if isinstance(extension, RvizVisualization)
    ]
    assert trial_executor.ros_node is None
    assert shown.ros_node is rclpy_node
    assert shown.frame_prefix == ActionTrialVisualization.FRAME_PREFIX
    assert shown.marker_topic == ActionTrialVisualization.MARKER_TOPIC
    assert shown.marker_alpha == trials.copy_marker_alpha
    trials.discard()
