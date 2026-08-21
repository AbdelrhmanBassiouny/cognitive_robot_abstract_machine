"""
Tracy stacks one cube on top of another, held only by real MuJoCo contact friction, in
MuJoCo.

Giskard still drives the left arm's Cartesian reaches (small moves are the common case
it is built for, unlike ``ParkArmsAction``'s own large joint-space jump that turned out
to be unreliable for Tracy -- see :mod:`tracy_equipment`'s own docstring), but every one
of the left arm's and its gripper's joints are listed in ``physically_simulated_dofs``
(see :class:`~semantic_digital_twin.adapters.multi_sim.MujocoSynchronizer`), matching
``coraplex_panda_demo``'s own proven pick-and-place pattern: those DOFs are driven by
real actuator/contact dynamics rather than kinematically teleported every tick, so a cube
held only by the gripper's squeeze is not left behind the instant a kinematic snap would
otherwise yank the arm out from under it -- friction can only react to continuous motion,
not an instantaneous position jump. Only the two cubes are additionally, independently
physically simulated, as free bodies with real collision geometry (see
:func:`tracy_equipment.add_cube`); nothing ever kinematically attaches a cube to the
gripper (no ``AttachNode``/``PickUpAction``/``PlaceAction``).

Run with (the ``iai_tracy_description`` ROS package must be built and sourced)::

    python coraplex/demos/coraplex_tracy_demo/stacking_demo.py
"""

from __future__ import annotations

import logging
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")

from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from semantic_digital_twin.world_description.geometry import Color

# coraplex/demos is not part of the coraplex package (only coraplex/src is on
# sys.path); this "demos" tree is a collection of standalone scripts run directly
# (python coraplex/demos/coraplex_tracy_demo/stacking_demo.py), matching every sibling
# demo here, so this sibling module is only reachable as a bare import.
from tracy_equipment import (
    add_cube,
    apply_gravity_compensation,
    equip_arms_with_servos,
    exclude_self_collision,
    joint_state_of_type,
)

logger = logging.getLogger(__name__)

NODE_NAME = "tracy_stacking_demo"

CUBE_SIZE = 0.05
"""
Edge length of both cubes, in metres -- well inside the Robotiq 2F-85's roughly 85mm
opening, unlike ``coraplex_real_tracy/demo.py``'s own 10cm boxes, which that demo never
actually has to close its fingers around since it holds them with an ``AttachNode``
instead of real friction.
"""

_PICK_XY = (0.8, 0.25)
_STACK_XY = (0.8, 0.0)
"""
Reused as-is from ``coraplex_real_tracy/demo.py``'s own proven-reachable coordinates
for Tracy's left arm (its own ``box2``, picked by ``Arms.LEFT``, and its own stack base)
-- not re-derived here, since that demo already established these work.
"""

HOVER_CLEARANCE = 0.15
"""
Height, in metres, above a cube's own top face the TCP moves to before descending onto
it -- clears the cube during the horizontal part of each approach, so the gripper never
drags across the table or another cube on its way in.
"""


def _table_top_z(robot: Tracy) -> float:
    """
    Height of Tracy's own table's top surface above the world root, in metres.

    :param robot: The robot whose table height is read.
    """
    table = robot.root
    tabletop = max(table.collision, key=lambda shape: shape.scale.x * shape.scale.y)
    root_transform_table = robot._world.compute_forward_kinematics_np(
        robot._world.root, table
    )
    return float(
        root_transform_table[2, 3] + tabletop.origin.to_np()[2, 3] + tabletop.scale.z / 2
    )


def main(headless: bool = False) -> None:
    """
    Build the scene, pick up the first cube, and stack it on the second.

    :param headless: Whether to run without opening MuJoCo's viewer window.
    """
    from coraplex.datastructures.dataclasses import Context
    from coraplex.datastructures.enums import Arms, ExecutionType, MovementType
    from coraplex.execution_environment import ExecutionEnvironment
    from coraplex.plans.factories import sequential
    from coraplex.robot_plans.motions.gripper import (
        MoveGripperMotion,
        MoveToolCenterPointMotion,
    )

    world = URDFParser.from_file(Tracy.get_ros_file_path()).parse()
    robot = Tracy.from_world(world)

    joint_state_of_type(robot.right_arm, StaticJointState.PARK).apply_to(world)
    joint_state_of_type(robot.right_arm.end_effector, GripperState.CLOSE).apply_to(world)
    joint_state_of_type(robot.left_arm.end_effector, GripperState.OPEN).apply_to(world)
    world.notify_state_change()

    apply_gravity_compensation(world, robot)
    exclude_self_collision(world, robot)
    equip_arms_with_servos(world, robot)

    physically_simulated_dofs = {
        connection.raw_dof
        for connection in robot.left_arm.active_connections
        + robot.left_arm.end_effector.active_connections
        if isinstance(connection, ActiveConnection1DOF)
    }

    table_top_z = _table_top_z(robot)
    cube_center_z = table_top_z + CUBE_SIZE / 2
    stacked_center_z = table_top_z + CUBE_SIZE + CUBE_SIZE / 2

    pick_x, pick_y = _PICK_XY
    stack_x, stack_y = _STACK_XY
    add_cube(world, "cube_to_stack", Point3(pick_x, pick_y, cube_center_z), CUBE_SIZE, Color(0.9, 0.3, 0.3, 1.0))
    add_cube(world, "cube_base", Point3(stack_x, stack_y, cube_center_z), CUBE_SIZE, Color(0.3, 0.9, 0.3, 1.0))

    import rclpy
    from rclpy.executors import SingleThreadedExecutor

    if not rclpy.ok():
        rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True, name="rclpy-executor")
    spinner.start()

    multi_sim = MujocoSim(
        world=world,
        headless=headless,
        step_size=1e-3,
        physically_simulated_dofs=physically_simulated_dofs,
        sync_rate_hz=100,
    )
    context = Context(world, robot, ros_node=node, evaluate_conditions=False)
    context.simulation_clock = lambda: multi_sim.simulator.current_simulation_time
    multi_sim.start_simulation()
    time.sleep(0.5)

    def pose(x: float, y: float, z: float) -> Pose:
        return Pose.from_xyz_rpy(x, y, z, yaw=0, reference_frame=world.root)

    pick_hover = pose(pick_x, pick_y, cube_center_z + HOVER_CLEARANCE)
    pick_grasp = pose(pick_x, pick_y, cube_center_z)
    place_hover = pose(stack_x, stack_y, stacked_center_z + HOVER_CLEARANCE)
    place_pose = pose(stack_x, stack_y, stacked_center_z)

    plan = sequential(
        [
            MoveToolCenterPointMotion(pick_hover, Arms.LEFT),
            MoveToolCenterPointMotion(
                pick_grasp, Arms.LEFT, movement_type=MovementType.TRANSLATION
            ),
            MoveGripperMotion(motion=GripperState.CLOSE, gripper=Arms.LEFT),
            MoveToolCenterPointMotion(
                pick_hover, Arms.LEFT, movement_type=MovementType.TRANSLATION
            ),
            MoveToolCenterPointMotion(place_hover, Arms.LEFT),
            MoveToolCenterPointMotion(
                place_pose, Arms.LEFT, movement_type=MovementType.TRANSLATION
            ),
            MoveGripperMotion(motion=GripperState.OPEN, gripper=Arms.LEFT),
            MoveToolCenterPointMotion(
                place_hover, Arms.LEFT, movement_type=MovementType.TRANSLATION
            ),
        ],
        context=context,
    )

    try:
        with ExecutionEnvironment(
            execution_type=ExecutionType.SIMULATED,
            collision_avoidance=False,
            real_time_factor=1.0,
            max_ticks_per_motion_mapping=20000,
        ):
            plan.perform()
        logger.info("Stacking plan finished.")
    except Exception as error:
        logger.warning("Stacking plan raised: %r", error)
    finally:
        base_cube = world.get_body_by_name("cube_base")
        top_cube = world.get_body_by_name("cube_to_stack")
        base_position = multi_sim.simulator.get_bodies_positions([base_cube.name.name]).result
        top_position = multi_sim.simulator.get_bodies_positions([top_cube.name.name]).result
        logger.info("cube_base final position: %s", base_position)
        logger.info("cube_to_stack final position: %s", top_position)

        if not headless:
            while True:
                time.sleep(0.1)


if __name__ == "__main__":
    main()
