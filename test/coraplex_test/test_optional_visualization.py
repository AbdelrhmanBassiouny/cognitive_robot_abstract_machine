"""
Visualization is opt-in and preserves native demonstration ownership.
"""

from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, EntryPoints
from unittest.mock import Mock

import pytest
import rclpy

import coraplex.visualization as visualization_module
from coraplex.datastructures.enums import VisualizationBackend
from coraplex.plans.factories import sequential
from coraplex.plans.plan import Plan
from coraplex.plans.plan_callbacks import PlanCallback
from coraplex.plans.plan_node import PlanNode
from coraplex.visualization import (
    PlanVisualization,
    UnknownVisualizationOption,
    VisualizationBackendUnavailable,
    VisualizationOption,
    WorldVisualization,
)
from semantic_digital_twin.robots.minimal_robot import MinimalRobot
from semantic_digital_twin.adapters.rerun import RerunMode
import coraplex.testing as testing_module
from semantic_digital_twin.world import World

from .test_demonstrations import RecordingDemonstration


# %% optional provider
@dataclass
class ObservedScene(PlanVisualization):
    """
    An installed provider recording how a host manages its lifetime.
    """

    started: bool = False
    """
    Whether the host started the scene.
    """

    stopped: bool = False
    """
    Whether the host stopped the scene.
    """

    plans: list[Plan] = field(default_factory=list)
    """
    The plans attached to this scene.
    """

    def start(self):
        """
        Begin serving this scene.
        """
        self.started = True
        return self

    def stop(self) -> None:
        """
        Release this scene.
        """
        self.stopped = True

    def plan_callback(self, plan: Plan) -> PlanCallback:
        """
        Create an observer associated with the requested plan.

        :param plan: The observed plan.
        """
        self.plans.append(plan)
        return PlanCallback(plan=plan)


@pytest.fixture
def installed_scene(monkeypatch):
    """
    Expose a provider through the installed-plugin discovery boundary.
    """
    entry = Mock()
    entry.load.return_value = ObservedScene
    discover = Mock(return_value=[entry])
    monkeypatch.setattr(visualization_module, "entry_points", discover)
    return discover


# %% selection and ownership
def test_no_backend_selection_keeps_requested_default(monkeypatch) -> None:
    """
    Installing Cramera must not change an existing caller's renderer.
    """
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    selected = WorldVisualization.from_environment(World(), VisualizationBackend.RVIZ)
    assert selected.backend is VisualizationBackend.RVIZ


def test_explicit_backend_selection_uses_installed_provider(
    monkeypatch, installed_scene
) -> None:
    """
    An explicitly selected plugin observes the same world and native plan.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA.value)
    world = World()
    selected = WorldVisualization.from_environment(world).start()
    plan = sequential([]).plan
    selected.attach_plan(plan)
    provider = selected.cramera_visualization

    installed_scene.assert_called_once_with(
        group=VisualizationOption.PROVIDER_GROUP,
        name=VisualizationBackend.CRAMERA.value,
    )
    assert provider.world is world
    assert provider.started
    assert provider.plans == [plan]
    assert [callback.plan for callback in plan.node_callbacks] == [plan]
    selected.stop()
    assert provider.stopped
    assert plan.node_callbacks == []
    assert not selected.is_rendering


def test_provider_can_observe_plan_node_returned_by_demo(installed_scene) -> None:
    """
    The native PlanNode demo API and direct Plan API share one observer boundary.
    """
    selected = WorldVisualization(World(), backend=VisualizationBackend.CRAMERA).start()
    root = sequential([])
    selected.attach_plan(root)
    assert selected.cramera_visualization.plans == [root.plan]
    selected.stop()


def test_missing_provider_has_actionable_native_error(monkeypatch) -> None:
    """
    Selecting an uninstalled optional provider fails before starting resources.
    """
    monkeypatch.setattr(visualization_module, "entry_points", Mock(return_value=[]))
    with pytest.raises(VisualizationBackendUnavailable) as caught:
        WorldVisualization(World(), backend=VisualizationBackend.CRAMERA).start()
    assert caught.value.backend is VisualizationBackend.CRAMERA


def test_unknown_environment_selection_is_rejected(monkeypatch) -> None:
    """
    Misspelled backend configuration is not silently ignored.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, "missing-backend")
    with pytest.raises(UnknownVisualizationOption):
        WorldVisualization.from_environment(World())


def test_none_backend_leaves_world_callbacks_unchanged() -> None:
    """
    Headless use creates neither a provider nor a callback.
    """
    world = World()
    callbacks = list(world.state.state_change_callbacks)
    selected = WorldVisualization(world).start()
    selected.attach_plan(sequential([]))
    assert world.state.state_change_callbacks == callbacks
    assert not selected.is_rendering
    selected.stop()


def test_rviz_stops_publishers_without_destroying_borrowed_node(
    cylinder_bot_world, rclpy_node
) -> None:
    """
    The adapter releases its publishers while leaving the host ROS node usable.
    """
    selected = WorldVisualization(
        cylinder_bot_world,
        backend=VisualizationBackend.RVIZ,
        ros_node=rclpy_node,
        collision_visualization=True,
    ).start()
    publisher = selected.rviz_publisher
    assert publisher._collision_publisher is not None
    selected.stop()
    assert rclpy_node.context.ok()
    assert (
        publisher
        not in cylinder_bot_world.get_world_model_manager().model_change_callbacks
    )


def test_demonstration_keeps_all_repetitions_and_explicit_viewer(
    monkeypatch, cylinder_bot_world, installed_scene
) -> None:
    """
    Each repeated native plan is attached and the explicitly selected viewer stays
    inspectable.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA.value)
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot, repetitions=2
    )
    try:
        demonstration.run()
        selected = demonstration.visualization
        assert len(selected.cramera_visualization.plans) == demonstration.repetitions
        assert all(
            isinstance(plan, Plan) for plan in selected.cramera_visualization.plans
        )
        assert selected.is_rendering
    finally:
        demonstration.stop_visualization()
    assert demonstration.ros_session is None
    assert not rclpy.ok()


# %% cleanup and native alternatives
def test_starting_provider_twice_registers_only_once(installed_scene) -> None:
    """
    Starting the same visualization twice retains its single provider.
    """
    selected = WorldVisualization(World(), backend=VisualizationBackend.CRAMERA)
    selected.start()
    provider = selected.cramera_visualization
    selected.start()
    assert selected.cramera_visualization is provider
    assert installed_scene.call_count == 1
    selected.stop()
    selected.stop()


def test_non_visualization_entry_point_is_rejected(installed_scene) -> None:
    """
    An unrelated entry point cannot be used as a visualization provider.
    """
    installed_scene.return_value[0].load.return_value = World
    with pytest.raises(VisualizationBackendUnavailable):
        WorldVisualization(World(), backend=VisualizationBackend.CRAMERA).start()


def test_rviz_releases_a_context_it_owns(cylinder_bot_world) -> None:
    """
    A standalone RViz adapter cleans its own ROS resources on stop.
    """
    assert not rclpy.ok()
    selected = WorldVisualization(
        cylinder_bot_world, backend=VisualizationBackend.RVIZ
    ).start()
    assert rclpy.ok()
    selected.stop()
    assert not rclpy.ok()
    assert selected.ros_node is None


def test_rerun_save_uses_existing_native_recording(
    monkeypatch, cylinder_bot_world, tmp_path
) -> None:
    """
    The optional host delegates recording to the unchanged native Rerun adapter.
    """
    recording = tmp_path / "world.rrd"
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.RERUN.value)
    monkeypatch.setenv(VisualizationOption.RERUN_MODE, RerunMode.SAVE.value)
    monkeypatch.setenv(VisualizationOption.RERUN_TARGET, str(recording))
    selected = WorldVisualization.from_environment(cylinder_bot_world).start()
    selected.stop()
    assert recording.stat().st_size > 0
    assert not selected.is_rendering


def test_unavailable_ros_is_reported_without_starting(monkeypatch) -> None:
    """
    An explicit RViz selection requires its optional ROS publisher.
    """
    monkeypatch.setattr(visualization_module, "VizMarkerPublisher", None)
    with pytest.raises(VisualizationBackendUnavailable) as caught:
        WorldVisualization(World(), backend=VisualizationBackend.RVIZ).start()
    assert VisualizationBackend.RVIZ.value in caught.value.error_message()
    assert caught.value.suggest_correction()


def test_unknown_rerun_mode_is_reported(monkeypatch) -> None:
    """
    Unsupported Rerun output modes produce a named configuration failure.
    """
    monkeypatch.setenv(VisualizationOption.RERUN_MODE, "missing-mode")
    with pytest.raises(UnknownVisualizationOption) as caught:
        WorldVisualization.from_environment(World())
    assert caught.value.variable is VisualizationOption.RERUN_MODE
    assert str(VisualizationOption.RERUN_MODE) in caught.value.error_message()
    assert caught.value.suggest_correction()


def test_testing_helper_stays_headless_without_ros(monkeypatch) -> None:
    """
    Installing an optional renderer does not enable it for headless tests.
    """
    monkeypatch.delenv(VisualizationOption.BACKEND, raising=False)
    monkeypatch.setattr(testing_module, "VizMarkerPublisher", None)
    selected = testing_module.start_visualization(World())
    assert selected.backend is VisualizationBackend.NONE
    assert not selected.is_rendering


def test_failed_visualization_start_releases_demonstration_session(
    monkeypatch, cylinder_bot_world
) -> None:
    """
    An unavailable explicitly selected provider must not leak the demo ROS session.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA.value)
    monkeypatch.setattr(visualization_module, "entry_points", Mock(return_value=[]))
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )
    try:
        with pytest.raises(VisualizationBackendUnavailable):
            demonstration.run()
        assert demonstration.ros_session is None
        assert not rclpy.ok()
    finally:
        demonstration.stop_visualization()


# %% scope ownership and repeated observation
def test_native_entry_point_collection_loads_selected_provider(monkeypatch) -> None:
    """
    The installed metadata collection supports provider lookup on Python 3.12.
    """
    providers = EntryPoints(
        [
            EntryPoint(
                name=VisualizationBackend.CRAMERA.value,
                value="test:ObservedScene",
                group=VisualizationOption.PROVIDER_GROUP,
            )
        ]
    )
    monkeypatch.setattr(
        visualization_module, "entry_points", Mock(return_value=providers)
    )
    monkeypatch.setattr(EntryPoint, "load", Mock(return_value=ObservedScene))
    selected = WorldVisualization(World(), backend=VisualizationBackend.CRAMERA).start()
    assert isinstance(selected.cramera_visualization, ObservedScene)
    selected.stop()


def test_attaching_same_plan_twice_observes_it_once(installed_scene) -> None:
    """
    A plan and its root node identify the same observation subscription.
    """
    selected = WorldVisualization(World(), backend=VisualizationBackend.CRAMERA).start()
    root = sequential([])
    try:
        selected.attach_plan(root)
        selected.attach_plan(root.plan)
        assert selected.cramera_visualization.plans == [root.plan]
        assert [callback.plan for callback in root.plan.node_callbacks] == [root.plan]
    finally:
        selected.stop()


def test_stop_accepts_a_callback_already_removed_by_caller(installed_scene) -> None:
    """
    Removing a subscription externally must not prevent provider cleanup.
    """
    selected = WorldVisualization(World(), backend=VisualizationBackend.CRAMERA).start()
    provider = selected.cramera_visualization
    plan = sequential([]).plan
    selected.attach_plan(plan)
    plan.node_callbacks.clear()
    selected.stop()
    assert provider.stopped
    assert not selected.is_rendering


def test_scope_closes_temporary_visualizations(installed_scene) -> None:
    """
    A temporary viewer remains reachable for cleanup through its active scope.
    """
    with visualization_module.VisualizationSession():
        provider = (
            WorldVisualization(World(), backend=VisualizationBackend.CRAMERA)
            .start()
            .cramera_visualization
        )
        assert not provider.stopped
    assert provider.stopped


@pytest.mark.parametrize("error", [RuntimeError("aborted"), KeyboardInterrupt()])
def test_scope_closes_resources_and_propagates_abort(installed_scene, error) -> None:
    """
    Failed scripts and keyboard interrupts close their viewers before propagating.
    """
    with pytest.raises(type(error)) as caught:
        with visualization_module.VisualizationSession():
            provider = (
                WorldVisualization(World(), backend=VisualizationBackend.CRAMERA)
                .start()
                .cramera_visualization
            )
            raise error
    assert caught.value is error
    assert provider.stopped


def test_nested_scope_restores_outer_owner(installed_scene) -> None:
    """
    Leaving an inner scope keeps outer resources open and restores registration.
    """
    with visualization_module.VisualizationSession():
        outer = (
            WorldVisualization(World(), backend=VisualizationBackend.CRAMERA)
            .start()
            .cramera_visualization
        )
        with visualization_module.VisualizationSession():
            inner = (
                WorldVisualization(World(), backend=VisualizationBackend.CRAMERA)
                .start()
                .cramera_visualization
            )
        restored = (
            WorldVisualization(World(), backend=VisualizationBackend.CRAMERA)
            .start()
            .cramera_visualization
        )
        assert inner.stopped
        assert not outer.stopped
        assert not restored.stopped
    assert outer.stopped
    assert restored.stopped


def test_scope_releases_retained_demonstration_session(
    monkeypatch, cylinder_bot_world, installed_scene
) -> None:
    """
    A completed browser demo releases its retained native ROS thread on scope exit.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA.value)
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )
    with visualization_module.VisualizationSession():
        demonstration.run()
        session = demonstration.ros_session
        provider = demonstration.visualization.cramera_visualization
        assert session.spin_thread.is_alive()
    assert provider.stopped
    assert not session.spin_thread.is_alive()
    assert demonstration.ros_session is None
    assert not rclpy.ok()


def test_scope_finishes_other_cleanup_when_one_callback_fails() -> None:
    """
    An individual failing cleanup must not strand earlier acquired resources.
    """
    earlier = Mock()
    failing = Mock(side_effect=RuntimeError("cleanup failed"))
    with pytest.raises(RuntimeError):
        with visualization_module.VisualizationSession():
            visualization_module.VisualizationSession.register(earlier)
            visualization_module.VisualizationSession.register(failing)
    earlier.assert_called_once_with()
    failing.assert_called_once_with()
    outside = Mock()
    visualization_module.VisualizationSession.register(outside)
    outside.assert_not_called()


def test_explicit_stop_releases_demo_thread_but_keeps_borrowed_ros_context(
    monkeypatch, cylinder_bot_world, installed_scene, rclpy_node
) -> None:
    """
    The demo owns its executor even when it borrows an initialized ROS context.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA.value)
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )
    demonstration.run()
    session = demonstration.ros_session
    try:
        demonstration.stop_visualization()
        assert not session.spin_thread.is_alive()
        assert demonstration.ros_session is None
        assert rclpy_node.context.ok()
    finally:
        if session.spin_thread.is_alive():
            session.stop()


def test_unscoped_browser_demo_releases_owned_ros_session(
    monkeypatch, cylinder_bot_world, installed_scene
) -> None:
    """
    An inspectable browser scene does not retain an unowned executor lifetime.
    """
    monkeypatch.setenv(VisualizationOption.BACKEND, VisualizationBackend.CRAMERA.value)
    demonstration = RecordingDemonstration(
        world=cylinder_bot_world, used_robot=MinimalRobot
    )
    demonstration.acquire_world()
    session = demonstration.ros_session
    provider = demonstration.visualization.cramera_visualization
    try:
        demonstration.tear_down()
        assert not session.spin_thread.is_alive()
        assert demonstration.ros_session is None
        assert not rclpy.ok()
        assert not provider.stopped
    finally:
        demonstration.stop_visualization()
