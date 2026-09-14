"""
The plan the framework figure shows, written once and whole.

It says what it wants and leaves open everything it does not know: the piece to pick up,
which is looked for; whether that piece is where the plan needs it, which is read off the
world; how to take hold of it, which is sampled; and the hole it goes through, which is
concluded by rules. Nothing here says who supplies any of it -- every backend declares
what it can answer, and
:meth:`~coraplex.plans.plan_node.PlanNode.grounded_by` hands each slot to the first that
declares it can.
"""

from __future__ import annotations

from coraplex.datastructures.enums import Arms
from coraplex.datastructures.grasp import GraspDescription
from coraplex.language import SequentialNode
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from krrood.entity_query_language.factories import a, an
from semantic_digital_twin.reasoning.predicates import Colored, SupportedBy
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.world_entity import Body

SORTED_PIECE = MontessoriShapeCategory.CUBE
"""
The shape of piece this plan sorts.
"""

PIECE_COLOR: Color = KNOWN_PIECE_BY_CATEGORY[SORTED_PIECE].color
"""
The colour the set says a piece of that shape wears, which is what tells it from the
pieces of the other shapes on the table.
"""


def sorting_plan(
    board: ShapeSortingBoard, lid: Body, arm: Arms, end_effector: EndEffector
) -> SequentialNode:
    """
    Pick the piece up off the board's lid and put it through the hole it belongs in.

    :param board: The board the piece goes into, whose holes the hole wanted is one of.
    :param lid: The board's lid, as the surface a look searches names it.
    :param arm: The arm that picks the piece up and carries it.
    :param end_effector: That arm's hand, which the grasp is described for.
    :return: The plan, with the three things it does not supply left open.
    """
    piece = a(DetectedMontessoriShape)(category=SORTED_PIECE)
    piece = piece.where(Colored(piece, PIECE_COLOR), SupportedBy(piece, lid))
    return sequential(
        [
            a(PickUpAction)(
                arm=arm,
                object_designator=piece,
                grasp_description=a(GraspDescription)(
                    approach_direction=...,
                    vertical_alignment=...,
                    end_effector=end_effector,
                ),
            ),
            an(InsertionAction)(
                object_designator=piece,
                target=a(ShapeSortingHole)(shape_category=...).from_(board.apertures),
                arm=arm,
            ),
        ]
    )
