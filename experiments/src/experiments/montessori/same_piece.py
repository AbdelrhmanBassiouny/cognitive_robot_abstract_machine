"""
When two bodies are the same Montessori piece.

A plan is made in the world the robot believes, where a piece it perceived stands under
a name of its own; the monitor reports the piece as the world it watched holds it, under
another. They are one piece, and this is what says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional

from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.paper.run_plan import ObjectIdentity
from semantic_digital_twin.world_description.world_entity import Body


def kind_of(body: Body) -> Optional[MontessoriShapeCategory]:
    """
    The kind of piece a body is, in the world it stands in.

    :param body: The body to ask.
    :return: Its kind, or None where its world does not hold it as a piece.
    """
    for shape in body._world.get_semantic_annotations_by_type(MontessoriShape):
        if shape.root is body:
            return shape.shape_category
    return None


@dataclass(frozen=True)
class SamePiece(ObjectIdentity):
    """
    Two bodies are the same piece when the twin gives them the same name, or when each
    is a piece of the same kind in its own world.
    """

    def same(self, one: Body, other: Body) -> bool:
        if one.name == other.name:
            return True
        kinds = (kind_of(one), kind_of(other))
        return None not in kinds and kinds[0] is kinds[1]
