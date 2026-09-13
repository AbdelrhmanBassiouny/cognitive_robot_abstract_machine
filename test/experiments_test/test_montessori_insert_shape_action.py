import math

import pytest

import experiments.orm.ormatic_interface  # type: ignore
from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot
from coraplex.plans.executables import Executable
from coraplex.plans.factories import execute_single
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.patterns.caching import clear_memoization_cache

from experiments.montessori.insert_shape_action import (
    NO_HORIZONTAL_OFFSET,
    InsertMontessoriShapeAction,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    NoMatchingHoleError,
)
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


# %% the pose a shape states for its own hole


def _montessori_without_a_robot() -> MontessoriWorld:
    """
    The board with its holes and one loose shape of every kind, and no robot: the
    release pose a shape states is read off the shape and its hole alone.
    """
    montessori = MontessoriWorld()
    montessori.world.update_forward_kinematics()
    return montessori


def _insertion_of(
    shape: MontessoriShape, montessori: MontessoriWorld
) -> InsertionAction:
    """
    The insertion :class:`InsertMontessoriShapeAction` builds for ``shape``: through the
    hole of the board that matches it, turned the way the shape states for that hole.

    :param shape: The shape to insert.
    :param montessori: The world holding the board the shape goes into.
    """
    hole = montessori.board.hole_for(shape)
    hover_height = InsertMontessoriShapeAction.insertion_hover_height
    stated_pose = shape.insertion_pose_relative_to_hole(
        hole, NO_HORIZONTAL_OFFSET, hover_height
    )
    return InsertionAction(
        shape.root,
        hole,
        Arms.RIGHT,
        hover_height=hover_height,
        target_R_body=stated_pose.to_rotation_matrix(),
    )


def test_the_release_pose_is_the_one_the_shape_states_for_its_hole():
    """
    An insertion turned the way a Montessori shape states releases it exactly where the
    shape itself says it has to be to drop through its hole.
    """
    montessori = _montessori_without_a_robot()
    cube = shape_with_category(montessori, MontessoriShapeCategory.CUBE)
    hole = montessori.board.hole_for(cube)

    insertion = _insertion_of(cube, montessori)

    assert insertion.insertion_pose.to_np().flatten().tolist() == pytest.approx(
        cube.insertion_pose_relative_to_hole(
            hole, NO_HORIZONTAL_OFFSET, insertion.hover_height
        )
        .to_np()
        .flatten()
        .tolist()
    )


def test_a_disk_is_released_turned_onto_its_edge_and_a_cube_is_not():
    """
    The pose the shape states is what makes the difference: a disk has to present its
    edge to its slot, where a cube only has to hover over its hole.
    """
    montessori = _montessori_without_a_robot()
    turns = {}
    for category in (MontessoriShapeCategory.CUBE, MontessoriShapeCategory.DISK):
        shape = shape_with_category(montessori, category)
        insertion = _insertion_of(shape, montessori)
        _, pitch, _ = insertion.insertion_pose.to_rotation_matrix().to_rpy()
        turns[category] = float(pitch)

    assert turns[MontessoriShapeCategory.CUBE] == pytest.approx(0.0)
    assert turns[MontessoriShapeCategory.DISK] == pytest.approx(math.pi / 2)
