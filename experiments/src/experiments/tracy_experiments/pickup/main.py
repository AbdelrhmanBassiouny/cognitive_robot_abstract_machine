"""
The physical Tracy's left arm stacks a tower of cubes onto a base cube, with the real
robot as the real robot: the same per-cube pick/place action pairs
:mod:`~experiments.tracy_experiments.stacking.stacking_demo_mujoco` builds, but from the real
``PickUpAction``/``PlaceAction`` (Giskard-driven, over ROS) instead of
:mod:`~experiments.tracy_experiments.pick_and_place_action`'s MuJoCo-actuator pair, and
each cube's own target pose still precomputed up front via
:func:`~experiments.tracy_experiments.stacking.stacking_actions.stack_target_pose`.

Wired the way :mod:`coraplex_real_tracy.demo` wires the physical robot: a Giskard
standalone node is launched, the live world is fetched from a running ``WorldFetcher``
service and kept in sync via :class:`~semantic_digital_twin.adapters.ros.
world_synchronizer.WorldSynchronizer`, and the plan runs under
:attr:`~coraplex.datastructures.enums.ExecutionType.REAL`. Every cube is added to the
live, fetched world as a plain :class:`~semantic_digital_twin.world_description.
world_entity.Body`, the same trick :mod:`coraplex_real_tracy.demo` itself uses for its
own boxes -- these are symbolic anchors Giskard plans around, not a perception result,
so the physical cubes must already be placed at the matching real-world coordinates by
hand before this runs.

This has not been run against physical hardware; it is structurally wired to the same
pattern as :mod:`coraplex_real_tracy.demo`, and grasp reliability is a known open issue
on the MuJoCo-driven counterpart (see ``TRACY_MONTESSORI_HANDOFF.md``) that is expected
to carry over here.

Run with (``iai_tracy_description`` and the Giskard/world-fetcher ROS stack must be
running)::

    python -m experiments.tracy_experiments.stacking.stacking_demo_real
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
from typing_extensions import Dict

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import (
    ApproachDirection,
    Arms,
    ExecutionType,
    VerticalAlignment,
)
from coraplex.datastructures.grasp import GraspDescription
from coraplex.execution_environment import ExecutionEnvironment
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.view_manager import ViewManager
from experiments.tracy_experiments.equipment import table_top_z as read_table_top_z
from experiments.tracy_experiments.stacking.stacking_actions import stack_target_pose
from semantic_digital_twin.adapters.ros.world_fetcher import fetch_world_from_service
from semantic_digital_twin.adapters.ros.world_synchronizer import WorldSynchronizer
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

STACK_ARM = Arms.LEFT
"""
Which arm stacks every cube.
"""

CUBE_SIZE = 0.03
"""
Edge length of every cube, in metres -- matches
:mod:`~experiments.tracy_experiments.stacking.stacking_demo_mujoco`'s own cube.
"""

_STACK_XY = (0.59, 0.4)
"""
Where the base cube stands, and every cube is stacked on top of it -- matches
:mod:`~experiments.tracy_experiments.stacking.stacking_demo_mujoco`'s own coordinates, since both
are the same physical table.
"""

_PICK_XY_LIST = [(0.8, 0.25)]
"""
Where each cube to be stacked must already be placed by hand before this runs --
matches :mod:`~experiments.tracy_experiments.stacking.stacking_demo_mujoco`'s own coordinates.
"""

CUBE_NAME = "cube_base"

def _add_symbolic_cube(world: World, name: str, x: float, y: float, z: float) -> Body:
    """
    Add a cube to the live, fetched world as a fixed, symbolic body at its own expected
    real-world position -- not a perception result, so the physical cube must already be
    there.

    :param world: The live world to add the cube to, modified in place.
    :param name: Name of the cube.
    :param x: X-coordinate of the cube's own centre, in the world root frame.
    :param y: Y-coordinate of the cube's own centre, in the world root frame.
    :param z: Z-coordinate of the cube's own centre, in the world root frame.
    :return: The newly added cube.
    """
    cube = Body(
        name=PrefixedName(name),
        collision=ShapeCollection([Box(scale=Scale(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE))]),
        visual=ShapeCollection(
            [
                Box(
                    scale=Scale(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
                    color=Color(0.6, 0.6, 0.6),
                )
            ]
        ),
    )
    world.add_kinematic_structure_entity(cube)
    world.add_connection(
        FixedConnection.create_with_dofs(
            parent=world.root,
            child=cube,
            world=world,
            parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                x, y, z
            ),
        )
    )
    return cube


def _add_cubes(world: World, mounted_table_top_z: float) -> Dict[str, Body]:
    """
    Add the base cube and every cube to be stacked onto it, at the table height read off
    the live robot.

    :param world: The live world to add the cubes to, modified in place.
    :param mounted_table_top_z: Height of the live robot's own table top, read via
        :func:`~experiments.tracy_experiments.equipment.table_top_z`.
    :return: Every cube (including the base) keyed by name.
    """
    stack_x, stack_y = _STACK_XY
    cube_center_z = mounted_table_top_z + CUBE_SIZE / 2
    with world.modify_world():
        cube_bodies = {
            "cube_base": _add_symbolic_cube(
                world, "cube_base", stack_x, stack_y, cube_center_z
            )
        }
    return cube_bodies


def main() -> None:
    # giskard_process = subprocess.Popen(
    #     ["ros2", "launch", "giskardpy_ros", "giskardpy_tracy_standalone.launch.py"],
    #     start_new_session=True,
    # )
    # time.sleep(8)  # Wait for the launch file to start

    rclpy.init()
    node = rclpy.create_node("tracy_stacking_demo_real")
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    thread.start()

    try:
        world = fetch_world_from_service(node=node, timeout_seconds=300)
        WorldSynchronizer(_world=world, node=node)
        [robot] = world.get_semantic_annotations_by_type(Tracy)

        table_top_z = read_table_top_z(robot)
        cube_bodies = _add_cubes(world, table_top_z)


        context = Context(
            world=world, robot=robot, ros_node=node, evaluate_conditions=False
        )
        grasp_description = GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(STACK_ARM, robot),
        )

        actions = [ParkArmsAction(Arms.BOTH)]

        actions.append(
            PickUpAction(cube_bodies[CUBE_NAME], STACK_ARM, grasp_description)
        )
        plan = sequential(actions, context=context).plan

        logger.info("Performing stacking plan on the real robot.")
        # with ExecutionEnvironment(
        #     execution_type=ExecutionType.SIMULATED, collision_avoidance=True
        # ):
        #     plan.perform()
        logger.info("Stacking plan finished.")
        input()
    finally:
        pass
        #os.killpg(os.getpgid(giskard_process.pid), signal.SIGTERM)
        #giskard_process.wait()


if __name__ == "__main__":
    main()
