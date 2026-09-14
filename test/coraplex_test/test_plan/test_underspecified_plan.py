"""
A plan read for what it leaves open: its actions are stated rather than grounded, and
each of them hands over descriptions of things nothing has answered yet.
"""

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from krrood.entity_query_language.factories import a, an
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
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
