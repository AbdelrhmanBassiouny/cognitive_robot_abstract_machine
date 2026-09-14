"""
The plan the framework figure shows, written once and whole.

It says what it wants and leaves open everything it does not know: the piece to pick up,
which is looked for; whether that piece is where the plan needs it, which is read off the
world; which side of it the hand comes at, which is sampled; and the hole it goes
through, which is concluded by rules. Nothing here says who supplies any of it -- every
backend declares what it can answer, and
:meth:`~coraplex.plans.plan_node.PlanNode.grounded_by` hands each slot to the first that
declares it can.

The one thing the plan says about the grasp itself is that the hand comes down on the
piece: a piece resting on a surface offers the fingers nothing but its top, so which of
its sides the hand faces is all that is left to sample. Both actions state that one
grasp, so the piece is carried and let go held the way it was taken hold of.
"""

from __future__ import annotations

from coraplex.datastructures.enums import Arms, VerticalAlignment
from coraplex.datastructures.grasp import GraspDescription
from coraplex.language import SequentialNode
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.insertion import InsertionAction
from coraplex.robot_plans.actions.core.pick_up import PickUpAction
from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.pieces import KnownPieceSet
from experiments.montessori.semantics import (
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from krrood.entity_query_language.factories import a, an
from semantic_digital_twin.reasoning.predicates import Colored, SupportedBy
from semantic_digital_twin.robots.robot_parts import EndEffector
from semantic_digital_twin.world_description.world_entity import Body

SORTED_PIECE = MontessoriShapeCategory.CUBE
"""
The shape of piece this plan sorts.
"""

FROM_ABOVE = VerticalAlignment.TOP
"""
The hand comes down on the piece, which is the only way to the fingers a piece resting
on a surface leaves open.
"""


def sorting_plan(
    board: ShapeSortingBoard,
    lid: Body,
    pieces: KnownPieceSet,
    arm: Arms,
    end_effector: EndEffector,
) -> SequentialNode:
    """
    Pick the piece up off the board's lid and put it through the hole it belongs in.

    :param board: The board the piece goes into, whose holes the hole wanted is one of.
    :param lid: The board's lid, as the surface a look searches names it.
    :param pieces: The set on this table, which says what colour a piece of the shape
        sorted wears.
    :param arm: The arm that picks the piece up and carries it.
    :param end_effector: That arm's hand, which the grasp is described for.
    :return: The plan, with the three things it does not supply left open.
    """
    piece = a(DetectedMontessoriShape)(category=SORTED_PIECE)
    piece = piece.where(
        Colored(piece, pieces.by_category[SORTED_PIECE].color),
        SupportedBy(piece, lid),
    )
    grasp = a(GraspDescription)(
        approach_direction=...,
        vertical_alignment=FROM_ABOVE,
        end_effector=end_effector,
    )
    return sequential(
        [
            a(PickUpAction)(
                arm=arm,
                object_designator=piece,
                grasp_description=grasp,
            ),
            an(InsertionAction)(
                object_designator=piece,
                target=a(ShapeSortingHole)(shape_category=...).from_(board.apertures),
                arm=arm,
                grasp_description=grasp,
            ),
        ]
    )
