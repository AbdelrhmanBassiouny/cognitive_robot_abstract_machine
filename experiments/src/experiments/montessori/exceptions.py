"""
The ways the Montessori scene's semantics can fail.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import FrozenSet, Optional, TYPE_CHECKING

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from experiments.montessori.semantics import (
        MontessoriShape,
        MontessoriShapeCategory,
        ShapeSortingBoard,
        ShapeSortingHole,
    )


@dataclass
class NoMatchingHoleError(DataclassException):
    """
    Raised when a :class:`~experiments.montessori.semantics.ShapeSortingBoard` has no
    :class:`~experiments.montessori.semantics.ShapeSortingHole` whose category matches a
    given :class:`~experiments.montessori.semantics.MontessoriShape`.
    """

    montessori_shape: MontessoriShape
    """
    The shape that has no matching hole.
    """

    board: ShapeSortingBoard
    """
    The board that has no hole matching :attr:`montessori_shape`.
    """

    def error_message(self) -> str:
        return (
            f"{self.board.name} has no hole matching {self.montessori_shape.name}'s "
            f"category {self.montessori_shape.shape_category}."
        )

    def suggest_correction(self) -> str:
        return ""


@dataclass
class NoSuchPieceError(DataclassException):
    """
    Raised when a scene is asked about a loose piece of a shape it does not hold.
    """

    shape_category: MontessoriShapeCategory
    """
    The shape that was asked about.
    """

    standing_in_the_scene: FrozenSet[MontessoriShapeCategory]
    """
    The shapes the scene does hold a piece of.
    """

    def error_message(self) -> str:
        holds = ", ".join(sorted(str(each) for each in self.standing_in_the_scene))
        return f"No piece of shape {self.shape_category} stands in this scene; it holds {holds}."

    def suggest_correction(self) -> str:
        return (
            "Name a shape the scene's layout places, or build the scene from a layout "
            "that places this one."
        )


@dataclass
class HoleHasNoLandingRegionError(DataclassException):
    """
    Raised when the space under a hole is asked for and that hole was never measured.
    """

    hole: ShapeSortingHole
    """
    The hole with no space measured under it.
    """

    def error_message(self) -> str:
        return f"{self.hole.name} has no landing region, so nothing can be inside it."

    def suggest_correction(self) -> str:
        return (
            "Take the hole from a world that measured the space under it, which "
            "MontessoriWorld does when it builds its board."
        )


@dataclass
class BoardDescriptionIncomplete(DataclassException):
    """
    Raised when a statement of the shape-sorting board leaves open something a look
    needs to lay the board's holes over a picture.
    """

    missing_attribute: str
    """
    The attribute the statement leaves open, by the name the annotation gives it.
    """

    hole_index: Optional[int] = None
    """
    Which of the stated holes leaves it open, in the order they were stated, or None
    where the board itself does.
    """

    def error_message(self) -> str:
        described = (
            "The board" if self.hole_index is None else f"Hole {self.hole_index}"
        )
        return f"{described} is stated without its {self.missing_attribute}."

    def suggest_correction(self) -> str:
        return (
            "State the lid's size and height, and every hole's shape, size and place "
            "on the lid, so the whole layout can be fitted at once."
        )
