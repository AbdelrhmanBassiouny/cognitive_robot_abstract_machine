"""
A plan read for what it leaves open: its actions are stated rather than grounded, and
each of them hands over descriptions of things nothing has answered yet.
"""

import pytest

from coraplex.datastructures.enums import Arms, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.language import SequentialNode
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from krrood.entity_query_language.backends import (
    BackendChoice,
    EntityQueryLanguageBackend,
    EntityQueryLanguageGenerativeBackend,
)
from krrood.entity_query_language.factories import a, an
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from ..dataset.posting_slot import PostedShape, PostingSlot

# %% what a plan says about itself

# A match compares symbolically, so the descriptions below are told apart by identity
# rather than by ``==``, which would build a comparator and read as true whatever it was
# given.


def test_a_node_standing_for_a_statement_states_that_action_and_a_node_ordering_them_states_none():
    action = a(PickUpAction)(object_designator=a(Body), arm=Arms.LEFT)

    plan = sequential([action])

    (stated,) = plan.descendants[0].underspecified_actions
    assert stated is action
    assert plan.underspecified_actions == []


def test_it_leaves_open_every_description_its_actions_hand_over():
    posted_body = a(Body)
    grasp = a(GraspDescription)(approach_direction=..., vertical_alignment=...)
    slot = a(PostingSlot)(posted_shape=...)

    plan = sequential(
        [
            a(PickUpAction)(
                arm=Arms.LEFT, object_designator=posted_body, grasp_description=grasp
            ),
            an(InsertionAction)(
                object_designator=posted_body, target=slot, arm=Arms.LEFT
            ),
        ]
    )

    body_description, grasp_description, slot_description = plan.open_descriptions
    assert body_description is posted_body
    assert grasp_description is grasp
    assert slot_description is slot


def test_a_description_two_actions_share_is_left_open_once():
    posted_body = a(Body)

    plan = sequential(
        [
            a(PickUpAction)(arm=Arms.LEFT, object_designator=posted_body),
            an(InsertionAction)(
                object_designator=posted_body,
                target=a(PostingSlot)(posted_shape=...),
                arm=Arms.LEFT,
            ),
        ]
    )

    handed_over = [
        description
        for description in plan.open_descriptions
        if description is posted_body
    ]
    assert len(handed_over) == 1


def test_a_description_nested_in_another_is_left_open_before_the_one_nesting_it():
    """
    An outer description cannot be answered before the descriptions it is stated in
    terms of, so it is the innermost that comes first.
    """
    posted_shape = a(PostedShape)
    slot = a(PostingSlot)(posted_shape=posted_shape)
    body = a(Body)

    plan = sequential(
        [an(InsertionAction)(object_designator=body, target=slot, arm=Arms.LEFT)]
    )

    body_description, shape_description, slot_description = plan.open_descriptions
    assert body_description is body
    assert shape_description is posted_shape
    assert slot_description is slot


def test_a_plan_whose_actions_hand_nothing_over_leaves_nothing_open():
    body = Body(name=PrefixedName("posted_body"))

    plan = sequential([a(PickUpAction)(object_designator=body, arm=Arms.LEFT)])

    assert plan.open_descriptions == []


# %% grounding what a plan leaves open


@pytest.fixture
def world_with_two_slots() -> World:
    """
    A world holding one body to post and a slot of each shape to post it through.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName("posted_body")))
        PostingSlot.cut_into(world, PostedShape.ROUND, Point3(0.0, 0.0, 1.0))
        PostingSlot.cut_into(world, PostedShape.SQUARE, Point3(0.2, 0.0, 1.0))
    return world


@pytest.fixture
def backend() -> BackendChoice:
    """
    A choice that searches what a statement ranges over and generates what nothing has
    stated.
    """
    return BackendChoice(
        backends=[EntityQueryLanguageBackend(), EntityQueryLanguageGenerativeBackend()]
    )


def posting(body: Body, slot: Match[PostingSlot]) -> SequentialNode:
    """
    :param body: The body to pick up and post.
    :param slot: The slot to post it through.
    :return: A plan that picks the body up and posts it through the slot.
    """
    return sequential(
        [
            a(PickUpAction)(
                arm=Arms.LEFT,
                object_designator=body,
                grasp_description=a(GraspDescription)(
                    approach_direction=...,
                    vertical_alignment=VerticalAlignment.TOP,
                    end_effector=None,
                ),
            ),
            an(InsertionAction)(object_designator=body, target=slot, arm=Arms.LEFT),
        ]
    )


def test_each_stated_action_is_grounded_with_what_answers_what_it_leaves_open(
    world_with_two_slots: World, backend: BackendChoice
):
    body = world_with_two_slots.get_kinematic_structure_entity_by_name("posted_body")
    slots = world_with_two_slots.get_semantic_annotations_by_type(PostingSlot)
    plan = posting(body, a(PostingSlot)(posted_shape=PostedShape.SQUARE).from_(slots))

    [picking_up, posting_it] = next(plan.grounded_by(backend))

    assert isinstance(picking_up, PickUpAction)
    assert isinstance(posting_it, InsertionAction)
    assert picking_up.grasp_description.vertical_alignment is VerticalAlignment.TOP
    assert posting_it.target.posted_shape is PostedShape.SQUARE


def test_a_description_two_actions_hand_over_is_answered_once_for_both(
    world_with_two_slots: World, backend: BackendChoice
):
    """
    Two actions stating the same description mean the one thing, so the body posted is
    the body picked up rather than a second answer to the same question.
    """
    bodies = world_with_two_slots.kinematic_structure_entities
    slots = world_with_two_slots.get_semantic_annotations_by_type(PostingSlot)
    described = a(Body)().from_(bodies)
    plan = posting(
        described, a(PostingSlot)(posted_shape=PostedShape.SQUARE).from_(slots)
    )

    [picking_up, posting_it] = next(plan.grounded_by(backend))

    assert posting_it.object_designator is picking_up.object_designator


def test_it_is_grounded_once_for_every_way_what_it_leaves_open_is_answered(
    world_with_two_slots: World, backend: BackendChoice
):
    body = world_with_two_slots.get_kinematic_structure_entity_by_name("posted_body")
    slots = world_with_two_slots.get_semantic_annotations_by_type(PostingSlot)
    plan = sequential(
        [
            an(InsertionAction)(
                object_designator=body,
                target=a(PostingSlot)().from_(slots),
                arm=Arms.LEFT,
            )
        ]
    )

    grounded = list(plan.grounded_by(backend))

    assert [actions[0].target.posted_shape for actions in grounded] == [
        PostedShape.ROUND,
        PostedShape.SQUARE,
    ]


def test_a_plan_whose_actions_hand_nothing_over_is_grounded_as_it_stands(
    world_with_two_slots: World, backend: BackendChoice
):
    body = world_with_two_slots.get_kinematic_structure_entity_by_name("posted_body")
    [slot] = [
        held
        for held in world_with_two_slots.get_semantic_annotations_by_type(PostingSlot)
        if held.posted_shape is PostedShape.SQUARE
    ]
    plan = sequential(
        [an(InsertionAction)(object_designator=body, target=slot, arm=Arms.LEFT)]
    )

    [(posting_it,)] = [tuple(actions) for actions in plan.grounded_by(backend)]

    assert posting_it.target is slot
