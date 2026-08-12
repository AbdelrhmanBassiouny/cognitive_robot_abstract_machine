from copy import deepcopy

import pytest
from sqlalchemy import select

import experiments.orm.ormatic_interface as ormatic_interface  # type: ignore
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from krrood.ormatic.data_access_objects.helper import to_dao

from experiments.montessori.sorting_results import (
    InsertionOutcome,
    ShapeInsertionResult,
    SortingIterationResult,
)
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.spatial_types.spatial_types import Pose


@pytest.fixture
def three_action_plan(pr2_apartment_world):
    """
    A plan with three sequential actions, mirroring
    ``test_coraplex_test/test_orm/test_ormatic_designator.py``'s own ``simple_plan``
    fixture, so persisting it exercises the same multi-node tree that
    :class:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction`
    expands into (park arms, navigate, pick up, place, park arms again) without
    depending on a real grasp/placement resolving in simulation.
    """
    world = deepcopy(pr2_apartment_world)
    pr2 = world.get_semantic_annotations_by_type(PR2)[0]
    context = Context(world, pr2)

    return sequential(
        [
            NavigateAction(
                Pose.from_xyz_quaternion(
                    1.6, 1.9, 0, 0, 0, 0, 1, reference_frame=world.root
                ),
                True,
            ),
            MoveTorsoAction(TorsoState.HIGH),
            ParkArmsAction(Arms.BOTH),
        ],
        context=context,
    ).plan


def test_shape_insertion_result_persists_the_entire_plan_not_just_one_node(
    three_action_plan, experiments_testing_session
):
    """
    ``ShapeInsertionResult.plan`` must carry the entire realized plan tree an
    insertion attempt expanded into, not just its own top-level action node, so
    ``to_dao`` persists every sub-action alongside it rather than a single row.
    """
    with simulated_robot:
        three_action_plan.perform()

    iteration_result = SortingIterationResult(
        iteration=1,
        shape_results=[
            ShapeInsertionResult(
                shape_key="cube",
                outcome=InsertionOutcome.FELL_THROUGH,
                plan=three_action_plan,
            )
        ],
    )

    experiments_testing_session.add(to_dao(iteration_result))
    experiments_testing_session.commit()

    action_nodes = experiments_testing_session.scalars(
        select(ormatic_interface.ActionNodeDAO)
    ).all()
    assert len(action_nodes) == 3
