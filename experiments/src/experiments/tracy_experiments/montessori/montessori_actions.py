"""
Build the sequence of pick/place actions that sorts every loose Montessori shape with a
matching hole -- shared between :mod:`~experiments.tracy_experiments.
montessori_demo_mujoco` (MuJoCo stands in as the real robot) and
:mod:`~experiments.tracy_experiments.montessori.montessori_demo_real` (the physical robot is the
real robot), which differ only in which pick/place action class each shape's actions are
built from.
"""

from __future__ import annotations

import logging

from typing_extensions import Callable, List

from coraplex.datastructures.enums import ApproachDirection, Arms, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.robot_plans.actions.base import ActionDescription
from coraplex.view_manager import ViewManager
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    NoMatchingHoleError,
    ShapeSortingBoard,
)
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

SKIPPED_SHAPE_CATEGORIES = frozenset({MontessoriShapeCategory.DISK})
"""
Shape categories this demo leaves where they are.
"""


def build_sorting_actions(
    world: World,
    board: ShapeSortingBoard,
    robot: AbstractRobot,
    arm: Arms,
    pick_up_action: Callable[[Body, Arms, GraspDescription], ActionDescription],
    place_action: Callable[[Body, Pose, Arms], ActionDescription],
) -> List[ActionDescription]:
    """
    One pick/place action pair per loose Montessori shape that has a matching hole,
    placing it above that hole rather than trying to make it fall through: there is no
    fall-through check and no retry loop here (unlike :class:`~experiments.montessori.
    insert_shape_action.InsertMontessoriShapeAction`).

    :param world: The world to read loose shapes from.
    :param board: The board to find each shape's matching hole on.
    :param robot: The robot performing the actions.
    :param arm: Which arm picks up and places every shape.
    :param pick_up_action: Builds the pick-up action for one shape, e.g.
        ``PickUpAction`` or a partial application of ``PickUpActionMujoco``.
    :param place_action: Builds the place action for one shape, e.g. ``PlaceAction`` or
        a partial application of ``PlaceActionMujoco``.
    :return: The full action sequence, two actions per sorted shape.
    """
    actions: List[ActionDescription] = []
    for shape in world.get_semantic_annotations_by_type(MontessoriShape):
        if shape.shape_category in SKIPPED_SHAPE_CATEGORIES:
            logger.info(
                "Skipping %s: %s is not sorted.", shape.name, shape.shape_category
            )
            continue
        try:
            hole = board.hole_for(shape)
        except NoMatchingHoleError:
            logger.info("Skipping %s: no matching hole.", shape.name)
            continue
        grasp_description = GraspDescription(
            ApproachDirection.FRONT,
            VerticalAlignment.TOP,
            ViewManager.get_end_effector_view(arm, robot),
        )
        actions.append(pick_up_action(shape.root, arm, grasp_description))
        actions.append(
            place_action(shape.root, hole.root.global_transform.to_pose(), arm)
        )
    return actions
