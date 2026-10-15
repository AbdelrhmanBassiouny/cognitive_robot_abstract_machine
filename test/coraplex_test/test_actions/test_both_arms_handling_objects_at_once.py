"""
Tests that a gripper stays where it reached while it closes or opens, although the other
arm moves the base both arms share at the same time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from coraplex.plans.context_extensions import MotionToleranceConfig
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from cramph.composites import Parallel, Sequence
from cramph.context import ContextExtension
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.grasping.grasp_candidates import GraspCandidate
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.robots.robot_parts import Arm
from semantic_digital_twin.semantic_annotations.semantic_annotations import Cup
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

from ..conftest import grasp_point_of
from ...plan_running import robot_extensions, run_plan

# %% a robot with a cup in reach of each arm


@dataclass
class CupForEachArm:
    """
    A PR2 whose base moves with its arms, with one cup for each arm to pick up.
    """

    world: World
    """
    The world holding the robot and the cups.
    """

    context_extensions: list[ContextExtension]
    """
    The context extensions the plans of the robot read.
    """

    pick_ups: list[PickUpAction]
    """
    The pick-up of each cup, the nearer cup with the left arm and the farther one with
    the right arm.
    """

    def places(self) -> list[PlaceAction]:
        """
        :return: The actions that set each cup down to the side of where it is now, the
            first far away and the second close by, so that one gripper opens while the
            other arm is still on its way.
        """
        return [
            PlaceAction(
                object_designator=pick_up.grasp.graspable,
                target_location=self.world.transform(
                    Pose.from_xyz_rpy(
                        y=sideways_distance,
                        reference_frame=pick_up.grasp.graspable.root,
                    ),
                    self.world.root,
                ),
            )
            for pick_up, sideways_distance in zip(self.pick_ups, [0.3, -0.02])
        ]


def add_cup(
    world: World, name: str, world_T_cup: HomogeneousTransformationMatrix
) -> Cup:
    """
    :param world: The world the cup is added to.
    :param name: The name of the body of the cup.
    :param world_T_cup: Where the cup hovers.
    :return: The annotation of a cup fixed to the root of `world`.
    """
    shapes = ShapeCollection([Cylinder(width=0.08, height=0.07)])
    body = Body(name=PrefixedName(name), collision=shapes, visual=shapes)
    cup = Cup(root=body)
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=body,
                parent_T_connection_expression=world_T_cup,
            )
        )
        world.add_semantic_annotation(cup)
    return cup


def pick_up_from_above(cup: Cup, arm: Arm) -> PickUpAction:
    """
    :param cup: A cup standing upright.
    :param arm: The arm that picks it up.
    :return: The pick-up of `cup` that comes down onto its origin along its z-axis.
    """
    grasp = GraspCandidate(
        cup,
        Pose(
            orientation=RotationMatrix.from_rpy(pitch=np.pi / 2).quaternion,
            reference_frame=cup.root,
        ),
    )
    return PickUpAction(grasp=grasp, arm=arm)


@pytest.fixture
def cup_for_each_arm(pr2_world_copy: World) -> CupForEachArm:
    world = pr2_world_copy
    robot = world.get_semantic_annotations_by_type(PR2)[0]
    robot.mobile_base.full_body_controlled = True
    # The cups are out of reach and at different distances, so the base has to move
    # and one arm is done before the other.
    near_cup = add_cup(
        world,
        "near_cup",
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.9, y=0.2, z=0.6, reference_frame=world.root
        ),
    )
    far_cup = add_cup(
        world,
        "far_cup",
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=1.2, y=-0.2, z=0.6, reference_frame=world.root
        ),
    )
    return CupForEachArm(
        world=world,
        context_extensions=robot_extensions(robot),
        pick_ups=[
            pick_up_from_above(near_cup, robot.left_arm),
            pick_up_from_above(far_cup, robot.right_arm),
        ],
    )


# %% a gripper stays where it reached while it closes or opens


def test_a_gripper_closes_at_its_grasp_although_the_other_arm_is_moving(
    cup_for_each_arm: CupForEachArm,
):
    run_plan(
        Parallel(nodes=cup_for_each_arm.pick_ups), cup_for_each_arm.context_extensions
    )

    world = cup_for_each_arm.world
    for pick_up in cup_for_each_arm.pick_ups:
        # A goal puts the point the fingers meet at on the grasp, not the tool frame.
        np.testing.assert_allclose(
            grasp_point_of(pick_up.arm),
            world.transform(pick_up.grasp.grasp_pose, world.root)
            .position.to_np()
            .flatten()[:3],
            atol=MotionToleranceConfig().default_tcp_position_threshold,
        )


def test_a_gripper_opens_at_its_place_target_although_the_other_arm_is_moving(
    cup_for_each_arm: CupForEachArm,
):
    # One after the other, so that both cups sit in their grippers at their grasps.
    run_plan(
        Sequence(nodes=cup_for_each_arm.pick_ups), cup_for_each_arm.context_extensions
    )
    places = cup_for_each_arm.places()

    run_plan(Parallel(nodes=places), cup_for_each_arm.context_extensions)

    for place in places:
        np.testing.assert_allclose(
            place.object_designator.root.global_pose.position.to_np()[:3],
            place.target_location.position.to_np()[:3],
            atol=2 * MotionToleranceConfig().default_tcp_position_threshold,
        )
