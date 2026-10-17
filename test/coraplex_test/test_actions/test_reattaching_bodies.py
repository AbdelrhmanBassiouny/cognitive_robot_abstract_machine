"""
Tests for what holds a body an action moves under a new parent, see
:class:`~coraplex.robot_plans.mixins.ReattachesBodies`.
"""

from typing_extensions import List

from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from coraplex.robot_plans.actions.core.placing import PlaceAction
from cramph.composites import Sequence
from cramph.context import ContextExtension
from cramph.data_types import LifeCycleValues
from cramph.node import StatechartNode
from cramph.world_modification_nodes import MoveBranch
from semantic_digital_twin.collision_checking.collision_rules import (
    AllowCollisionForEndEffector,
)
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.semantic_annotations.semantic_annotations import Milk
from semantic_digital_twin.spatial_types.spatial_types import Pose

from ..conftest import motion_nodes_in_physics_of, motion_nodes_of
from ...plan_running import run_plan, simulated_executor, statechart_of
from .test_both_arms_handling_objects_at_once import CupForEachArm, cup_for_each_arm

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


# %% the gripper while its object is reattached


def allowances_while_reattaching(
    plan: StatechartNode,
    extensions: List[ContextExtension],
    end_effector: EndEffector,
    max_ticks: int = 5000,
) -> List[bool]:
    """
    Run `plan` simulated, tick by tick, until it succeeded.

    :param plan: The plan to run, which moves one body under a new parent.
    :param extensions: The context extensions of the plan.
    :param end_effector: The end effector touching the moved body.
    :param max_ticks: How many ticks `plan` is given to succeed.
    :return: For every tick after which the body was still being moved, whether
        `end_effector` was allowed to touch its surroundings, which is what the
        collision check of the next tick reads.
    """
    executor = simulated_executor(extensions)
    executor.compile(statechart_of(executor, plan))
    [reattaching] = branch_moves_of(plan.descendants)
    allowances = []
    for _ in range(max_ticks):
        if plan.life_cycle_state == LifeCycleValues.SUCCEEDED:
            break
        executor.tick()
        if reattaching.life_cycle_state == LifeCycleValues.RUNNING:
            allowances.append(
                any(
                    isinstance(rule, AllowCollisionForEndEffector)
                    and rule.end_effector is end_effector
                    for rule in executor.world.collision_manager.temporary_rules
                )
            )
    assert plan.life_cycle_state == LifeCycleValues.SUCCEEDED
    return allowances


def test_a_gripper_may_touch_its_surroundings_while_its_grasp_is_reattached(
    cup_for_each_arm: CupForEachArm,
):
    """
    The gripper is closed around the object, touching whatever the object rests on, from
    closing to lifting, so the moment the object is put under it is no exception.
    """
    pick_up = cup_for_each_arm.pick_ups[0]

    allowances = allowances_while_reattaching(
        pick_up, cup_for_each_arm.context_extensions, pick_up.arm.end_effector
    )

    assert allowances == [True]


def test_a_gripper_may_touch_its_surroundings_while_its_release_is_reattached(
    cup_for_each_arm: CupForEachArm,
):
    """
    The gripper still surrounds the object it has just let go of when the object is put
    back under the world.
    """
    pick_up = cup_for_each_arm.pick_ups[0]
    run_plan(pick_up, cup_for_each_arm.context_extensions)
    place = cup_for_each_arm.places()[0]

    allowances = allowances_while_reattaching(
        place, cup_for_each_arm.context_extensions, pick_up.arm.end_effector
    )

    assert allowances == [True]
