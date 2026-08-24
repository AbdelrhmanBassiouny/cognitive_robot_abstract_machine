"""
Tracy's left arm picks up every loose Montessori shape that has a matching hole and
places it above that hole, with MuJoCo standing in as the real robot: one
:class:`~experiments.tracy_experiments.pick_and_place_action.PickUpActionMujoco`/
:class:`~experiments.tracy_experiments.pick_and_place_action.PlaceActionMujoco` pair per
shape (see :func:`~experiments.tracy_experiments.montessori.montessori_actions.
build_sorting_actions`), composed into a single :func:`~coraplex.plans.factories.sequential`
plan -- see :mod:`~experiments.tracy_experiments.pick_and_place_action`'s own docstring
for why each action's own leaf motion runs plain Python (driving MuJoCo actuators
directly) rather than a Giskard motion mapping.

See :mod:`~experiments.tracy_experiments.montessori.montessori_demo_real` for the physical-robot
counterpart, which builds the same action sequence from the real
``PickUpAction``/``PlaceAction`` instead.

Run with (the ``iai_tracy_description`` ROS package must be built and sourced)::

    python -m experiments.tracy_experiments.montessori.montessori_demo_mujoco
"""

from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.plans.factories import sequential
from experiments.montessori.semantics import MontessoriShape
from experiments.tracy_experiments.equipment import (
    apply_gravity_compensation,
    equip_arms_with_servos,
    equip_grippers_with_servos,
    exclude_self_collision,
    joint_state_of_type,
    parse_tracy,
    tracy_table_mount_position,
)
from experiments.tracy_experiments.grasp_contact import (
    BOARD_FRICTION,
    apply_contact_friction,
    apply_montessori_grasp_contact_parameters,
)
from experiments.tracy_experiments.montessori.montessori_actions import (
    build_sorting_actions,
)
from experiments.tracy_experiments.pick_and_place_action import (
    PickUpActionMujoco,
    PlaceActionMujoco,
)
from experiments.tracy_experiments.real_time_simulation import RealTimeSimulation
from experiments.tracy_experiments.montessori.world import TracyMontessoriWorld
from semantic_digital_twin.datastructures.definitions import (
    GripperState,
    StaticJointState,
)
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Drawer,
    Handle,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.shape_collection import ShapeCollection

logger = logging.getLogger(__name__)

TRACY_MOUNT_X = 0.0
TRACY_MOUNT_Y = 0.0
"""
Where Tracy's own root ("table") is bolted, in the scene's root frame; matches
:mod:`~experiments.tracy_experiments.montessori.world`'s own proven-reachable coordinates.
"""

PICK_ARM = Arms.LEFT
"""
Which arm sorts every shape.
"""


def _strip_drawer_collision(world: World) -> None:
    """
    Remove the board's own drawers' and handles' collision geometry, leaving their
    visual geometry untouched.

    Nothing in this demo ever opens a drawer -- picking a shape up off the table and
    placing it above its matching hole never touches one -- but a drawer's own handle
    projects out towards the robot far enough that reaching for a nearby shape or hole
    repeatedly swept the arm through it, confirmed directly as a recurring
    ``CollisionViolatedError`` against the same handle, independent of the reach target
    or the board's own position. Removing an interaction this demo never needed is
    simpler than routing every reach around it.

    :param world: The world to modify in place.
    """
    with world.modify_world():
        for drawer in world.get_semantic_annotations_by_type(Drawer):
            drawer.root.collision = ShapeCollection([])
        for handle in world.get_semantic_annotations_by_type(Handle):
            handle.root.collision = ShapeCollection([])


def main(headless: bool = False) -> None:
    """
    Build the Montessori world on Tracy's own table, then pick up every loose shape that
    has a matching hole and place it above that hole.

    :param headless: Whether to run without opening MuJoCo's viewer window.
    """
    tracy_world = parse_tracy()
    mount_position, table_top_z = tracy_table_mount_position(
        tracy_world, x=TRACY_MOUNT_X, y=TRACY_MOUNT_Y
    )
    montessori = TracyMontessoriWorld(shapes_are_movable=True, table_top_z=table_top_z)
    robot = montessori.mount_stationary_robot(
        Tracy, tracy_world, mount_position, mount_yaw=0.0
    )
    world = montessori.world
    # _strip_drawer_collision(world)
    # Without this, the loose shapes keep MuJoCo's own soft contact defaults, which let
    # a shape pinched between the fingers sink in and slip back out as the arm lifts.
    apply_montessori_grasp_contact_parameters(
        world.get_semantic_annotations_by_type(MontessoriShape)
    )
    apply_contact_friction([montessori.board.root], BOARD_FRICTION)

    joint_state_of_type(robot.left_arm.end_effector, GripperState.OPEN).apply_to(world)
    # Both arms start already parked, baked into the initial pose, rather than being
    # physically driven there once the simulation starts: the sweep from Tracy's raw
    # parsed (URDF-zero) pose to its park target passes close enough to the board that
    # driving it for real, with collision avoidance either on (it could not find a
    # compliant path) or off (a real, high-force contact), either raised a hard
    # collision error or visibly knocked the loose shapes around -- confirmed directly.
    # Starting already parked skips that sweep entirely.
    joint_state_of_type(robot.left_arm, StaticJointState.PARK).apply_to(world)
    joint_state_of_type(robot.right_arm, StaticJointState.PARK).apply_to(world)
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
            # Both arms' own actuators are commanded to their park targets directly
            # here, matching the pose already baked into the world's own initial state
            # (see above) -- not planned and driven there via park_arms, since that
            # would physically sweep the arm from its raw parsed pose through the
            # board's own vicinity to reach park, which visibly knocked the loose
            # shapes around even with collision avoidance off.
            for arm in [robot.left_arm, robot.right_arm]:
                park_state = joint_state_of_type(arm, StaticJointState.PARK)
                for connection, target in zip(
                    park_state.connections, park_state.target_values
                ):
                    sim.command(actuators[connection.raw_dof.name.name], target)
            sim.advance(0.5)

            actions = build_sorting_actions(
                world,
                montessori.board,
                robot,
                PICK_ARM,
                pick_up_action=lambda body, arm, grasp: PickUpActionMujoco(
                    object_designator=body,
                    arm=arm,
                    grasp_description=grasp,
                    sim=sim,
                    actuators=actuators,
                ),
                place_action=lambda body, target, arm: PlaceActionMujoco(
                    object_designator=body,
                    target_location=target,
                    arm=arm,
                    sim=sim,
                    actuators=actuators,
                ),
            )

            plan = sequential(actions, context).plan
            plan.perform()
            logger.info("Sorting plan finished.")
        except Exception as error:
            logger.warning("Sorting plan raised: %r", error)
        finally:
            world.update_forward_kinematics()
            for shape in world.get_semantic_annotations_by_type(MontessoriShape):
                position = shape.root.global_transform.to_position()
                logger.info(
                    "%s final position: (%.3f, %.3f, %.3f)",
                    shape.name,
                    float(position.x),
                    float(position.y),
                    float(position.z),
                )

            if not headless:
                while sim.is_running:
                    time.sleep(0.1)


if __name__ == "__main__":
    main()
