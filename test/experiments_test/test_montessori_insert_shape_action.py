import pytest

import experiments.orm.ormatic_interface  # type: ignore
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot
from coraplex.plans.executables import Executable
from coraplex.plans.factories import execute_single
from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.utils import clear_memoization_cache

from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction
from experiments.montessori.semantics import MontessoriShape, NoMatchingHoleError
from experiments.montessori.world import MontessoriWorld, robot_installed
from semantic_digital_twin.robots.hsrb import HSRB
from semantic_digital_twin.spatial_types.spatial_types import Point3


@pytest.fixture
def montessori_with_robot():
    if not robot_installed(HSRB):
        pytest.skip("hsr_description is not installed")

    montessori = MontessoriWorld()
    montessori.spawn_robot(HSRB)
    montessori.world.update_forward_kinematics()
    return montessori


def shape_with_category(montessori: MontessoriWorld, category: str) -> MontessoriShape:
    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == category
    ]
    return shape


def test_insert_montessori_shape_action_builds_a_valid_plan(montessori_with_robot):
    montessori = montessori_with_robot
    cube_shape = shape_with_category(montessori, "cube")
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape, board=montessori.board, arm=Arms.RIGHT
    )
    plan = execute_single(action, context=context)
    plan.notify()
    executable = plan.parse()

    assert isinstance(executable, Executable)


def test_insert_montessori_shape_action_moves_the_shape_to_its_matching_hole(
    montessori_with_robot,
):
    montessori = montessori_with_robot
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


def test_insert_montessori_shape_action_applies_the_target_horizontal_offset(
    montessori_with_robot,
):
    """
    A retried insertion (see
    :func:`~experiments.montessori.montessori_demo._insert_all_shapes`) sets
    target_horizontal_offset so the shape is released over a different point than a
    failed previous attempt, rather than repeating the exact same drop.
    """
    montessori = montessori_with_robot
    cube_shape = shape_with_category(montessori, "cube")
    hole = montessori.board.hole_for(cube_shape)
    hole_position = hole.root.global_transform.to_position()
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )
    offset = Point3(0.01, -0.01, 0.0)

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape,
        board=montessori.board,
        arm=Arms.RIGHT,
        target_horizontal_offset=offset,
    )
    with simulated_robot:
        node = execute_single(action, context=context)
        node.perform()

    shape_position = cube_shape.global_transform.to_position()
    assert float(shape_position.x) == pytest.approx(
        float(hole_position.x) + float(offset.x), abs=0.05
    )
    assert float(shape_position.y) == pytest.approx(
        float(hole_position.y) + float(offset.y), abs=0.05
    )


def test_insert_montessori_shape_action_runs_twice_in_a_row(montessori_with_robot):
    """
    World.get_kinematic_structure_entities_of_branch is memoized per (world, root-
    object) and never invalidated across an attach/detach cycle, so a second insertion's
    gripper-contents query can silently see a stale, empty branch for the previous
    insertion's already-released grasp.

    Clearing the memoization cache
    before each insertion (as :func:`~experiments.montessori.montessori_demo._insert_all_shapes`
    does) works around this.
    """
    montessori = montessori_with_robot
    cube_shape = shape_with_category(montessori, "cube")
    triangle_shape = shape_with_category(montessori, "triangular_prism")
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    for shape in (cube_shape, triangle_shape):
        hole = montessori.board.hole_for(shape)
        hole_position = hole.root.global_transform.to_position()

        clear_memoization_cache(montessori.world)
        action = InsertMontessoriShapeAction(
            montessori_shape=shape, board=montessori.board, arm=Arms.RIGHT
        )
        with simulated_robot:
            node = execute_single(action, context=context)
            node.perform()

        shape_position = shape.global_transform.to_position()
        assert float(shape_position.x) == pytest.approx(
            float(hole_position.x), abs=0.05
        )
        assert float(shape_position.y) == pytest.approx(
            float(hole_position.y), abs=0.05
        )


def test_insert_montessori_shape_action_raises_for_a_shape_without_a_matching_hole(
    montessori_with_robot,
):
    montessori = montessori_with_robot
    sphere_shape = shape_with_category(montessori, "sphere")
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    action = InsertMontessoriShapeAction(
        montessori_shape=sphere_shape, board=montessori.board, arm=Arms.RIGHT
    )

    with pytest.raises(NoMatchingHoleError):
        plan = execute_single(action, context=context)
        plan.notify()
        plan.parse()


def test_has_fallen_through_hole_is_false_right_after_kinematic_placement(
    montessori_with_robot,
):
    """
    PlaceAction only ever kinematically teleports the shape to hover above its hole; it
    never checks whether the shape actually fits through, so has_fallen_through_hole
    must not read that teleport alone as success.
    """
    montessori = montessori_with_robot
    cube_shape = shape_with_category(montessori, "cube")
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape, board=montessori.board, arm=Arms.RIGHT
    )
    with simulated_robot:
        node = execute_single(action, context=context)
        node.perform()

    assert action.has_fallen_through_hole() is False


def test_has_fallen_through_hole_is_true_once_the_shape_settles_in_mujoco(
    montessori_with_robot,
):
    from experiments.montessori.montessori_demo import _settle_shape_in_mujoco

    montessori = montessori_with_robot
    cube_shape = shape_with_category(montessori, "cube")
    context = Context(
        montessori.world, montessori.robot, query_backend=ProbabilisticBackend()
    )

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape, board=montessori.board, arm=Arms.RIGHT
    )
    with simulated_robot:
        node = execute_single(action, context=context)
        node.perform()

    _settle_shape_in_mujoco(cube_shape, montessori, headless=True)

    assert action.has_fallen_through_hole() is True
