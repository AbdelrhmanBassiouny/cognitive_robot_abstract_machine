"""
The demos that drive the physical Tracy spin their node on one thread.

rclpy's multi-threaded executor spins hot for as long as a callback it handed out runs,
and every callback of these demos' nodes -- the world's synchronizer, the world fetch,
Giskard's action client -- is in the node's one mutually exclusive group anyway, so a
single-threaded executor serves them alike without starving the process.

A demo's run needs Giskard launched and the robot's world served, so the launch is stood
in for and the world fetch is where the test looks at the node and stops the run.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from types import ModuleType

import pytest
import rclpy
from rclpy.executors import Executor, SingleThreadedExecutor
from rclpy.node import Node
from typing_extensions import Iterator, List, Optional

from experiments.tracy_experiments.montessori import montessori_demo_real
from experiments.tracy_experiments.stacking import stacking_demo_real
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service

TEST_DOMAIN_ID = 106
"""
The ROS domain the demos' nodes are created on here, apart from a robot's own.
"""


class TheRunStoppedAtTheWorldFetch(Exception):
    """
    Raised where a demo fetches the robot's world, to end its run once the node spinning
    it has been seen.
    """


@dataclass
class GiskardLaunchStandIn:
    """
    Stands in for the launched Giskard process a demo waits on and ends.
    """

    command: List[str] = field(default_factory=list)
    """
    What the demo asked to launch.
    """

    pid: int = field(default_factory=os.getpid)
    """
    The identifier the demo reads to end the process group.
    """

    def wait(self) -> int:
        return 0


@dataclass
class WorldFetchThatLooksAtTheNode:
    """
    Stands in for fetching the robot's world: notes which executor spins the node the
    demo fetches with, and stops the run.
    """

    executor: Optional[Executor] = None
    """
    The executor spinning the demo's node when it asked for the world.
    """

    node: Optional[Node] = None
    """
    The node the demo asked with.
    """

    def __call__(self, node: Node, timeout_seconds: float) -> None:
        self.node = node
        self.executor = node.executor
        raise TheRunStoppedAtTheWorldFetch()


@pytest.fixture()
def ros() -> Iterator[None]:
    rclpy.init(domain_id=TEST_DOMAIN_ID)
    yield
    rclpy.try_shutdown()


@pytest.mark.parametrize("demo", [stacking_demo_real, montessori_demo_real])
def test_a_real_demo_spins_its_node_on_one_thread(
    ros: None, monkeypatch: pytest.MonkeyPatch, demo: ModuleType
) -> None:
    fetch = WorldFetchThatLooksAtTheNode()
    monkeypatch.setattr(rclpy, rclpy.init.__name__, lambda *_, **__: None)
    monkeypatch.setattr(
        subprocess,
        subprocess.Popen.__name__,
        lambda command, **_: GiskardLaunchStandIn(command=command),
    )
    monkeypatch.setattr(time, time.sleep.__name__, lambda _: None)
    monkeypatch.setattr(os, os.getpgid.__name__, lambda pid: pid)
    monkeypatch.setattr(os, os.killpg.__name__, lambda group, sent: None)
    monkeypatch.setattr(demo, fetch_world_from_service.__name__, fetch)

    with pytest.raises(TheRunStoppedAtTheWorldFetch):
        demo.main()

    assert type(fetch.executor) is SingleThreadedExecutor
