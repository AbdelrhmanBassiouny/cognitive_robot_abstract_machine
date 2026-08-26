"""
Tracy's left arm picks up every loose Montessori shape that has a matching hole and
places it above that hole, with MuJoCo standing in as the real robot: one
:class:`~experiments.tracy_experiments.pick_and_place_action.PickUpActionMujoco`/
:class:`~experiments.tracy_experiments.pick_and_place_action.PlaceActionMujoco` pair per
shape, written out as one flat :func:`~coraplex.plans.factories.sequential` plan (Tracy's
four sorted shapes and their matching holes are fixed by :class:`~experiments.
tracy_experiments.montessori.world.TracyMontessoriWorld`'s own construction, so the plan
does not need to be built dynamically) -- see :mod:`~experiments.tracy_experiments.
pick_and_place_action`'s own docstring for why each action's own leaf motion runs plain
Python (driving MuJoCo actuators directly) rather than a Giskard motion mapping.

See :mod:`~experiments.tracy_experiments.montessori.montessori_demo_real` for the physical-robot
counterpart, which builds its action sequence dynamically from the real
``PickUpAction``/``PlaceAction`` via :func:`~experiments.tracy_experiments.montessori.
montessori_actions.build_sorting_actions` instead.

Run with (the ``iai_tracy_description`` ROS package must be built and sourced)::

    python -m experiments.tracy_experiments.montessori.montessori_demo_mujoco
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

    apply_montessori_grasp_contact_parameters(
        world.get_semantic_annotations_by_type(MontessoriShape)
    )
    apply_contact_friction([montessori.board.root], BOARD_FRICTION)

    joint_state_of_type(robot.left_arm.end_effector, GripperState.OPEN).apply_to(world)
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
            for arm in [robot.left_arm, robot.right_arm]:
                park_state = joint_state_of_type(arm, StaticJointState.PARK)
                for connection, target in zip(
                    park_state.connections, park_state.target_values
                ):
                    sim.command(actuators[connection.raw_dof.name.name], target)
            sim.advance(0.5)

            shapes_by_name = {
                shape.name.name: shape
                for shape in world.get_semantic_annotations_by_type(MontessoriShape)
            }
            circular_hole_1_shape = shapes_by_name["circular_hole_1_shape"]
            square_hole_shape = shapes_by_name["square_hole_shape"]
            triangle_hole_shape = shapes_by_name["triangle_hole_shape"]
            rectangular_hole_shape = shapes_by_name["rectangular_hole_shape"]

            grasp_description = GraspDescription(
                ApproachDirection.FRONT,
                VerticalAlignment.TOP,
                ViewManager.get_end_effector_view(PICK_ARM, robot),
            )

            plan = sequential(
                [
                    # circular_hole_1_shape -> circular_hole_1
                    PickUpActionMujoco(
                        object_designator=circular_hole_1_shape.root,
                        arm=PICK_ARM,
                        grasp_description=grasp_description,
                        sim=sim,
                        actuators=actuators,
                    ),
                    PlaceActionMujoco(
                        object_designator=circular_hole_1_shape.root,
                        target_location=montessori.board.hole_for(
                            circular_hole_1_shape
                        ).root.global_transform.to_pose(),
                        arm=PICK_ARM,
                        sim=sim,
                        actuators=actuators,
                    ),
                    # square_hole_shape -> square_hole
                    PickUpActionMujoco(
                        object_designator=square_hole_shape.root,
                        arm=PICK_ARM,
                        grasp_description=grasp_description,
                        sim=sim,
                        actuators=actuators,
                    ),
                    PlaceActionMujoco(
                        object_designator=square_hole_shape.root,
                        target_location=montessori.board.hole_for(
                            square_hole_shape
                        ).root.global_transform.to_pose(),
                        arm=PICK_ARM,
                        sim=sim,
                        actuators=actuators,
                    ),
                    # triangle_hole_shape -> triangle_hole
                    PickUpActionMujoco(
                        object_designator=triangle_hole_shape.root,
                        arm=PICK_ARM,
                        grasp_description=grasp_description,
                        sim=sim,
                        actuators=actuators,
                    ),
                    PlaceActionMujoco(
                        object_designator=triangle_hole_shape.root,
                        target_location=montessori.board.hole_for(
                            triangle_hole_shape
                        ).root.global_transform.to_pose(),
                        arm=PICK_ARM,
                        sim=sim,
                        actuators=actuators,
                    ),
                    # rectangular_hole_shape -> rectangular_hole
                    PickUpActionMujoco(
                        object_designator=rectangular_hole_shape.root,
                        arm=PICK_ARM,
                        grasp_description=grasp_description,
                        sim=sim,
                        actuators=actuators,
                    ),
                    PlaceActionMujoco(
                        object_designator=rectangular_hole_shape.root,
                        target_location=montessori.board.hole_for(
                            rectangular_hole_shape
                        ).root.global_transform.to_pose(),
                        arm=PICK_ARM,
                        sim=sim,
                        actuators=actuators,
                    ),
                ],
                context,
            ).plan
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
