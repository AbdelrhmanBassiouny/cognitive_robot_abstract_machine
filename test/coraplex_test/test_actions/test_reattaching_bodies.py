"""
Tests for what holds a body an action moves under a new parent, see
:class:`~coraplex.robot_plans.mixins.ReattachesBodies`.
"""

from typing_extensions import List

from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from cramph.composites import Sequence
from cramph.node import StatechartNode
from cramph.world_modification_nodes import MoveBranch
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.spatial_types.spatial_types import Pose

from ..conftest import motion_nodes_in_physics_of, motion_nodes_of

# %% reading the expanded plan


def branch_moves_of(nodes: List[StatechartNode]) -> List[MoveBranch]:
    """
    :return: The nodes among `nodes` that move a body under a new parent.
    """
    return [node for node in nodes if isinstance(node, MoveBranch)]


# %% what holds a picked object


def test_a_kinematically_simulated_pick_is_held_by_the_world(pr2_apartment_context):
    """
    Nothing in a world moved kinematically holds an object, so the object is put under
    the gripper for it to be held at all.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    pick_up = PickUpAction(grasp=milk.grasp_candidates()[0], arm=view.right_arm)

    [attaching] = branch_moves_of(motion_nodes_of(pick_up, extensions))

    assert attaching.body is milk.root
    assert attaching.new_parent is view.right_arm.end_effector.tool_frame


def test_a_physically_simulated_pick_is_held_by_its_own_grip(pr2_apartment_context):
    """
    The pads hold the object in physics, so putting it under the gripper as well would
    hold it whether or not the grasp did.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    pick_up = PickUpAction(grasp=milk.grasp_candidates()[0], arm=view.right_arm)

    assert branch_moves_of(motion_nodes_in_physics_of(pick_up, extensions)) == []


def test_a_physically_simulated_place_is_released_by_its_own_grip(
    pr2_apartment_context,
):
    """
    Releasing is the same move the other way, and in physics the pads opening is what
    lets the object go, so the model is left alone here too.
    """
    world, view, extensions = pr2_apartment_context
    milk = world.get_semantic_annotations_by_type(Milk)[0]
    plan = Sequence(
        nodes=[
            PickUpAction(grasp=milk.grasp_candidates()[0], arm=view.right_arm),
            PlaceAction(
                object_designator=milk,
                target_location=Pose.from_xyz_rpy(
                    1, 1, 0.8, reference_frame=world.root
                ),
            ),
        ]
    )

    assert branch_moves_of(motion_nodes_in_physics_of(plan, extensions)) == []
