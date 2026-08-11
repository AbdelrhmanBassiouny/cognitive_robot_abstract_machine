"""
Integration test proving MontessoriWorld.spawn_robot is genuinely generic over the
robot class, not just tuned for HSRB: spawns a real PR2 (not the synthetic
test-double in test/experiments_test/dataset/synthetic_wheeled_arm_robot.py) and runs
a real InsertMontessoriShapeAction through it.
"""

import pytest

import experiments.orm.ormatic_interface  # type: ignore
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import execute_single
from krrood.entity_query_language.backends import ProbabilisticBackend

from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import MontessoriWorld, robot_installed
from semantic_digital_twin.robots.pr2 import PR2


@pytest.fixture
def montessori_with_pr2():
    if not robot_installed(PR2):
        pytest.skip("iai_pr2_description is not installed")

    montessori = MontessoriWorld()
    montessori.spawn_robot(PR2)
    montessori.world.update_forward_kinematics()
    return montessori


def shape_with_category(montessori: MontessoriWorld, category: str) -> MontessoriShape:
    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == category
    ]
    return shape


def test_spawn_robot_spawns_a_pr2(montessori_with_pr2):
    montessori = montessori_with_pr2

    assert isinstance(montessori.robot, PR2)


def test_insert_montessori_shape_action_moves_the_shape_to_its_matching_hole_with_pr2(
    montessori_with_pr2,
):
    montessori = montessori_with_pr2
    cube_shape = shape_with_category(montessori, "cube")
    hole = montessori.board.hole_for(cube_shape)
    hole_position = hole.root.global_transform.to_position()
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape, board=montessori.board, arm=Arms.RIGHT
    )
    with simulated_robot:
        node = execute_single(action, context=context)
        node.perform()

    shape_position = cube_shape.global_transform.to_position()
    assert float(shape_position.x) == pytest.approx(float(hole_position.x), abs=0.05)
    assert float(shape_position.y) == pytest.approx(float(hole_position.y), abs=0.05)
