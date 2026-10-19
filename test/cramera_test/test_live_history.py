"""
Statechart history publication and recording boundaries.
"""

from __future__ import annotations

import pytest

from typing_extensions import TYPE_CHECKING

from cramph.data_types import LifeCycleValues

from cramera.live.recording import Recording
from cramera.live.visualization import (
    LiveVisualization,
    WorldStateSync,
)

from .dataset.motion_execution import motion_execution
from .test_live_visualization import world

if TYPE_CHECKING:
    from semantic_digital_twin.world import World

    from .dataset.motion_execution import MotionExecution

# %% history publication


class TestMotionHistoryPublication:
    """
    History subscriptions publish chart changes for the plan's lifetime.
    """

    def test_compiling_publishes_the_chart(
        self, motion_execution: MotionExecution
    ) -> None:
        """
        The viewer sees the chart before the first tick.
        """
        motion_execution.compile()

        assert [node.name for node in motion_execution.bridge.chart_state.nodes] == [
            node.name for node in motion_execution.chart.nodes
        ]

    def test_history_changes_publish_the_chart_and_plan(
        self, motion_execution: MotionExecution
    ) -> None:
        """
        A recorded state change refreshes both execution views.
        """
        motion_execution.compile()

        motion_execution.record(LifeCycleValues.RUNNING)

        assert motion_execution.bridge.chart_state.nodes[0].life_cycle == (
            LifeCycleValues.RUNNING.name
        )
        assert motion_execution.bridge.plan_state.nodes[0].status == (
            LifeCycleValues.RUNNING
        )

    def test_compiling_twice_subscribes_to_the_history_once(
        self, motion_execution: MotionExecution
    ) -> None:
        """
        A recompiled chart does not accumulate one subscription per compile.
        """
        motion_execution.compile()
        motion_execution.compile()

        assert motion_execution.chart.state_history.observers == [
            motion_execution.publishing
        ]

    def test_a_reset_clears_the_progress_of_the_plan(
        self, motion_execution: MotionExecution
    ) -> None:
        """
        A reset chart restores every plan entry to its unstarted state.
        """
        motion_execution.compile()
        motion_execution.record(LifeCycleValues.RUNNING)
        motion_execution.record(LifeCycleValues.SUCCEEDED)

        motion_execution.record(LifeCycleValues.NOT_STARTED)

        assert {node.status for node in motion_execution.bridge.plan_state.nodes} == {
            LifeCycleValues.NOT_STARTED
        }

    def test_root_completion_removes_the_history_subscription(
        self, motion_execution: MotionExecution
    ) -> None:
        """
        Completed plans no longer alter the published state.
        """
        motion_execution.compile()
        motion_execution.record(LifeCycleValues.RUNNING)
        assert motion_execution.chart.state_history.observers == [
            motion_execution.publishing
        ]

        motion_execution.publishing.finish()
        motion_execution.publishing.finish()
        published = motion_execution.bridge.chart_state
        motion_execution.record(LifeCycleValues.NOT_STARTED)

        assert motion_execution.chart.state_history.observers == []
        assert motion_execution.bridge.chart_state == published

    def test_visualization_stop_removes_history_subscriptions(
        self, motion_execution: MotionExecution
    ) -> None:
        """
        Stopping a viewer also detaches histories of unfinished plans.
        """
        visualization = LiveVisualization(bridge=motion_execution.bridge)
        visualization.publishing.observe(motion_execution.chart)
        assert motion_execution.chart.state_history.observers == [
            visualization.publishing
        ]

        visualization.stop()
        visualization.stop()

        assert motion_execution.chart.state_history.observers == []


# %% recording alignment


class TestHistoryRecordingAlignment:
    """
    Recorded poses retain the chart state of their own tick.
    """

    def test_next_history_change_does_not_overwrite_previous_world_frame(
        self, world: World, motion_execution: MotionExecution
    ) -> None:
        """
        History is published before the corresponding world frame is appended.
        """
        bridge = motion_execution.bridge
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        world_sync = WorldStateSync(_world=world, bridge=bridge)
        motion_execution.compile()
        motion_execution.record(LifeCycleValues.RUNNING)
        world_sync.on_state_change()

        motion_execution.record(LifeCycleValues.SUCCEEDED)
        world_sync.on_state_change()

        frames = bridge.recording.stop()
        world_sync.stop()
        assert [frame.statechart.nodes[0].life_cycle for frame in frames] == [
            LifeCycleValues.RUNNING.name,
            LifeCycleValues.SUCCEEDED.name,
        ]

    def test_plan_end_flushes_a_chart_change_without_another_world_update(
        self, world: World, motion_execution: MotionExecution
    ) -> None:
        """
        A final chart-only update completes the last captured pose, and the subscription
        ends with the plan.
        """
        bridge = motion_execution.bridge
        bridge.attach(world)
        bridge.recording = Recording()
        bridge.recording.start()
        world_sync = WorldStateSync(_world=world, bridge=bridge)
        motion_execution.compile()
        motion_execution.record(LifeCycleValues.RUNNING)
        world_sync.on_state_change()

        motion_execution.record(LifeCycleValues.SUCCEEDED)
        motion_execution.publishing.finish()

        frames = bridge.recording.stop()
        world_sync.stop()
        assert len(frames) == 1
        assert (
            frames[0].statechart.nodes[0].life_cycle == LifeCycleValues.SUCCEEDED.name
        )
        assert not any(
            observer is motion_execution.publishing
            for observer in motion_execution.chart.state_history.observers
        )
