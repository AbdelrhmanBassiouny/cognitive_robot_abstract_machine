"""
A scene whose board and pieces the world already holds, standing in for one the camera
found, so a sorting run can be asked what it would do without a look being taken.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List

from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
from semantic_digital_twin.world import World


@dataclass
class SceneAlreadyStood:
    """
    The board and the pieces, as a world already holds them.
    """

    world: World
    """
    The world holding them.
    """

    board: ShapeSortingBoard
    """
    The board, as the world holds it.
    """

    pieces: List[MontessoriShape] = field(default_factory=list)
    """
    The pieces on the table, as the world holds them.
    """

    def perceive(self) -> None:
        """
        Look at the scene, which is already stood and so is already looked at.
        """
