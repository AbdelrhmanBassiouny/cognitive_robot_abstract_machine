"""
The physical Tracy's left arm picks up every loose Montessori shape that has a matching
hole and places it above that hole, with the real robot as the real robot: the same
action sequence :mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco` builds (see
:func:`~experiments.tracy_experiments.montessori.montessori_actions.build_sorting_actions`), but
from the real ``PickUpAction``/``PlaceAction`` (Giskard-driven, over ROS) instead of
:mod:`~experiments.tracy_experiments.pick_and_place_action`'s MuJoCo-actuator pair.

Wired the way :mod:`coraplex_real_tracy.demo` wires the physical robot: a Giskard
standalone node is launched, the live world is fetched from a running ``WorldFetcher``
service and kept in sync via :class:`~semantic_digital_twin.adapters.ros.
world_synchronizer.WorldSynchronizer`, and the plan runs under
:attr:`~coraplex.datastructures.enums.ExecutionType.REAL`.

Unlike that demo's own boxes, the shape-sorting board and loose shapes are not simple
enough to add as bare bodies: :class:`~experiments.tracy_experiments.montessori.world.
TracyMontessoriWorld` already knows how to build them (mesh, hole cutouts, shape
geometry), so this instead builds one in its own scratch world and merges it onto the
live, fetched world at Tracy's own mount pose -- the same
:meth:`~semantic_digital_twin.world.World.merge_world` machinery
:func:`~experiments.montessori.world.mount_stationary_robot` already uses (in the
opposite role: there a robot is merged into a freshly built scene, here a freshly built
scene is merged onto an already-live robot).

This has not been run against physical hardware; it is structurally wired to the same
pattern as :mod:`coraplex_real_tracy.demo`, and grasp reliability is a known open issue
on the MuJoCo-driven counterpart (see ``TRACY_MONTESSORI_HANDOFF.md``) that is expected
to carry over here.

Run with (``iai_tracy_description`` and the Giskard/world-fetcher ROS stack must be
running)::

    python -m experiments.tracy_experiments.montessori.montessori_demo_real
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")

import rclpy
from rclpy.executors import MultiThreadedExecutor

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms, ExecutionType
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from experiments.montessori.semantics import ShapeSortingBoard
from experiments.tracy_experiments.equipment import table_top_z as read_table_top_z
from experiments.tracy_experiments.montessori.montessori_actions import (
    build_sorting_actions,
)
from experiments.tracy_experiments.montessori.world import TracyMontessoriWorld
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection

logger = logging.getLogger(__name__)

TRACY_MOUNT_X = 0.0
TRACY_MOUNT_Y = 0.0
"""
Where the physical Tracy's own root ("table") is bolted, in the live world's root
frame -- matches :mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco`'s own
mount pose, since both are the same physical robot.
"""

PICK_ARM = Arms.LEFT
"""
Which arm sorts every shape.
"""


def _attach_montessori_scene(
    world: World, mounted_table_top_z: float
) -> ShapeSortingBoard:
    """
    Build the shape-sorting board and loose shapes in their own scratch world, then
    merge that scene onto the live, already-mounted ``world`` at Tracy's own mount
    pose.

    :param world: The live, fetched world to attach the scene to, modified in place.
    :param mounted_table_top_z: Height of the live robot's own table top, read via
        :func:`~experiments.tracy_experiments.equipment.table_top_z`.
    :return: The board merged into ``world``.
    """
    scene = TracyMontessoriWorld(
        shapes_are_movable=True, table_top_z=mounted_table_top_z
    )
    board = scene.board
    with world.modify_world():
        mount = FixedConnection(
            parent=world.root,
            child=scene.world.root,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=TRACY_MOUNT_X, y=TRACY_MOUNT_Y, z=0.0, yaw=0.0
            ),
        )
        world.merge_world(scene.world, mount)
    return board


def main() -> None:
    giskard_process = subprocess.Popen(
        ["ros2", "launch", "giskardpy_ros", "giskardpy_tracy_standalone.launch.py"],
        start_new_session=True,
    )
    time.sleep(8)  # Wait for the launch file to start

    rclpy.init()
    node = rclpy.create_node("tracy_montessori_demo_real")
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    thread.start()

    try:
        # 300s matches giskardpy's own client (giskardpy/middleware/ros2/python_interface.py),
        # which waits this long for the same race: the world-fetcher server is still
        # parsing the URDF and starting up when the client's default 10s budget would
        # otherwise expire.
        world = fetch_world_from_service(node=node, timeout_seconds=300)
        WorldSynchronizer(_world=world, node=node)
        [robot] = world.get_semantic_annotations_by_type(Tracy)

        board = _attach_montessori_scene(world, read_table_top_z(robot))

        context = Context(
            world=world, robot=robot, ros_node=node, evaluate_conditions=False
        )
        actions = [ParkArmsAction(Arms.BOTH)] + build_sorting_actions(
            world,
            board,
            robot,
            PICK_ARM,
            pick_up_action=PickUpAction,
            place_action=PlaceAction,
        )
        plan = sequential(actions, context=context).plan

        logger.info("Performing sorting plan on the real robot.")
        with ExecutionEnvironment(
            execution_type=ExecutionType.REAL, collision_avoidance=False
        ):
            plan.perform()
        logger.info("Sorting plan finished.")
    finally:
        os.killpg(os.getpgid(giskard_process.pid), signal.SIGTERM)
        giskard_process.wait()


if __name__ == "__main__":
    main()
