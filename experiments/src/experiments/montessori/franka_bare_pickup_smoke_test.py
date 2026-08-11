"""
The smallest possible scene that can show a Panda picking up a shape: a floor, one
tabletop, the Panda bolted to it, and a single loose cube on the table -- nothing else.

Deliberately not built on :class:`~experiments.montessori.world.MontessoriWorld`: that
scene carries a sorting board (with its cut mesh, drawers, and a whole row of shapes),
and having all of that physically present nearby means a failed grasp cannot cleanly be
told apart from the arm's reach fouling one of them. Here, if the grasp fails, it is
failing on its own terms.

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.franka_bare_pickup_smoke_test
    python -m experiments.montessori.franka_bare_pickup_smoke_test --viewer
"""

from __future__ import annotations

import argparse
import logging
import threading

import numpy as np

from experiments.montessori.franka_panda_equipment import (
    GRASP_FRICTION,
    apply_grasp_contact_parameters,
    equip_panda_for_physical_simulation,
    parse_panda,
)
from experiments.montessori.world import mount_stationary_robot
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.panda import Panda
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
)
from semantic_digital_twin.utils import rclpy_installed
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.geometry import Box, Color, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

NODE_NAME = "franka_bare_pickup_smoke_test"
"""
Name of the ROS 2 node this script's execution runs against.
"""

FLOOR_SCALE = Scale(3.0, 3.0, 0.02)
"""
Size of the floor slab, whose top surface is the world's ``z = 0``.
"""

TABLE_TOP_SCALE = Scale(0.6, 0.9, 0.025)
"""
Size of the tabletop. No legs: nothing here stands on the floor, and legs are only more
geometry for a reach to collide with.
"""

TABLE_TOP_POSITION = Point3(-0.4, 0.0, 0.5)
"""
Centre of the tabletop.
"""

TABLE_TOP_SURFACE_Z = float(TABLE_TOP_POSITION.z) + TABLE_TOP_SCALE.z / 2
"""
Height of the tabletop's upper surface, which the Panda and the cube both rest on.
"""

MOUNT_STANDOFF_DISTANCE = 0.35
"""
How far past the tabletop's near edge the Panda is bolted.
"""

MOUNT_POSITION = Point3(
    float(TABLE_TOP_POSITION.x) + TABLE_TOP_SCALE.x / 2 + MOUNT_STANDOFF_DISTANCE,
    0.0,
    TABLE_TOP_SURFACE_Z,
)
"""
Where the Panda is bolted: past the tabletop's near edge, at table height.
"""

MOUNT_YAW = np.pi
"""
Which way the mounted Panda faces: towards the cube, which lies at lower ``x``.
"""

CUBE_EDGE_LENGTH = 0.03
"""
Edge length of the loose cube; matches
:data:`~experiments.montessori.world.MontessoriWorld`'s own cube shape, for a fair
comparison against the full scene.
"""

CUBE_POSITION = Point3(-0.15, -0.30, TABLE_TOP_SURFACE_Z + CUBE_EDGE_LENGTH / 2)
"""
Where the cube rests: offset from the mount's own y (matching the montessori scene's
``square_hole_shape`` slot exactly), to test whether an off-centre lateral reach -- not
the board or the other shapes -- is what the full-scene attempt still fails on.
"""

MUJOCO_STEP_SIZE = 1e-4
"""
Physics step size, matching ``coraplex_panda_demo/demo.py``'s own exactly.
"""

SYNC_RATE_HZ = 100
"""
Rate at which the physically simulated joints' real, physics-driven positions are read
back into the world model.
"""


def _box_body(name: str, scale: Scale, color: Color) -> Body:
    """
    A body whose visual and collision geometry are one box.

    :param name: Name of the body.
    :param scale: Size of the box.
    :param color: Colour of the box.
    """
    return Body.from_shape_collection(
        PrefixedName(name, NODE_NAME), ShapeCollection([Box(scale=scale, color=color)])
    )


def build_scene() -> tuple[World, Panda, Body]:
    """
    Build the floor, tabletop, bolted Panda and one loose cube.

    :return: The world, the mounted Panda, and the loose cube's body.
    """
    world = World()
    with world.modify_world():
        root = Body(name=PrefixedName("root", NODE_NAME))
        world.add_kinematic_structure_entity(root)

        floor = _box_body("floor", FLOOR_SCALE, Color.GREY())
        world.add_connection(
            FixedConnection(
                parent=root,
                child=floor,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    z=-FLOOR_SCALE.z / 2
                ),
            )
        )

        table_top = _box_body("table_top", TABLE_TOP_SCALE, Color.BEIGE())
        world.add_connection(
            FixedConnection(
                parent=root,
                child=table_top,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=TABLE_TOP_POSITION.x,
                    y=TABLE_TOP_POSITION.y,
                    z=TABLE_TOP_POSITION.z,
                ),
            )
        )

        cube = _box_body(
            "cube",
            Scale(CUBE_EDGE_LENGTH, CUBE_EDGE_LENGTH, CUBE_EDGE_LENGTH),
            Color.RED(),
        )
        cube_connection = Connection6DoF.create_with_dofs(
            world=world, parent=root, child=cube
        )
        world.add_connection(cube_connection)

        # Matches MontessoriWorld.add_robot_stand's own geometry exactly, to test
        # whether the stand itself (not the board or the other shapes) is what the
        # full montessori scene's reach is fouling on.
        stand_scale = Scale(0.3, 0.3, 0.025)
        stand = _box_body("stand", stand_scale, Color.BEIGE())
        world.add_connection(
            FixedConnection(
                parent=root,
                child=stand,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=MOUNT_POSITION.x,
                    y=MOUNT_POSITION.y,
                    z=float(MOUNT_POSITION.z) - stand_scale.z / 2,
                ),
            )
        )
        stand_leg = _box_body(
            "stand_leg", Scale(0.05, 0.05, float(MOUNT_POSITION.z)), Color.BEIGE()
        )
        world.add_connection(
            FixedConnection(
                parent=root,
                child=stand_leg,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=MOUNT_POSITION.x,
                    y=MOUNT_POSITION.y,
                    z=float(MOUNT_POSITION.z) / 2,
                ),
            )
        )

    # Set after the connection is added to the world so the pose lands in the free
    # joint's own dof values, which is what MuJoCo reads as its starting pose; passed to
    # create_with_dofs instead it would be a fixed offset and the cube would start at
    # the world origin.
    cube_connection.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=CUBE_POSITION.x,
        y=CUBE_POSITION.y,
        z=CUBE_POSITION.z,
        reference_frame=root,
    )

    robot = mount_stationary_robot(
        world, Panda, parse_panda(), MOUNT_POSITION, mount_yaw=MOUNT_YAW
    )
    apply_grasp_contact_parameters([cube], GRASP_FRICTION)

    return world, robot, cube


def _parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments selecting whether a MuJoCo viewer window is opened.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Open a MuJoCo viewer window; off by default so this runs headless.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Build the bare scene and try to pick the cube up and move it, reporting whether it
    actually moved.
    """
    # force: the CRAM/Giskard stack configures the root logger on import, which would
    # otherwise swallow this script's own reporting.
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    arguments = _parse_arguments()

    if not rclpy_installed():
        logger.error("rclpy is not installed; this needs the CRAM/Giskard stack.")
        return

    import rclpy
    from rclpy.executors import SingleThreadedExecutor

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
    from coraplex.plans.failures import PlanFailure
    from coraplex.robot_plans.actions.core.pick_up import PickUpAction
    from coraplex.robot_plans.actions.core.placing import PlaceAction
    from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
    from semantic_digital_twin.adapters.multi_sim import MujocoSim
    from semantic_digital_twin.spatial_types.spatial_types import Pose

    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    spinner.start()

    world, robot, cube = build_scene()
    physically_simulated_dofs = equip_panda_for_physical_simulation(robot)

    multi_sim = MujocoSim(
        world=world,
        headless=not arguments.viewer,
        step_size=MUJOCO_STEP_SIZE,
        real_time_factor=None if not arguments.viewer else 1.0,
        physically_simulated_dofs=physically_simulated_dofs,
        sync_rate_hz=SYNC_RATE_HZ,
    )
    context = Context(world, robot, ros_node=node, update_world_model_attachment=False)
    context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time
    arm = robot.get_arms()[0]
    gripper = arm.end_effector

    multi_sim.start_simulation()
    try:
        world.update_forward_kinematics()
        start_position = cube.global_transform.to_position()

        plan = sequential(
            [
                ParkArmsAction(Arms.RIGHT),
                PickUpAction(
                    cube,
                    Arms.RIGHT,
                    GraspDescription(
                        ApproachDirection.FRONT,
                        VerticalAlignment.TOP,
                        gripper,
                        rotate_gripper=True,
                    ),
                ),
                PlaceAction(
                    cube,
                    Pose.from_xyz_rpy(
                        x=start_position.x,
                        y=start_position.y + 0.15,
                        z=start_position.z,
                        reference_frame=world.root,
                    ),
                    Arms.RIGHT,
                ),
                ParkArmsAction(Arms.RIGHT),
            ],
            context=context,
        )
        with ExecutionEnvironment(
            execution_type=ExecutionType.SIMULATED,
            collision_avoidance=False,
            real_time_pacing=True,
            max_ticks_per_motion_mapping=300,
        ):
            try:
                plan.perform()
            except PlanFailure as failure:
                logger.error("Pick-and-place did not finish: %s", failure)

        world.update_forward_kinematics()
        end_position = cube.global_transform.to_position()
        moved = float(
            np.linalg.norm(
                [
                    float(end_position.x) - float(start_position.x),
                    float(end_position.y) - float(start_position.y),
                ]
            )
        )
        logger.info(
            "cube: (%.3f, %.3f, %.3f) -> (%.3f, %.3f, %.3f); moved %.3f m "
            "horizontally (moved: %s)",
            float(start_position.x),
            float(start_position.y),
            float(start_position.z),
            float(end_position.x),
            float(end_position.y),
            float(end_position.z),
            moved,
            moved > 0.05,
        )
    finally:
        multi_sim.stop_simulation()
        executor.shutdown()
        spinner.join(timeout=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
