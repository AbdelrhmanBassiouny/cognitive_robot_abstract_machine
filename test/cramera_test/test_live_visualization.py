"""
Tests of the cramera visualization backend: binding the bridge to a world through the
world's own callbacks and publishing the statechart of the executor it is added to.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.world_entity import Body

from coraplex.robot_plans.actions.base import GoalAction
from cramph.context import ContextExtension, StatechartContext
from cramph.data_types import LifeCycleValues
from cramph.executor import StatechartExecutor
from cramph.node import EndStatechart, StatechartNode
from cramph.nodes_for_testing import ConstTrueNode
from cramph.statechart import Statechart
from krrood.ormatic.utils import classproperty

from cramera import paths
from cramera.live import visualization as visualization_module
from cramera.live.bridge import Bridge
from cramera.live.recording import Recording, RecordingState
from cramera.live.visualization import (
    StatechartPublishing,
    LiveVisualization,
    WorldModelSync,
    WorldStateSync,
)

from .dataset.motion_execution import motion_execution
from .test_live_bridge import (
    ActionDescription,
    make_chart,
    nodes_by_kind,
)

# %% fixtures


@pytest.fixture()
def world() -> World:
    """
    A real world with one free-floating body, so state changes can be triggered.
    """
    world = World()
    root = Body(name=PrefixedName("root", prefix="world"))
    milk = Body(name=PrefixedName("milk.stl", prefix="world"))
    with world.modify_world():
        world.add_body(root)
        world.add_connection(
            Connection6DoF.create_with_dofs(parent=root, child=milk, world=world)
        )
    return world


@dataclass
class ServerRecorder:
    """
    Stands in for the HTTP server: records whether it was shut down.
    """

    shut_down: bool = False

    def shutdown(self):
        self.shut_down = True

    def server_close(self) -> None:
        """
        Release the server socket after shutdown.
        """


@pytest.fixture()
def finalized_recordings(monkeypatch) -> list[Recording]:
    """
    Serve to a :class:`ServerRecorder` without ROS markers, and record which captures
    are finalized instead of writing them to disk.

    :return: The finalized captures, in order.
    """
    finalized: list[Recording] = []
    monkeypatch.setattr(
        visualization_module, "serve", lambda passed_bridge, port: ServerRecorder()
    )
    monkeypatch.setattr(
        visualization_module.RosMarkerListener,
        "start_if_available",
        lambda passed_bridge: None,
    )
    monkeypatch.setattr(
        visualization_module,
        "finalize_recording",
        lambda passed_bridge, recording: finalized.append(recording),
    )
    return finalized


def an_ending_statechart(world: World) -> Statechart:
    """
    :param world: The world the statechart runs in.
    :return: A statechart that ends once its only step succeeded.
    """
    statechart = Statechart(context=StatechartContext(world=world))
    statechart.add_node(step := ConstTrueNode(name="step"))
    statechart.add_node(EndStatechart.when_true(step))
    return statechart


# %% world synchronization


class TestWorldSync:
    def test_a_state_change_publishes_a_snapshot(self, world):
        bridge = Bridge()
        bridge.attach(world)
        sync = WorldStateSync(_world=world, bridge=bridge)
        before = bridge.get_state()["sequenceNumber"]

        sync.on_state_change()

        assert bridge.get_state()["sequenceNumber"] == before + 1

    def test_the_sync_registers_with_the_worlds_state_callbacks(self, world):
        sync = WorldStateSync(_world=world, bridge=Bridge())

        assert sync in world.state.state_change_callbacks

    def test_a_state_change_appends_to_an_active_recording(self, world):
        bridge = Bridge()
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        sync = WorldStateSync(_world=world, bridge=bridge)

        sync.on_state_change()

        assert bridge.recording.frame_count() == 1

    def test_a_recorded_tick_carries_the_action_the_plan_is_performing(self, world):
        """
        The tick's action is what names its stretch of the replay timeline, so it has to
        be captured as the tick is buffered — afterwards the plan has moved on.
        """
        bridge = Bridge()
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        performing = "TransportAction"
        bridge.running_step = lambda: performing
        sync = WorldStateSync(_world=world, bridge=bridge)

        sync.on_state_change()
        performing = "ParkArmsAction"
        sync.on_state_change()

        assert [frame.step for frame in bridge.recording.stop()] == [
            "TransportAction",
            "ParkArmsAction",
        ]

    def test_a_recorded_tick_carries_the_statechart_that_was_executing(self, world):
        """
        The statechart the tick found running is what a replay shows at that moment; it
        is gone by the time the recording is bundled, so it is captured per tick.
        """
        bridge = Bridge()
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        bridge.observe_chart(make_chart())
        sync = WorldStateSync(_world=world, bridge=bridge)

        sync.on_state_change()

        assert bridge.recording.stop()[0].statechart == bridge.chart_state

    def test_a_tick_before_any_motion_records_no_statechart(self, world):
        bridge = Bridge()
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        sync = WorldStateSync(_world=world, bridge=bridge)

        sync.on_state_change()

        assert bridge.recording.stop()[0].statechart is None

    def test_a_state_change_without_a_recording_does_not_fail(self, world):
        bridge = Bridge()
        bridge.attach(world)
        sync = WorldStateSync(_world=world, bridge=bridge)

        sync.on_state_change()  # bridge.recording is None — must not raise

    def test_a_model_change_refreshes_the_bundle_signature(self, world):
        bridge = Bridge()
        bridge.attach(world)
        sync = WorldModelSync(_world=world, bridge=bridge)
        before = bridge.bundle_signature()

        with world.modify_world():
            world.add_connection(
                FixedConnection(
                    parent=world.root,
                    child=Body(name=PrefixedName("bench", prefix="laboratory")),
                )
            )
        sync.on_model_change()

        assert bridge.bundle_signature() != before


# %% plan synchronization


@dataclass(eq=False, repr=False, kw_only=True)
class ActionNamingTheChart(GoalAction):
    """
    An action reaching a goal that is always reached, expandable without a robot, as far
    as naming the published chart goes.
    """

    @classproperty
    def context_extensions_required_to_expand(
        cls,
    ) -> tuple[type[ContextExtension], ...]:
        return ()

    def create_goal(self) -> StatechartNode:
        return ConstTrueNode()


class TestStatechartPublishing:
    def test_compiling_publishes_the_plan_tree(self, motion_execution) -> None:
        motion_execution.compile()

        assert nodes_by_kind(motion_execution.bridge)["Sequence"] is not None

    def test_a_started_action_names_the_chart(
        self, world, finalized_recordings
    ) -> None:
        bridge = Bridge()
        live = LiveVisualization(bridge=bridge)
        statechart = Statechart(context=StatechartContext(world=world))
        statechart.add_node(action := ActionNamingTheChart(name="action"))
        executor = StatechartExecutor(context=statechart.context, extensions=[live])

        executor.compile(statechart)

        assert bridge._chart_title == type(action).__name__
        live.stop()

    def test_a_history_change_publishes_the_statechart(self, motion_execution) -> None:
        motion_execution.compile()

        motion_execution.record(LifeCycleValues.RUNNING)

        assert motion_execution.bridge.get_chart()["nodes"] != []

    def test_a_started_node_republishes_the_plan(self, motion_execution) -> None:
        motion_execution.compile()

        motion_execution.record(LifeCycleValues.RUNNING)

        assert (
            nodes_by_kind(motion_execution.bridge)["ConstTrueNode"]["status"]
            == LifeCycleValues.RUNNING.name
        )


# %% the backend


class TestLiveVisualization:
    """
    Viewer sessions bind native world and plan observers for their lifetime.
    """

    def test_start_attaches_and_serves(self, world, monkeypatch):
        bridge = Bridge()
        server = ServerRecorder()
        monkeypatch.setattr(
            visualization_module, "serve", lambda passed_bridge, port: server
        )
        live = LiveVisualization(bridge=bridge)

        assert live.start(world) is live

        assert bridge.world is world
        assert bridge.live_server is server
        assert live.state_sync in world.state.state_change_callbacks
        assert bridge.recording.state is RecordingState.RECORDING

    def test_start_replaces_an_earlier_unsaved_recording(self, world, monkeypatch):
        """
        Re-attaching (e.g. a rerun in the same process) starts a fresh capture — a
        single in-flight slot, the same precedent the ``__live__`` throwaway bundle
        already sets for a second attach.
        """
        bridge = Bridge()
        monkeypatch.setattr(
            visualization_module, "serve", lambda passed_bridge, port: ServerRecorder()
        )
        stale = Recording()
        stale.start()
        stale.stop()
        bridge.recording = stale

        LiveVisualization(bridge=bridge).start(world)

        assert bridge.recording is not stale
        assert bridge.recording.state is RecordingState.RECORDING

    def test_start_registers_an_atexit_safety_net(self, world, monkeypatch, tmp_path):
        """
        A demo has no long-lived process left for the browser to send
        ``/recording/stop`` to — the interpreter exits the moment the script's main body
        returns.

        The registered callback must finalize whatever the bridge is currently recording
        at that point.
        """
        monkeypatch.setenv("CRAMERA_DATA", str(tmp_path))
        bridge = Bridge()
        monkeypatch.setattr(
            visualization_module, "serve", lambda passed_bridge, port: ServerRecorder()
        )
        registered = []
        monkeypatch.setattr(
            visualization_module.atexit,
            "register",
            lambda fn, *args: registered.append((fn, args)),
        )

        LiveVisualization(bridge=bridge).start(world)
        bridge.recording.append(bridge.state)

        [(callback, args)] = registered
        callback(*args)

        assert bridge.recording.scene_name == paths.RECORDING_SCENE_NAME
        assert (
            tmp_path / "scenes" / paths.RECORDING_SCENE_NAME / "scene.json"
        ).is_file()

    def test_the_atexit_safety_net_is_silent_with_nothing_to_finalize(
        self, world, monkeypatch
    ):
        bridge = Bridge()  # never attached — bridge.recording is None
        visualization_module._finalize_recording_at_exit(bridge)  # must not raise

    def test_the_atexit_safety_net_swallows_a_bundling_failure(
        self, world, monkeypatch, capsys
    ):
        """
        The interpreter is already tearing down at this point; a bundling failure must
        not surface as an unhandled exception on every ordinary demo exit.
        """
        bridge = Bridge()
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        bridge.recording.append(bridge.state)
        monkeypatch.setattr(
            visualization_module,
            "finalize_recording",
            lambda *a: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        visualization_module._finalize_recording_at_exit(bridge)  # must not raise

    def test_start_reuses_a_running_server(self, world, monkeypatch):
        bridge = Bridge()
        existing = ServerRecorder()
        bridge.live_server = existing

        def fail(*arguments):
            raise AssertionError("serve() must not be called while a server runs")

        monkeypatch.setattr(visualization_module, "serve", fail)

        LiveVisualization(bridge=bridge).start(world)

        assert bridge.live_server is existing

    def test_stop_detaches_the_callbacks_and_the_server(self, world, monkeypatch):
        bridge = Bridge()
        server = ServerRecorder()
        monkeypatch.setattr(
            visualization_module, "serve", lambda passed_bridge, port: server
        )
        live = LiveVisualization(bridge=bridge).start(world)

        state_sync = live.state_sync
        live.stop()

        assert server.shut_down is True
        assert bridge.live_server is None
        assert state_sync not in world.state.state_change_callbacks

    def test_an_executor_run_is_published_from_compile_to_its_end(
        self, world, finalized_recordings
    ) -> None:
        bridge = Bridge()
        live = LiveVisualization(bridge=bridge)
        statechart = an_ending_statechart(world)
        executor = StatechartExecutor(context=statechart.context, extensions=[live])

        executor.compile(statechart)

        assert bridge.world is world
        assert statechart.state_history.observers == [live.publishing]
        assert nodes_by_kind(bridge)["ConstTrueNode"] is not None

        executor.execute()

        assert statechart.state_history.observers == []
        live.stop()

    def test_the_viewer_keeps_showing_a_run_once_it_ended(
        self, world, finalized_recordings
    ) -> None:
        """
        What the run left stays inspectable in the viewer until the visualization is
        stopped.
        """
        bridge = Bridge()
        live = LiveVisualization(bridge=bridge)
        statechart = an_ending_statechart(world)
        executor = StatechartExecutor(context=statechart.context, extensions=[live])
        executor.compile(statechart)
        server = bridge.live_server

        executor.execute()

        assert live.is_rendering
        assert bridge.live_server is server
        assert finalized_recordings == []
        live.stop()

    def test_stopping_after_a_run_finalizes_its_recording(
        self, world, finalized_recordings
    ) -> None:
        bridge = Bridge()
        live = LiveVisualization(bridge=bridge)
        statechart = an_ending_statechart(world)
        executor = StatechartExecutor(context=statechart.context, extensions=[live])
        executor.compile(statechart)
        recording = bridge.recording
        executor.execute()

        live.stop()

        assert finalized_recordings == [recording]
        assert bridge.live_server is None
        assert not live.is_rendering

    def test_later_runs_in_the_same_world_continue_the_recording(
        self, world, finalized_recordings
    ) -> None:
        bridge = Bridge()
        live = LiveVisualization(bridge=bridge)
        first = an_ending_statechart(world)
        executor = StatechartExecutor(context=first.context, extensions=[live])
        executor.compile(first)
        server = bridge.live_server
        recording = bridge.recording
        executor.execute()
        second = an_ending_statechart(world)
        executor = StatechartExecutor(context=second.context, extensions=[live])

        executor.compile(second)

        assert bridge.live_server is server
        assert bridge.recording is recording
        assert second.state_history.observers == [live.publishing]
        executor.execute()
        live.stop()

    def test_a_run_in_another_world_is_served_by_the_same_server(
        self, world, finalized_recordings
    ) -> None:
        bridge = Bridge()
        live = LiveVisualization(bridge=bridge)
        first = an_ending_statechart(world)
        executor = StatechartExecutor(context=first.context, extensions=[live])
        executor.compile(first)
        server = bridge.live_server
        recording = bridge.recording
        first_state_sync = live.state_sync
        executor.execute()
        other_world = World()
        second = an_ending_statechart(other_world)
        executor = StatechartExecutor(context=second.context, extensions=[live])

        executor.compile(second)

        assert bridge.world is other_world
        assert first_state_sync not in world.state.state_change_callbacks
        assert bridge.live_server is server
        assert bridge.recording is recording
        executor.execute()
        live.stop()
