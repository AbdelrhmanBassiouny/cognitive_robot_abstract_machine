"""
Tests that :class:`~experiments.montessori.insert_shape_action.InsertMontessoriShapeAction`
generalizes to a robot with no mobile base at all, using a self-contained synthetic
robot (see :mod:`.dataset.synthetic_fixed_arm_robot`) instead of a real fixed-base
robot's own description (e.g. the Panda's MJCF), which this environment cannot resolve
without a network fetch.
"""

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.plans.factories import execute_single
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.spatial_types.spatial_types import Point3

from experiments.montessori.insert_shape_action import InsertMontessoriShapeAction
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import MontessoriWorld

from .dataset.synthetic_fixed_arm_robot import SyntheticFixedArmRobot

MOUNT_POSITION = Point3(0.25, 0.0, 0.5)


def _montessori_with_mounted_fixed_arm_robot() -> MontessoriWorld:
    montessori = MontessoriWorld()
    # A robot stand is a Table too, so the scene now holds two of them; the fixed-base
    # plan must not depend on there being exactly one (the montessori table).
    montessori.add_robot_stand(MOUNT_POSITION)
    robot_world = URDFParser.from_file(
        SyntheticFixedArmRobot.get_ros_file_path()
    ).parse()
    montessori.mount_stationary_robot(
        SyntheticFixedArmRobot, robot_world, MOUNT_POSITION
    )
    montessori.world.update_forward_kinematics()
    return montessori


def _shape_with_category(montessori: MontessoriWorld, category: str) -> MontessoriShape:
    [shape] = [
        shape
        for shape in montessori.world.get_semantic_annotations_by_type(MontessoriShape)
        if shape.shape_category == category
    ]
    return shape


def _designator_type_names(node) -> list[str]:
    """
    The class name of every node's designator in the plan tree rooted at ``node``, in
    the order they are visited.
    """
    names = []
    designator = getattr(node, "designator", None)
    if designator is not None:
        names.append(type(designator).__name__)
    for child in node.children:
        names.extend(_designator_type_names(child))
    return names


def test_insert_montessori_shape_action_builds_a_plan_for_a_fixed_base_robot():
    montessori = _montessori_with_mounted_fixed_arm_robot()
    cube_shape = _shape_with_category(montessori, "cube")
    context = Context(montessori.world, montessori.robot)

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape, board=montessori.board, arm=Arms.RIGHT
    )
    plan = execute_single(action, context=context)
    plan.notify()
    plan.parse()

    assert "InsertMontessoriShapeAction" in _designator_type_names(plan)


def test_insert_montessori_shape_action_skips_navigation_for_a_fixed_base_robot():
    montessori = _montessori_with_mounted_fixed_arm_robot()
    cube_shape = _shape_with_category(montessori, "cube")
    context = Context(montessori.world, montessori.robot)

    action = InsertMontessoriShapeAction(
        montessori_shape=cube_shape, board=montessori.board, arm=Arms.RIGHT
    )
    plan = execute_single(action, context=context)
    plan.notify()
    plan.parse()

    assert "NavigateAction" not in _designator_type_names(plan)
