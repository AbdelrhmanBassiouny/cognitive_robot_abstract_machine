"""
Tests a plan that takes a bowl and a cup out of a kitchen drawer with both arms at once
and sets them down on the kitchen island.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import numpy as np
import pytest

from coraplex.plans.context_extensions import MotionToleranceConfig
from coraplex.robot_plans.actions.core.container import OpenAction
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.robot_plans.actions.core.robot_body import (
    MoveTorsoAction,
    ParkArmsAction,
)
from cramph.composites import Parallel, Sequence
from cramph.context import ContextExtension
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.grasping.grasp_candidates import (
    GraspCandidate,
    HasGraspCandidates,
)
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Bowl,
    Cup,
    Handle,
)
from semantic_digital_twin.spatial_types import (
    HomogeneousTransformationMatrix,
    RotationMatrix,
)
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Cylinder
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from ..plan_running import robot_extensions, run_plan

# %% a kitchen with a bowl and a cup in a drawer


@dataclass
class KitchenWithFilledDrawer:
    """
    A PR2 in the kitchen, whose closed drawer holds a bowl and a cup.
    """

    world: World
    """
    The world holding the kitchen, the robot and the two objects.
    """

    robot: PR2
    """
    The robot performing the plan.
    """

    context_extensions: list[ContextExtension]
    """
    The context extensions the plans of :attr:`robot` read.
    """

    drawer_handle: Handle
    """
    The handle of the drawer the objects lie in.
    """

    bowl: Bowl
    """
    The bowl in the drawer.
    """

    cup: Cup
    """
    The cup in the drawer.
    """

    @property
    def kitchen_island(self) -> Body:
        """
        :return: The surface of the kitchen island the objects are set down on.
        """
        return self.world.get_body_by_name("kitchen_island_surface")


def add_cylinder(
    world: World,
    name: str,
    radius: float,
    height: float,
    parent_T_cylinder: HomogeneousTransformationMatrix,
) -> Body:
    """
    :param world: The world the cylinder is added to.
    :param name: The name of the new body.
    :param radius: The radius of the cylinder in meters.
    :param height: The height of the cylinder in meters.
    :param parent_T_cylinder: Where the cylinder stands, relative to the body it is
        fixed to.
    :return: A cylinder fixed to the reference frame of `parent_T_cylinder`.
    """
    shapes = ShapeCollection([Cylinder(width=2 * radius, height=height)])
    cylinder = Body(name=PrefixedName(name), collision=shapes, visual=shapes)
    with world.modify_world():
        world.add_kinematic_structure_entity(cylinder)
        world.add_connection(
            FixedConnection(
                parent=parent_T_cylinder.reference_frame,
                child=cylinder,
                parent_T_connection_expression=parent_T_cylinder,
            )
        )
    return cylinder


def add_handle_frame(world: World, handle_link: Body) -> Body:
    """
    The kitchen's handle links have their x-axis pointing out of the furniture and their
    y-axis along the bar. A handle is grasped at its origin along its x-axis, with the
    fingers closing along its y-axis, so it needs a frame that points into the furniture
    and across the bar.

    :param world: The world `handle_link` is in.
    :param handle_link: The link of a handle of the kitchen.
    :return: A frame at the origin of `handle_link` that a gripper can grasp it by.
    """
    handle_frame = Body(name=PrefixedName(f"{handle_link.name.name}_grasp_frame"))
    link_T_frame = HomogeneousTransformationMatrix.from_point_rotation_matrix(
        rotation_matrix=RotationMatrix(
            data=[[-1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]],
            reference_frame=handle_link,
        ),
        reference_frame=handle_link,
    )
    with world.modify_world():
        world.add_kinematic_structure_entity(handle_frame)
        world.add_connection(
            FixedConnection(
                parent=handle_link,
                child=handle_frame,
                parent_T_connection_expression=link_T_frame,
            )
        )
    return handle_frame


@pytest.fixture
def kitchen_with_filled_drawer(
    pr2_world_copy: World, kitchen_world: World
) -> KitchenWithFilledDrawer:
    world = pr2_world_copy
    world.merge_world(deepcopy(kitchen_world))
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    drawer = world.get_body_by_name("sink_area_left_middle_drawer_main")
    cup = Cup(
        root=add_cylinder(
            world,
            name="cup",
            radius=0.04,
            height=0.07,
            parent_T_cylinder=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.1, y=0.2, z=-0.05, reference_frame=drawer
            ),
        )
    )
    bowl = Bowl(
        root=add_cylinder(
            world,
            name="bowl",
            radius=0.07,
            height=0.05,
            parent_T_cylinder=HomogeneousTransformationMatrix.from_xyz_rpy(
                x=0.1, y=-0.2, z=-0.05, reference_frame=drawer
            ),
        )
    )
    drawer_handle = Handle(
        root=add_handle_frame(
            world, world.get_body_by_name("sink_area_left_middle_drawer_handle")
        )
    )
    with world.modify_world():
        world.add_semantic_annotations([cup, bowl, drawer_handle])
    return KitchenWithFilledDrawer(
        world=world,
        robot=robot,
        context_extensions=robot_extensions(robot),
        drawer_handle=drawer_handle,
        bowl=bowl,
        cup=cup,
    )


def grasp_from_above(graspable: HasGraspCandidates) -> GraspCandidate:
    """
    :param graspable: The annotation of an object standing upright.
    :return: The grasp that comes down onto the origin of `graspable` along its z-axis.
    """
    return GraspCandidate(
        graspable,
        Pose(
            orientation=RotationMatrix.from_rpy(pitch=np.pi / 2).quaternion,
            reference_frame=graspable.root,
        ),
    )


# %% taking both objects out of the drawer and setting them down


def test_bowl_and_cup_are_moved_from_the_drawer_onto_the_kitchen_island(
    kitchen_with_filled_drawer: KitchenWithFilledDrawer,
):
    kitchen = kitchen_with_filled_drawer
    world, robot = kitchen.world, kitchen.robot
    world_T_bowl_goal = world.transform(
        Pose.from_xyz_rpy(x=0.2, z=0.05, reference_frame=kitchen.kitchen_island),
        world.root,
    )
    world_T_cup_goal = world.transform(
        Pose.from_xyz_rpy(
            x=0.15, y=0.25, z=0.07, reference_frame=kitchen.kitchen_island
        ),
        world.root,
    )
    in_front_of_the_closed_drawer = Pose.from_xyz_rpy(
        x=0.4, y=0.7, reference_frame=world.root
    )
    in_front_of_the_open_drawer = Pose.from_xyz_rpy(
        x=0.3, y=0.89, reference_frame=world.root
    )
    facing_the_kitchen_island = Pose.from_xyz_rpy(
        x=-0.3, y=1.85, yaw=np.pi, reference_frame=world.root
    )

    plan = Sequence(
        [
            NavigateAction(in_front_of_the_closed_drawer),
            OpenAction(kitchen.drawer_handle, robot.left_arm),
            ParkArmsAction(robot.all_arms),
            NavigateAction(in_front_of_the_open_drawer),
            Parallel(
                [
                    PickUpAction(grasp_from_above(kitchen.bowl), robot.left_arm),
                    PickUpAction(grasp_from_above(kitchen.cup), robot.right_arm),
                ]
            ),
            ParkArmsAction(robot.all_arms),
            NavigateAction(facing_the_kitchen_island),
            MoveTorsoAction(TorsoState.HIGH),
            Parallel(
                [
                    PlaceAction(kitchen.bowl, world_T_bowl_goal),
                    PlaceAction(kitchen.cup, world_T_cup_goal),
                ]
            ),
            ParkArmsAction(robot.all_arms),
        ]
    )
    run_plan(plan, kitchen.context_extensions)

    # A pick-up and a place each end within the position threshold of their goal.
    position_tolerance = 2 * MotionToleranceConfig().default_tcp_position_threshold
    for placed, world_T_goal in [
        (kitchen.bowl, world_T_bowl_goal),
        (kitchen.cup, world_T_cup_goal),
    ]:
        assert placed.root.parent_connection.parent is world.root
        np.testing.assert_allclose(
            placed.root.global_pose.position.to_np(),
            world_T_goal.position.to_np(),
            atol=position_tolerance,
        )
