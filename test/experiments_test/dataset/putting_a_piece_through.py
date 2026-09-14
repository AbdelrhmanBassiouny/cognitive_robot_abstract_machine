"""
Putting one piece through a hole of the board, standing in for the action a plan states,
so a description of the hole can be handed over by a statement about a piece without the
tests depending on a robot plan of their own.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.montessori.semantics import ShapeSortingHole
from semantic_digital_twin.world_description.world_entity import Body


@dataclass
class PuttingAPieceThrough:
    """
    One piece, and the hole it is put through.
    """

    piece: Body
    """
    The body the piece stands on, which is how an action names the thing it handles.
    """

    hole: ShapeSortingHole
    """
    The hole it goes through.
    """
