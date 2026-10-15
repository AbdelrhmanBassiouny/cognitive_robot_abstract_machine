"""
Tests that a robot driving with objects in its grippers keeps each of them upright.
"""

from __future__ import annotations

import numpy as np
import pytest

from coraplex.plans.context_extensions import MotionToleranceConfig
from coraplex.robot_plans.actions.composite.carrying import CarryAction
from coraplex.robot_plans.actions.composite.facing import FaceAndLookAtAction
from coraplex.robot_plans.actions.composite.transporting import MoveAndPlaceAction
from coraplex.robot_plans.actions.core.navigation import (
    FaceAtAction,
    LookAtAction,
    NavigateAction,
)
from coraplex.robot_plans.actions.core.placing import PlaceAction
from cramph.composites import Sequence
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Cup
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Cylinder
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from .test_both_arms_handling_objects_at_once import add_cup, pick_up_from_above
from ...plan_running import expand, robot_extensions, run_plan

# %% a PR2 and the cups it carries


@pytest.fixture
def pr2(pr2_world_copy: World) -> PR2:
    return pr2_world_copy.get_semantic_annotations_by_type(PR2)[0]


def tilt_from_upright(body: Body) -> float:
    """
    :param body: The body to measure.
    :return: The angle in radians between the z-axis of `body` and the world's z-axis.
    """
    up_in_world = body.global_pose.to_np()[:3, 2]
    return float(np.arccos(np.clip(up_in_world[2], -1.0, 1.0)))


def cup_held_tilted(pr2: PR2) -> Cup:
    """
    :param pr2: The robot that holds the cup.
    :return: A cup fixed below the tool frame of the left gripper of `pr2`, its z-axis
        tilted away from the world's z-axis.
    """
    world = pr2._world
    tool_frame = pr2.left_arm.end_effector.tool_frame
    shapes = ShapeCollection([Cylinder(width=0.08, height=0.07)])
    body = Body(name=PrefixedName("held_cup"), collision=shapes, visual=shapes)
    cup = Cup(root=body)
    with world.modify_world():
        world.add_kinematic_structure_entity(body)
        world.add_connection(
            FixedConnection(
                parent=tool_frame,
                child=body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    roll=0.4, pitch=0.3, reference_frame=tool_frame
                ),
            )
        )
        world.add_semantic_annotation(cup)
    return cup


def drive_ahead(pr2: PR2) -> NavigateAction:
    """
    :param pr2: The robot that drives.
    :return: The drive moving `pr2` a short way forward.
    """
    return NavigateAction(Pose.from_xyz_rpy(x=0.3, reference_frame=pr2.root))


# %% held objects end upright


def test_a_tilted_cup_in_a_gripper_ends_upright(pr2: PR2):
    cup = cup_held_tilted(pr2)
    carry = CarryAction(drive_ahead(pr2))

    run_plan(carry, robot_extensions(pr2))

    assert tilt_from_upright(cup.root) <= carry.upright_threshold


def test_a_cup_picked_up_earlier_in_the_plan_ends_upright(pr2: PR2):
    world = pr2._world
    cup = add_cup(
        world,
        "tilted_cup",
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.7, y=0.3, z=0.8, roll=0.3, reference_frame=world.root
        ),
    )
    carry = CarryAction(drive_ahead(pr2))

    run_plan(
        Sequence([pick_up_from_above(cup, pr2.left_arm), carry]),
        robot_extensions(pr2),
    )

    # The cup is held with the orientation error the gripper reached its grasp with.
    assert (
        tilt_from_upright(cup.root)
        <= carry.upright_threshold + MotionToleranceConfig().tool_orientation_threshold
    )


# %% nothing held leaves only the drive


def test_a_robot_holding_nothing_only_drives(pr2: PR2):
    carry = CarryAction(drive_ahead(pr2))

    expand(carry, robot_extensions(pr2))

    assert carry.action_body is carry.navigate


def test_a_cup_put_down_earlier_in_the_plan_is_not_carried(pr2: PR2):
    world = pr2._world
    cup = add_cup(
        world,
        "cup",
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.7, y=0.3, z=0.8, reference_frame=world.root
        ),
    )
    carry = CarryAction(drive_ahead(pr2))

    expand(
        Sequence(
            [
                pick_up_from_above(cup, pr2.left_arm),
                PlaceAction(cup, Pose.from_xyz_rpy(y=0.1, reference_frame=cup.root)),
                carry,
            ]
        ),
        robot_extensions(pr2),
    )

    assert carry.action_body is carry.navigate


# %% a placing drives with the object upright


def test_a_placing_carries_its_object_to_where_it_stands(pr2: PR2):
    cup = cup_held_tilted(pr2)
    target = Pose.from_xyz_rpy(x=0.8, z=0.8, reference_frame=pr2.root)
    move_and_place = MoveAndPlaceAction(
        navigate=drive_ahead(pr2),
        face_and_look_at=FaceAndLookAtAction(
            face_at=FaceAtAction(target), look_at=LookAtAction(target)
        ),
        place=PlaceAction(cup, target),
    )

    expand(move_and_place, robot_extensions(pr2))

    carry = move_and_place.action_body.nodes[0]
    assert isinstance(carry, CarryAction)
    assert carry.navigate is move_and_place.navigate
