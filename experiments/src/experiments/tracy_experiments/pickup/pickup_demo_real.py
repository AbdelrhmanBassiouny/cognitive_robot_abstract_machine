"""
The physical Tracy's left arm picks up a single cube -- pickup only, no place -- wired
the way :mod:`coraplex_real_tracy.demo` wires the physical robot: a Giskard standalone
node is launched, the live world is fetched from a running ``WorldFetcher`` service and
kept in sync via :class:`~semantic_digital_twin.adapters.ros.
world_synchronizer.WorldSynchronizer`, and the plan runs under
:attr:`~coraplex.datastructures.enums.ExecutionType.REAL`.

The cube is added to the live, fetched world as a plain
:class:`~semantic_digital_twin.world_description.world_entity.Body`, the same
symbolic-anchor trick :mod:`~experiments.tracy_experiments.stacking.stacking_demo_real`
uses -- it is not a perception result, so the physical cube must already be placed at
:data:`CUBE_X`/:data:`CUBE_Y` by hand before this runs. Once added it is visible in the
same rviz the physical robot renders in (via ``WorldSynchronizer``), so its position can
be checked against the real cube before the pickup runs -- the script pauses for that
check right after spawning it.

Run with (``iai_tracy_description`` and the Giskard/world-fetcher ROS stack must be
running)::

    python -m experiments.tracy_experiments.pickup.pickup_demo_real
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
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from coraplex.view_manager import ViewManager
from experiments.tracy_experiments.equipment import table_top_z as read_table_top_z
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

PICK_ARM = Arms.LEFT
"""
Which arm picks up the cube.
"""

CUBE_SIZE = 0.03
"""
Edge length of the cube, in metres.
"""

CUBE_X = 0.8
CUBE_Y = 0.0
"""
Where the cube must already be placed by hand before this runs, in the live world's root
frame.
"""


def _add_cube(world: World, mounted_table_top_z: float) -> Body:
    """
    Add the cube to the live, fetched world as a fixed, symbolic body at
    :data:`CUBE_X`/:data:`CUBE_Y`, resting on the live robot's own table top -- not a
    perception result, so the physical cube must already be there.

    :param world: The live world to add the cube to, modified in place.
    :param mounted_table_top_z: Height of the live robot's own table top, read via
        :func:`~experiments.tracy_experiments.equipment.table_top_z`.
    :return: The newly added cube.
    """
    cube = Body(
        name=PrefixedName("pickup_cube"),
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
    cube_center_z = mounted_table_top_z + CUBE_SIZE / 2
    with world.modify_world():
        world.add_kinematic_structure_entity(cube)
        world.add_connection(
            FixedConnection.create_with_dofs(
                parent=world.root,
                child=cube,
                world=world,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    CUBE_X, CUBE_Y, cube_center_z
                ),
            )
        )
    return cube


def main() -> None:
    giskard_process = subprocess.Popen(
        ["ros2", "launch", "giskardpy_ros", "giskardpy_tracy_standalone.launch.py"],
        start_new_session=True,
    )
    time.sleep(8)  # Wait for the launch file to start

    rclpy.init()
    node = rclpy.create_node("tracy_pickup_demo_real")
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    thread.start()

    try:
        world = fetch_world_from_service(node=node, timeout_seconds=300)
        WorldSynchronizer(_world=world, node=node)
        [robot] = world.get_semantic_annotations_by_type(Tracy)

        cube = _add_cube(world, read_table_top_z(robot))

        logger.info(
            "Cube spawned in rviz at x=%.3f, y=%.3f. Check it lines up with the real "
            "cube, then press Enter to run the pickup.",
            CUBE_X,
            CUBE_Y,
        )
        input()

        context = Context(
            world=world, robot=robot, ros_node=node, evaluate_conditions=False
        )
        grasp_description = GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(PICK_ARM, robot),
        )
        actions = [
            ParkArmsAction(Arms.BOTH),
            PickUpAction(cube, PICK_ARM, grasp_description),
        ]
        plan = sequential(actions, context=context).plan

        logger.info("Performing pickup plan on the real robot.")
        with ExecutionEnvironment(
            execution_type=ExecutionType.REAL, collision_avoidance=True
        ):
            plan.perform()
        logger.info("Pickup plan finished.")
    finally:
        os.killpg(os.getpgid(giskard_process.pid), signal.SIGTERM)
        giskard_process.wait()


if __name__ == "__main__":
    main()
