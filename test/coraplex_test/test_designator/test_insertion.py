"""
Tests for :class:`~coraplex.robot_plans.actions.core.insertion.InsertAction`: what it
states about the world before and after it runs, where it releases the body it carries,
and that a plan can leave its target open for a query to settle.
"""

from __future__ import annotations

import math

import pytest
from typing_extensions import Dict, List, Tuple

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.exceptions import ApertureHasNoLandingRegion
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.insertion import (
    DEFAULT_MINIMUM_CONTAINMENT_RATIO,
    InsertAction,
)
from coraplex.robot_plans.actions.core.placing import PlaceAction
from coraplex.view_manager import ViewManager
from krrood.entity_query_language.backends import EntityQueryLanguageGenerativeBackend
from krrood.entity_query_language.factories import a, evaluate_condition, variable_from
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import InsideOf
from semantic_digital_twin.reasoning.robot_predicates import is_body_gripped
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.spatial_types.spatial_types import Point3, RotationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

from ..dataset.one_arm_robot import OneArmRobot
from ..dataset.posting_slot import PostedShape, PostingSlot

POSTED_BODY_SCALE = Scale(0.03, 0.03, 0.03)
"""
How large the body every test here posts through a slot is, in metres: small enough to
stand inside a slot's space behind it whole.
"""

FIRST_SLOT_STANDS_AT = Point3(0.6, 0.0, 0.5)
"""
Where the first slot's opening stands, in the world root frame.
"""

SLOT_SPACING = 0.2
"""
How far apart, along y, the slots of :func:`world_with_two_slots` stand.
"""

BODY_STARTS_AT = Point3(0.4, 0.0, 0.0)
"""
Where the posted body starts, in the world root frame: on neither slot's side of the
world, so a test that reads containment reads what it put there itself.
"""


@pytest.fixture
def world_with_two_slots() -> (
    Tuple[World, OneArmRobot, Body, Dict[PostedShape, PostingSlot]]
):
    """
    A world holding a one-armed robot, a loose body, and one slot per
    :class:`~..dataset.posting_slot.PostedShape`.
    """
    world = URDFParser.from_file(OneArmRobot.get_ros_file_path()).parse()
    robot = OneArmRobot.from_world(world)
    body = Body(
        name=PrefixedName("posted_body"),
        collision=ShapeCollection([Box(scale=POSTED_BODY_SCALE)]),
    )
    slots: Dict[PostedShape, PostingSlot] = {}
    with world.modify_world():
        world.add_connection(
            FixedConnection(
                parent=world.root,
                child=body,
                parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
                    float(BODY_STARTS_AT.x),
                    float(BODY_STARTS_AT.y),
                    float(BODY_STARTS_AT.z),
                ),
            )
        )
        for index, posted_shape in enumerate(PostedShape):
            slots[posted_shape] = PostingSlot.cut_into(
                world,
                posted_shape,
                Point3(
                    float(FIRST_SLOT_STANDS_AT.x),
                    float(FIRST_SLOT_STANDS_AT.y) + index * SLOT_SPACING,
                    float(FIRST_SLOT_STANDS_AT.z),
                ),
            )
    world.update_forward_kinematics()
    return world, robot, body, slots


def _stand_body_at(world: World, body: Body, position: Point3) -> None:
    """
    Move a loose body somewhere in the world root frame.

    :param world: The world holding the body.
    :param body: The body to move.
    :param position: Where its own origin is to stand.
    """
    world.move_branch_to(
        body,
        HomogeneousTransformationMatrix.from_xyz_rpy(
            float(position.x),
            float(position.y),
            float(position.z),
            reference_frame=world.root,
        ),
    )


# %% what the action states about the world


def test_the_pre_condition_states_that_the_arm_holds_the_body(world_with_two_slots):
    """
    Before an insertion runs, what has to hold is that the body is in the gripper of the
    arm that inserts it -- stated as a query the world answers, not checked in Python.
    """
    world, robot, body, slots = world_with_two_slots
    action = InsertAction(body, slots[PostedShape.SQUARE], Arms.LEFT)

    pre_condition = InsertAction.pre_condition(
        action.bound_variables, Context(world, robot), action.designator_parameter
    )

    # A symbolic call binds the function the decorator wrapped, not the wrapper the
    # module exports under the same name.
    assert pre_condition._type_ is is_body_gripped.__wrapped__
    assert pre_condition._kwargs_["body"]._domain_ is body
    assert pre_condition._kwargs_["threshold"] == action.grasp_detection_threshold

    gripper = pre_condition._kwargs_["gripper"]
    assert gripper._type_ is ViewManager.get_end_effector_view.__wrapped__
    assert list(gripper._kwargs_["arm"]._domain_) == [action.arm]
    assert gripper._kwargs_["robot_view"] is robot


def test_the_post_condition_states_that_the_body_is_behind_the_opening(
    world_with_two_slots,
):
    """
    After an insertion runs, what has to hold is that the body stands in the space
    behind the very slot it was inserted through -- the same containment reading a
    detector makes of an insertion.
    """
    world, robot, body, slots = world_with_two_slots
    slot = slots[PostedShape.SQUARE]
    action = InsertAction(body, slot, Arms.LEFT)

    post_condition = InsertAction.post_condition(
        action.bound_variables, Context(world, robot), action.designator_parameter
    )

    assert post_condition._type_ is InsideOf
    assert post_condition._kwargs_["other"] is slot.landing_region
    assert (
        post_condition._kwargs_["minimum_containment_ratio"]
        == DEFAULT_MINIMUM_CONTAINMENT_RATIO
    )


def test_the_post_condition_holds_only_once_the_body_is_behind_the_opening(
    world_with_two_slots,
):
    """
    The statement is answered from the world rather than from what the action did: it is
    false while the body rests where it started and true once it stands in the slot's
    own space behind it.
    """
    world, robot, body, slots = world_with_two_slots
    slot = slots[PostedShape.SQUARE]
    action = InsertAction(body, slot, Arms.LEFT)
    post_condition = InsertAction.post_condition(
        action.bound_variables, Context(world, robot), action.designator_parameter
    )

    assert evaluate_condition(post_condition) is False

    _stand_body_at(world, body, slot.landing_region.global_transform.to_position())

    assert evaluate_condition(post_condition) is True


def test_a_slot_with_no_space_behind_it_cannot_say_whether_a_body_went_through(
    world_with_two_slots,
):
    world, robot, body, slots = world_with_two_slots
    slot = slots[PostedShape.SQUARE]
    slot.landing_region = None
    action = InsertAction(body, slot, Arms.LEFT)

    with pytest.raises(ApertureHasNoLandingRegion):
        InsertAction.post_condition(
            action.bound_variables, Context(world, robot), action.designator_parameter
        )


# %% where the body is let go of


def test_the_body_is_released_above_the_opening_along_the_slots_own_axis(
    world_with_two_slots,
):
    """
    The release pose is stated in the slot's own frame, so it is lined up with the
    opening however the opening is turned, and stands :attr:`hover_height` along its
    axis.
    """
    world, robot, body, slots = world_with_two_slots
    slot = slots[PostedShape.ROUND]
    action = InsertAction(body, slot, Arms.LEFT, hover_height=0.05)

    insertion_pose = action.insertion_pose

    assert insertion_pose.reference_frame is slot.root
    assert insertion_pose.to_position().to_np()[:3].tolist() == [0.0, 0.0, 0.05]


def test_a_body_that_only_fits_turned_is_released_turned_that_way(
    world_with_two_slots,
):
    """
    A body that only goes through an opening turned some way -- a coin onto its edge for
    a slot -- is released turned that way by stating that turn, rather than by an
    insertion of its own.
    """
    world, robot, body, slots = world_with_two_slots
    slot = slots[PostedShape.ROUND]
    onto_its_edge = RotationMatrix.from_rpy(
        pitch=math.pi / 2, reference_frame=slot.root
    )
    action = InsertAction(
        body, slot, Arms.LEFT, hover_height=0.05, target_R_body=onto_its_edge
    )

    insertion_pose = action.insertion_pose

    assert insertion_pose.to_position().to_np()[:3].tolist() == [0.0, 0.0, 0.05]
    assert insertion_pose.to_rotation_matrix().to_np().flatten().tolist() == (
        pytest.approx(onto_its_edge.to_np().flatten().tolist())
    )


def test_the_plan_carries_the_body_to_that_release_pose_and_lets_it_go(
    world_with_two_slots,
):
    """
    An insertion is a place at a pose the slot itself settles, so the carrying, the
    descent, the release and the retreat are the ones a place already makes.
    """
    world, robot, body, slots = world_with_two_slots
    slot = slots[PostedShape.ROUND]
    context = Context(world, robot, evaluate_conditions=False)
    action = InsertAction(
        body, slot, Arms.LEFT, hover_height=0.05, release_opening_velocity=0.07
    )

    places = _places_of(action, context)

    assert [type(place) for place in places] == [PlaceAction]
    [place] = places
    assert place.object_designator is body
    assert place.arm is Arms.LEFT
    assert place.release_opening_velocity == 0.07
    assert place.target_location.to_np().tolist() == (
        world.transform(action.insertion_pose, world.root).to_np().tolist()
    )


def _places_of(action: InsertAction, context: Context) -> List[PlaceAction]:
    """
    Every place the action's own plan is built from.

    :param action: The action to build the plan of.
    :param context: The context the plan is built in.
    """
    plan = sequential([action], context).plan
    action.expand()
    return [
        node.designator
        for node in plan.nodes
        if isinstance(getattr(node, "designator", None), PlaceAction)
    ]


# %% leaving the slot for a query to settle


def test_an_insertion_whose_slot_is_left_open_is_a_match_that_enumerates(
    world_with_two_slots,
):
    """
    ``a(InsertAction)(...)`` with its target left to a query reads as a match, and the
    generative backend answers it with one insertion per slot and arm it could mean.
    """
    world, robot, body, slots = world_with_two_slots

    query = a(InsertAction)(
        object_designator=body,
        target=variable_from(list(slots.values())),
        arm=...,
    )

    assert isinstance(query, Match)
    candidates = list(EntityQueryLanguageGenerativeBackend().evaluate(query))
    assert len(candidates) == len(slots) * len(Arms)
    assert {candidate.target for candidate in candidates} == set(slots.values())
    assert all(candidate.object_designator is body for candidate in candidates)
