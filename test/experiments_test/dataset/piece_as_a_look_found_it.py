"""
A role of a piece, standing in for what a look reports: something that is not the piece
but stands for it, the way a sighting stands for the thing sighted.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.montessori.semantics import MontessoriShape
from krrood.patterns.role import Role


@dataclass(eq=False)
class PieceAsALookFoundIt(Role[MontessoriShape]):
    """
    The piece as one look reported it, which is a role of the piece the world holds
    rather than that piece.
    """
