"""
The loose Montessori pieces this lab's physical set actually contains.

Every measurement here was taken off the pieces themselves rather than derived from the
board's own holes: a piece is cut smaller than the hole it drops through, so the hole's
footprint is the wrong size to recognise a piece by or to build one from.

Each piece is described by the outline it presents while resting on its own flat face,
the colour it was measured to be, and how far it can be turned about its standing axis
before it looks as it did. That last one is what makes a piece's orientation a *minimal*
turn rather than an absolute one: a square is unchanged by a quarter turn, so there is
no sense in reporting that it was turned by more.
"""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np
from typing_extensions import Optional, Tuple, Type, Union

from experiments.montessori.semantics import (
    CubeShape,
    CylinderShape,
    MontessoriShape,
    RectangularPrismShape,
    TriangularPrismShape,
)
from semantic_digital_twin.world_description.geometry import Color, Polygon2D

# %% the colours they were measured to be


@dataclass(frozen=True)
class HueCircle:
    """
    The colour circle as OpenCV encodes hue in a byte: hues run from zero up to
    :attr:`size` and wrap around there.
    """

    size: int = 180
    """
    Number of hues OpenCV fits into a byte.
    """

    def distance(
        self, one: Union[int, np.ndarray], other: int
    ) -> Union[int, np.ndarray]:
        """
        How far apart two hues lie on the colour circle, the short way round.

        :param one: A hue as OpenCV reports it, or an array of them.
        :param other: The hue to compare it against.
        :return: The distance, element by element when ``one`` is an array.
        """
        apart = np.abs(np.asarray(one, dtype=int) - int(other))
        return np.minimum(apart, self.size - apart)

    def pure_color(self, hue: int) -> Color:
        """
        A hue at full saturation and brightness.

        :param hue: A hue as OpenCV reports it.
        """
        red, green, blue = colorsys.hsv_to_rgb(hue / self.size, 1.0, 1.0)
        return Color(red, green, blue)


class PieceHue(IntEnum):
    """
    The hues the pieces in this set wear, measured off the rectified camera image as
    OpenCV reports hue.
    """

    CYAN = 86
    """
    Hue of the pale blue pieces.
    """

    YELLOW = 21
    """
    Hue of the yellow pieces.

    The bare table has no colour to speak of, so nothing on it competes for this; the
    board's own lid does share it, but the lid is searched on its own plane and excluded
    from the loose pieces by its outline.
    """


# %% one kind of piece


@dataclass(frozen=True, eq=False)
class KnownPiece:
    """
    One kind of loose piece this set contains, as measured off the piece itself.
    """

    category: Type[MontessoriShape]
    """
    The kind of piece it is, and so the hole it belongs in.
    """

    outline: Polygon2D
    """
    The outline it presents while resting on its own flat face, in metres about its own
    centre, at zero turn.
    """

    height: float
    """
    How far its top face stands above the surface it rests on, in metres.
    """

    hue: int
    """
    The colour it was measured to be, as OpenCV reports hue.
    """

    rotation_period: Optional[float]
    """
    The smallest turn about its standing axis, in radians, that leaves it looking as it
    did, or None when every turn does.

    An orientation is only ever reported within half of this either way, since a larger
    turn is indistinguishable from a smaller one.
    """

    @property
    def color(self) -> Color:
        """
        The colour to draw this piece in.

        Only :attr:`hue` was measured off the piece, so this is that hue at full
        saturation and brightness -- the pure form of the colour it wears, rather than
        the shade any one photograph of it happened to catch.
        """
        return HueCircle().pure_color(self.hue)

    @property
    def radius(self) -> float:
        """
        How far its outline reaches from its own centre, in metres.
        """
        return float(np.abs(self.outline.vertices).max())

    def smallest_equivalent_turn(self, angle: float) -> float:
        """
        The smallest turn that leaves this piece looking the way the given one does.

        :param angle: A turn about the world frame's z-axis, in radians.
        :return: The same turn brought within half a :attr:`rotation_period` of zero, or
            zero for a piece no turn changes.
        """
        if self.rotation_period is None:
            return 0.0
        half = self.rotation_period / 2
        return (angle + half) % self.rotation_period - half


# %% the set they make up


@dataclass(frozen=True)
class PieceSet:
    """
    The kinds of loose piece a physical set contains, and how closely a measured colour
    must match one of theirs to be taken for it.
    """

    pieces: Tuple[KnownPiece, ...]
    """
    Every kind of loose piece in the set.
    """

    hue_tolerance: int = 4
    """
    How far a measured colour may sit from a piece's own and still be taken for it.

    Measured on this table, every piece read within 2 of its own recorded colour while
    the two things standing on the table that are not pieces read 6 and 7 away, so this
    sits midway between and turns them away. It is the one number here that a real
    change of lighting would have to be re-measured for.
    """

    hue_circle: HueCircle = field(default_factory=HueCircle)
    """
    The colour circle the pieces' hues lie on.
    """

    @classmethod
    def this_lab(cls) -> PieceSet:
        """
        The pieces this lab's physical set contains, with every dimension in metres.

        The disk and the sphere are left out because this physical set has neither.
        """
        return cls(
            pieces=(
                KnownPiece(
                    category=CubeShape,
                    outline=Polygon2D.rectangle(width=0.03, length=0.03),
                    height=0.03,
                    hue=PieceHue.CYAN,
                    rotation_period=math.pi / 2,
                ),
                KnownPiece(
                    category=CylinderShape,
                    outline=Polygon2D.circle(diameter=0.028),
                    height=0.03,
                    hue=PieceHue.CYAN,
                    rotation_period=None,
                ),
                KnownPiece(
                    category=RectangularPrismShape,
                    outline=Polygon2D.rectangle(width=0.02, length=0.04),
                    height=0.03,
                    hue=PieceHue.YELLOW,
                    rotation_period=math.pi,
                ),
                KnownPiece(
                    category=TriangularPrismShape,
                    outline=Polygon2D.equilateral_triangle(side=0.037),
                    height=0.03,
                    hue=PieceHue.YELLOW,
                    rotation_period=2 * math.pi / 3,
                ),
            )
        )

    @property
    def hues(self) -> Tuple[int, ...]:
        """
        Every colour a piece in this set wears.

        What a piece stands on is whatever the table happens to be covered with, so it
        is these that say a pixel belongs to a piece rather than anything about the
        surface under it.
        """
        return tuple(sorted({piece.hue for piece in self.pieces}))

    def piece_for(self, category: Type[MontessoriShape]) -> Optional[KnownPiece]:
        """
        The piece of a given kind, or None when this set has none of that kind.

        :param category: The kind of piece to look up.
        """
        for piece in self.pieces:
            if piece.category is category:
                return piece
        return None

    def could_be(self, piece: KnownPiece, hue: Optional[int]) -> bool:
        """
        Whether a piece's own colour is close enough to a measured one to be it.

        :param piece: The piece to consider.
        :param hue: The colour measured, or None where there was none to read.
        """
        if hue is None:
            return True
        return bool(self.hue_circle.distance(hue, piece.hue) <= self.hue_tolerance)

    def wears_a_piece_colour(self, hue: np.ndarray) -> np.ndarray:
        """
        Which of the given hues lie close enough to one a piece in this set wears.

        :param hue: Hues as OpenCV reports them, of any shape.
        :return: A boolean array of the same shape.
        """
        apart = np.stack([self.hue_circle.distance(hue, worn) for worn in self.hues])
        return apart.min(axis=0) <= self.hue_tolerance
