"""
Minimal Tracy sanity check: mount Tracy on its own built-in table (no Montessori board
or loose shapes at all), start a MuJoCo physics simulation, and have it run
``ParkArmsAction(Arms.BOTH)``.

:mod:`~experiments.montessori.tracy_montessori_demo`'s first full run did not work; this
strips the scene down to just Tracy standing on a bare floor, to isolate whether its own
mounting and physical-simulation equipping (see
:mod:`~experiments.montessori.tracy_equipment`) and Giskard's control loop work at all,
before putting the Montessori task back on top of it.

Run with (the ``experiments`` package must be importable, and ``iai_tracy_description``
must be built and sourced)::

    python -m experiments.montessori.tracy_parkarms_demo
    python -m experiments.montessori.tracy_parkarms_demo --viewer
"""

from __future__ import annotations

import argparse
import logging
import threading
import time
from typing import TYPE_CHECKING

from experiments.montessori.tracy_equipment import (
    equip_tracy_for_physical_simulation,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.montessori.world import _body_with_visual_only_shape, mount_stationary_robot
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.utils import rclpy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.world_entity import Body

if TYPE_CHECKING:
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )

logger = logging.getLogger(__name__)

NODE_NAME = "tracy_parkarms_demo"

FLOOR_SCALE = Scale(4.0, 4.0, 0.02)
"""
Size of the bare floor slab Tracy is mounted on; just big enough to visibly carry its
own table.
"""

FLOOR_Z = 0.0
"""
Height of the ground Tracy's table is mounted to stand on.
"""

MUJOCO_STEP_SIZE = 2e-4
"""
Physics step size, matching :data:`~experiments.montessori.montessori_demo.MUJOCO_STEP_SIZE`:
see :mod:`~experiments.montessori.tracy_equipment`'s own docstring for why Tracy uses the
same generic, unclamped actuator this pairs with rather than the Panda's tuned one.
"""

SYNC_RATE_HZ = 100
"""
Rate at which the physically simulated joints' real, physics-driven positions are read
back into the world model.
"""


def _build_world() -> tuple[World, Tracy]:
    """
    Build a bare floor and mount Tracy on it -- no Montessori board, no loose shapes.

    :return: The assembled world and the mounted Tracy.
    """
    world = World()
    root = Body(name=PrefixedName(name="root", prefix="world"))
    with world.modify_world():
        world.add_kinematic_structure_entity(root)
        floor = _body_with_visual_only_shape(
            PrefixedName("floor", "tracy_parkarms"),
            Box(scale=FLOOR_SCALE, color=Color.GREY()),
        )
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=floor,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=0.0, y=0.0, z=FLOOR_Z - FLOOR_SCALE.z / 2
                ),
            )
        )

    tracy_world = parse_tracy()
    mount_position, table_top_z = tracy_table_mount_position(tracy_world, x=0.0, y=0.0)
    logger.info("Mounting Tracy at %s; table top lands at z=%.3f.", mount_position, table_top_z)
    robot = mount_stationary_robot(world, Tracy, tracy_world, mount_position, mount_yaw=0.0)
    return world, robot


def _park_arms(
    node, viewer: bool, no_rviz: bool
) -> tuple[MujocoSim, "TFPublisher | None", "VizMarkerPublisher | None"]:
    """
    Build the world, equip Tracy for physical simulation, start MuJoCo, and run
    ``ParkArmsAction(Arms.BOTH)``.

    :param node: The ROS 2 node TF/marker publishing runs against.
    :param viewer: Whether to open a MuJoCo viewer window.
    :param no_rviz: Whether to skip publishing TF/visualization markers to RViz.
    :return: The live simulation and publishers, left running for the caller to stop
        once it is done with them.
    """
    from coraplex.datastructures.dataclasses import Context
    from coraplex.datastructures.enums import Arms, ExecutionType
    from coraplex.execution_environment import ExecutionEnvironment
    from coraplex.plans.factories import execute_single
    from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
    from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
        VizMarkerPublisher,
    )

    world, robot = _build_world()
    physically_simulated_dofs = equip_tracy_for_physical_simulation(robot)
    logger.info("Built world with %d bodies; %d physically simulated dofs.", len(world.bodies), len(physically_simulated_dofs))

    tf_publisher = None
    viz_marker_publisher = None
    if not no_rviz:
        tf_publisher = TFPublisher(node=node, _world=world)
        viz_marker_publisher = VizMarkerPublisher(_world=world, node=node)
        logger.info(
            "Visualizing the world on topic '%s'.", viz_marker_publisher.topic_name
        )

    multi_sim = MujocoSim(
        world=world,
        headless=not viewer,
        step_size=MUJOCO_STEP_SIZE,
        real_time_factor=1.0,
        physically_simulated_dofs=physically_simulated_dofs,
        sync_rate_hz=SYNC_RATE_HZ,
    )
    context = Context(world, robot, ros_node=node, evaluate_conditions=False)
    context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time

    multi_sim.start_simulation()
    with ExecutionEnvironment(
        execution_type=ExecutionType.SIMULATED,
        collision_avoidance=False,
        real_time_pacing=False,
    ):
        logger.info("Running ParkArmsAction(Arms.BOTH).")
        plan_node = execute_single(ParkArmsAction(Arms.BOTH), context=context)
        plan_node.perform()
    logger.info("ParkArmsAction finished.")

    return multi_sim, tf_publisher, viz_marker_publisher


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Open a MuJoCo viewer window; off by default so the demo runs headless.",
    )
    parser.add_argument(
        "--no-rviz",
        action="store_true",
        help="Don't publish TF/visualization markers to RViz; publishes by default.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    arguments = _parse_arguments()

    if not rclpy_installed():
        logger.error("rclpy is not installed; this needs the CRAM/Giskard stack.")
        return

    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    spinner.start()

    multi_sim = None
    tf_publisher = None
    viz_marker_publisher = None
    try:
        multi_sim, tf_publisher, viz_marker_publisher = _park_arms(
            node, arguments.viewer, arguments.no_rviz
        )
        logger.info("Done. Press Ctrl+C to stop.")
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if multi_sim is not None:
            multi_sim.stop_simulation()
        if viz_marker_publisher is not None:
            viz_marker_publisher.stop()
        if tf_publisher is not None:
            tf_publisher.stop()
        executor.shutdown()
        spinner.join(timeout=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
