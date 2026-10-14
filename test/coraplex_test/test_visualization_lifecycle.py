"""
A visualization releases whatever it acquired, however its start or stop fails.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import rclpy
from rclpy.node import Node
from typing_extensions import Type

import coraplex.visualization as visualization_module
from coraplex.visualization import RvizVisualization
from semantic_digital_twin.world import World

from .test_optional_visualization import (
    VisualizationRecordingItsRuns,
    an_ending_statechart,
    an_executor,
)


# %% partial acquisition
def test_failed_publisher_creation_releases_owned_ros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        visualization_module, "VizMarkerPublisher", Mock(side_effect=RuntimeError)
    )
    selected = RvizVisualization()
    assert not rclpy.ok()
    with pytest.raises(RuntimeError):
        selected.start(World())
    assert not rclpy.ok()
    assert selected.ros_node is None
    assert not selected.is_rendering


def test_failed_node_creation_releases_owned_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rclpy, "create_node", Mock(side_effect=RuntimeError))
    selected = RvizVisualization()
    assert not rclpy.ok()
    with pytest.raises(RuntimeError):
        selected.start(World())
    assert not rclpy.ok()


@pytest.mark.parametrize("failure_type", [RuntimeError, KeyboardInterrupt])
def test_collision_setup_failure_closes_publisher_and_owned_ros(
    monkeypatch: pytest.MonkeyPatch, failure_type: Type[BaseException]
) -> None:
    failure = failure_type()
    publisher = Mock()
    publisher.with_collision_visualization.side_effect = failure
    monkeypatch.setattr(
        visualization_module, "VizMarkerPublisher", Mock(return_value=publisher)
    )
    selected = RvizVisualization(collision_visualization=True)
    assert not rclpy.ok()
    with pytest.raises(failure_type) as caught:
        selected.start(World())
    assert caught.value is failure
    publisher.stop.assert_called_once_with()
    assert selected.ros_node is None
    assert not selected.is_rendering
    assert not rclpy.ok()


def test_failed_publisher_start_preserves_borrowed_node(
    monkeypatch: pytest.MonkeyPatch,
    rclpy_node: Node,
) -> None:
    monkeypatch.setattr(
        visualization_module, "VizMarkerPublisher", Mock(side_effect=RuntimeError())
    )
    selected = RvizVisualization(ros_node=rclpy_node)
    with pytest.raises(RuntimeError):
        selected.start(World())
    assert selected.ros_node is rclpy_node
    assert rclpy_node.context.ok()
    assert not selected.is_rendering


# %% cleanup failures and reuse
def test_publisher_stop_failure_still_releases_owned_ros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = Mock()
    publisher.stop.side_effect = RuntimeError()
    monkeypatch.setattr(
        visualization_module, "VizMarkerPublisher", Mock(return_value=publisher)
    )
    selected = RvizVisualization()
    selected.start(World())
    with pytest.raises(RuntimeError):
        selected.stop()
    assert selected.ros_node is None
    assert not selected.is_rendering
    assert not rclpy.ok()
    selected.stop()
    publisher.stop.assert_called_once_with()


def test_a_failed_run_still_stops_the_visualization() -> None:
    visualization = VisualizationRecordingItsRuns()
    executor = an_executor(visualization)
    statechart = an_ending_statechart(executor.context)
    executor.compile(statechart)

    with pytest.raises(TimeoutError):
        executor.tick_until_end(timeout=0)

    assert visualization.stops == 1
    assert not visualization.is_rendering
