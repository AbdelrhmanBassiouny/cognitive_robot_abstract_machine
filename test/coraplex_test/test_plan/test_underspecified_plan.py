"""
A whole plan read as underspecified: its actions are stated rather than grounded, and
each of them hands over descriptions of things nothing has answered yet.
"""

import pytest

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.language import SequentialNode
from coraplex.plans.factories import sequential
from coraplex.plans.underspecified import UnderspecifiedPlan, underspecified
from coraplex.robot_plans.actions.core.insertion import InsertAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

from ..dataset.posting_slot import PostedShape, PostingSlot

# %% the plan the figure states


@pytest.fixture
def posted_body() -> Match[Body]:
    """
    The one description of the body both actions are about: what is picked up is what is
    posted.
    """
    return a(Body)()


@pytest.fixture
def grasp() -> Match[GraspDescription]:
    """
    How the body is held, left entirely open.
    """
    return a(GraspDescription)(approach_direction=..., vertical_alignment=...)


@pytest.fixture
def slot() -> Match[PostingSlot]:
    """
    The opening the body goes through, with the shape it takes left open.
    """
    return a(PostingSlot)(posted_shape=...)


@pytest.fixture
def pick_up(posted_body: Match[Body], grasp: Match[GraspDescription]) -> Match:
    return a(PickUpAction)(
        arm=Arms.LEFT, object_designator=posted_body, grasp_description=grasp
    )


@pytest.fixture
def insertion(posted_body: Match[Body], slot: Match[PostingSlot]) -> Match:
    return a(InsertAction)(object_designator=posted_body, target=slot, arm=Arms.LEFT)


@pytest.fixture
def root(pick_up: Match, insertion: Match) -> SequentialNode:
    return sequential([pick_up, insertion])


@pytest.fixture
def plan(root: SequentialNode) -> UnderspecifiedPlan:
    return underspecified(root)


# %% what such a plan says about itself

# A match compares symbolically, so the descriptions below are told apart by identity
# rather than by ``==``, which would build a comparator and read as true whatever it was
# given.


def test_a_plan_read_as_underspecified_runs_the_plan_it_was_given(
    plan: UnderspecifiedPlan, root: SequentialNode
):
    assert plan.root is root


def test_it_states_its_actions_in_the_order_they_run(
    plan: UnderspecifiedPlan, pick_up: Match, insertion: Match
):
    first, second = plan.actions
    assert first is pick_up
    assert second is insertion


def test_it_leaves_open_every_description_its_actions_hand_over(
    plan: UnderspecifiedPlan,
    posted_body: Match[Body],
    grasp: Match[GraspDescription],
    slot: Match[PostingSlot],
):
    body_description, grasp_description, slot_description = plan.open_descriptions
    assert body_description is posted_body
    assert grasp_description is grasp
    assert slot_description is slot


def test_a_description_two_actions_share_is_left_open_once(
    plan: UnderspecifiedPlan, posted_body: Match[Body]
):
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
    posted_shape = a(PostedShape)()
    slot = a(PostingSlot)(posted_shape=posted_shape)
    body = a(Body)()

    plan = underspecified(
        sequential(
            [a(InsertAction)(object_designator=body, target=slot, arm=Arms.LEFT)]
        )
    )

    body_description, shape_description, slot_description = plan.open_descriptions
    assert body_description is body
    assert shape_description is posted_shape
    assert slot_description is slot


def test_a_plan_whose_actions_hand_nothing_over_leaves_nothing_open():
    body = Body(name=PrefixedName("posted_body"))

    plan = underspecified(
        sequential([a(PickUpAction)(object_designator=body, arm=Arms.LEFT)])
    )

    assert plan.open_descriptions == []
