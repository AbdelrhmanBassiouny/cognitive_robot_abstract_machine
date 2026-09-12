"""
Tracy's left arm stacks a tower of cubes onto a base cube, with MuJoCo standing in as
the real robot: one :class:`~experiments.tracy_experiments.pick_and_place_action.
PickUpActionMujoco`/:class:`~experiments.tracy_experiments.pick_and_place_action.
PlaceActionMujoco` pair per cube, composed into a single
:func:`~coraplex.plans.factories.sequential` plan -- mirroring
:mod:`~experiments.tracy_experiments.montessori.montessori_demo_mujoco`'s own action-sequence
pattern rather than driving :mod:`~experiments.tracy_experiments.trajectory_planning`
directly.

Every cube's own target pose in the stack is precomputed up front (see
:func:`~experiments.tracy_experiments.stacking.stacking_actions.stack_target_pose`) rather than
measured after each place: unlike an earlier version of this demo, a missed grasp is not
tolerated by re-measuring the stack's own current height, only by the pick/place
action's own retry-free reach.

See :mod:`~experiments.tracy_experiments.stacking.stacking_demo_real` for the physical-robot
counterpart, which builds the same action sequence from the real
``PickUpAction``/``PlaceAction`` instead.

Run with (the ``iai_tracy_description`` ROS package must be built and sourced)::

    python -m experiments.tracy_experiments.stacking.stacking_demo_mujoco
"""

from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import ApproachDirection, Arms, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.factories import sequential
from coraplex.view_manager import ViewManager
from experiments.montessori.world import mount_stationary_robot
from experiments.tracy_experiments.equipment import (
    add_cube,
    apply_gravity_compensation,
    equip_arms_with_servos,
    equip_grippers_with_servos,
    exclude_self_collision,
    joint_state_of_type,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.pick_and_place_action import (
    PickUpActionMujoco,
    PlaceActionMujoco,
)
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from experiments.tracy_experiments.stacking.stacking_actions import stack_target_pose
from experiments.tracy_experiments.trajectory_planning import park_arms
from semantic_digital_twin.datastructures.definitions import GripperState
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

TRACY_MOUNT_X = 0.0
TRACY_MOUNT_Y = 0.0
"""
Where Tracy's own root ("table") is bolted, in the scene's root frame.
"""

STACK_ARM = Arms.LEFT
"""
Which arm stacks every cube.
"""

CUBE_SIZE = 0.05
"""
Edge length of every cube, in metres -- well inside the Robotiq 2F-85's roughly 85mm
opening.
"""

_STACK_XY = (0.8, 0.0)
"""
Where the base cube stands, and every cube is stacked on top of it.
"""

_PICK_XY_LIST = [(0.8, 0.25), (0.8, 0.10), (0.8, 0.40)]
"""
Tracy's left arm's own pick coordinates, one per cube stacked onto the base.

Spaced 0.15m apart along Y -- a full cube's own edge length of clearance -- so an
empty-gripper reach for one cube's own hover pose does not sweep the arm into its
neighbour.
"""


def _build_world_and_cubes() -> tuple[World, Tracy, float, dict[str, Body]]:
    """
    Mount Tracy and add the base cube plus every cube to be stacked onto it, all resting
    on the table.

    :return: The world, the mounted robot, the table's own top height, and every cube
        (including the base) keyed by name.
    """
    tracy_world = parse_tracy()
    mount_position, top_z = tracy_table_mount_position(
        tracy_world, x=TRACY_MOUNT_X, y=TRACY_MOUNT_Y
    )
    world = World()
    robot = mount_stationary_robot(
        world, Tracy, tracy_world, mount_position, mount_yaw=0.0
    )

    cube_center_z = top_z + CUBE_SIZE / 2
    stack_x, stack_y = _STACK_XY
    cube_bodies = {
        "cube_base": add_cube(
            world,
            "cube_base",
            Point3(stack_x, stack_y, cube_center_z),
            CUBE_SIZE,
            Color(0.3, 0.9, 0.3, 1.0),
        )
    }

    cube_names = [f"cube_{index + 1}" for index in range(len(_PICK_XY_LIST))]
    cube_colors = [
        Color(0.9, 0.3, 0.3, 1.0),
        Color(0.3, 0.3, 0.9, 1.0),
        Color(0.9, 0.8, 0.2, 1.0),
    ]
    for name, (pick_x, pick_y), color in zip(cube_names, _PICK_XY_LIST, cube_colors):
        cube_bodies[name] = add_cube(
            world, name, Point3(pick_x, pick_y, cube_center_z), CUBE_SIZE, color
        )

    return world, robot, top_z, cube_bodies


def main(headless: bool = False) -> None:
    """
    Build the scene, then pick up each cube in :data:`_PICK_XY_LIST` in turn and stack
    it on the growing tower, at its precomputed target pose.

    :param headless: Whether to run without opening MuJoCo's viewer window.
    """
    world, robot, table_top_z, cube_bodies = _build_world_and_cubes()
    stack_cube_names = [name for name in cube_bodies if name != "cube_base"]

    joint_state_of_type(robot.right_arm.end_effector, GripperState.CLOSE).apply_to(
        world
    )
    joint_state_of_type(robot.left_arm.end_effector, GripperState.OPEN).apply_to(world)
    world.notify_state_change()

    apply_gravity_compensation(world, robot)
    exclude_self_collision(world, robot)
    arm_actuators = equip_arms_with_servos(world, robot)
    gripper_actuators = equip_grippers_with_servos(world, robot)
    actuators = {**arm_actuators, **gripper_actuators}

    context = Context(world, robot, evaluate_conditions=False)

    with RealTimeSimulation(world=world, headless=headless, step_size=1e-3) as sim:
        try:
            time.sleep(5)
            park_arms(sim, actuators, robot, [Arms.LEFT, Arms.RIGHT])

            stack_x, stack_y = _STACK_XY
            grasp_description = GraspDescription(
                ApproachDirection.FRONT,
                VerticalAlignment.TOP,
                ViewManager.get_end_effector_view(STACK_ARM, robot),
            )

            actions = []
            for stack_index, name in enumerate(stack_cube_names, start=1):
                actions.append(
                    PickUpActionMujoco(
                        object_designator=cube_bodies[name],
                        arm=STACK_ARM,
                        grasp_description=grasp_description,
                        sim=sim,
                        actuators=actuators,
                    )
                )
                actions.append(
                    PlaceActionMujoco(
                        object_designator=cube_bodies[name],
                        target_location=stack_target_pose(
                            stack_index,
                            stack_x,
                            stack_y,
                            table_top_z,
                            CUBE_SIZE,
                            world.root,
                        ),
                        arm=STACK_ARM,
                        sim=sim,
                        actuators=actuators,
                    )
                )

            plan = sequential(actions, context).plan
            plan.perform()
            logger.info("Stacking plan finished.")
        except Exception as error:
            logger.warning("Stacking plan raised: %r", error)
        finally:
            final_positions = sim.multi_sim.simulator.get_bodies_positions(
                list(cube_bodies)
            ).result
            for name in cube_bodies:
                logger.info("%s final position: %s", name, final_positions[name])

            if not headless:
                while sim.is_running:
                    time.sleep(0.1)


if __name__ == "__main__":
    main()
