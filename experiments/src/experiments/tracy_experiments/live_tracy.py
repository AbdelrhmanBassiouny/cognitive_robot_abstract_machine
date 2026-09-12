"""
The physical Tracy as a process reaches it: the world the robot publishes, fetched from
the running ``WorldFetcher`` service and kept in step with every process watching it,
drawn into rviz, and the robot's camera as something a look is taken through.

Every script that runs against the live robot -- the perception node, the pickup demo,
an episode recorded on the robot -- opens the same connection, so all of them see one
world and wire it the same way.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from dataclasses import dataclass

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from typing_extensions import Iterator

from experiments.montessori.perception.node import (
    MontessoriPerceptionNode,
    build_node,
)
from experiments.network_limits import check_large_messages_can_arrive
from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
)
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.world import World

logger = logging.getLogger(__name__)

WORLD_FETCH_TIMEOUT_SECONDS = 300.0
"""
How long a fetch of the published world waits for the service before giving up.
"""

EXECUTOR_THREAD_NAME = "rclpy-executor"
"""
The name of the thread the connection's node is spun on.
"""


@dataclass
class LiveTracy:
    """
    The physical Tracy, connected: its node, the world it publishes, the robot as that
    world holds it, and its camera as a look.
    """

    node: Node
    """
    The node every subscription and publication to the robot is made on.
    """

    world: World
    """
    The world the robot publishes, kept in step with every process watching it.
    """

    robot: Tracy
    """
    The robot as :attr:`world` holds it.
    """

    look: MontessoriPerceptionNode
    """
    The robot's camera, watching the table continuously.
    """

    @classmethod
    @contextlib.contextmanager
    def connected(
        cls,
        node_name: str,
        fetch_timeout: float = WORLD_FETCH_TIMEOUT_SECONDS,
        show_images: bool = False,
    ) -> Iterator[LiveTracy]:
        """
        Connect to the robot for as long as the block runs.

        ROS must already be initialised. The node is spun on a thread of its own, the
        published world is fetched and then kept in step through a
        :class:`~semantic_digital_twin.adapters.ros.world_synchronizer.WorldSynchronizer`,
        so what is stood in it is what every process watching it holds, and drawn into
        rviz, so it can be checked against the real table.

        :param node_name: The name the node registers under.
        :param fetch_timeout: How long to wait for the world service, in seconds.
        :param show_images: Whether the camera opens a window on each of its streams.
        """
        check_large_messages_can_arrive()
        node = rclpy.create_node(node_name)
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        threading.Thread(
            target=executor.spin, daemon=True, name=EXECUTOR_THREAD_NAME
        ).start()
        try:
            world = fetch_world_from_service(node=node, timeout_seconds=fetch_timeout)
            [robot] = world.get_semantic_annotations_by_type(Tracy)
            # The rviz publisher is built before the synchronizer: it registers a
            # state-change callback partway through its own construction, and a sync
            # update landing in that window reaches it before it is ready and takes
            # down the executor thread.
            VizMarkerPublisher(_world=world, node=node)
            WorldSynchronizer(_world=world, node=node)
            yield cls(
                node=node,
                world=world,
                robot=robot,
                look=build_node(node, world, show_images=show_images),
            )
        finally:
            executor.shutdown()
            node.destroy_node()
