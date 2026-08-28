"""
Recognise a loose piece by fitting the pieces this set is known to contain to the
outline the camera measured.

Rather than measuring proportions of an outline and deciding from thresholds what shape
they suggest (which is how the holes in the board's lid are still read, see
:class:`~experiments.montessori.perception.footprint.CrossSectionClassifier`), each known
piece is laid over the measured outline and turned until it fits best. The set is small
and every piece in it has been measured, so the question is not *what shape is this* but
*which of these four is it, and how is it turned* -- a question with a far narrower
answer, and one whose answer carries how well it fitted.

That fit is what makes the shape and the orientation one result rather than two: an
outline is recognised at the same moment its turn is found, and a piece no known outline
covers is refused instead of being reported as whichever threshold it happened to fall
between.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np
from typing_extensions import List, Optional, Tuple

from experiments.montessori.pieces import (
    HUE_TOLERANCE,
    KNOWN_PIECES,
    KnownPiece,
    hue_distance,
)

# %% what a fit came to


@dataclass(frozen=True, eq=False)
class MatchedPiece:
    """
    Which known piece an outline was recognised as, and how it is turned.
    """

    piece: KnownPiece
    """
    The piece the outline was recognised as.
    """

    yaw: float
    """
    How far it is turned about the world frame's z-axis, in radians.

    Always the smallest turn that leaves the piece looking as it does, so a square is
    reported within an eighth of a turn of straight and a circle at zero.
    """

    overlap: float
    """
    How much of the two outlines coincided, as the area they share divided by the area
    they cover together.

    One is an exact fit. A low value says the outline the camera measured is not the
    shape of any piece, which on a reflective table is what happens when a piece's own
    reflection is taken in along with it.
    """


# %% fitting them


@dataclass(frozen=True)
class PieceMatcher:
    """
    Recognises a measured outline as one of the pieces this set contains.
    """

    candidates: Tuple[KnownPiece, ...] = KNOWN_PIECES
    """
    The pieces that may be found on the table.
    """

    hue_tolerance: int = HUE_TOLERANCE
    """
    How far a measured colour may sit from a piece's own before that piece is ruled out.
    """

    minimum_overlap: float = 0.6
    """
    How much of the two outlines must coincide before a piece is reported at all.

    A cleanly seen piece reaches at least 0.94, and the widest an outline of the wrong
    shape was measured to reach is 0.52; this sits between them, low enough that a piece
    read together with its own reflection in the table still comes through at 0.68.
    """

    angle_step: float = math.radians(2.0)
    """
    How finely a piece is turned while looking for its best fit, in radians.

    Two degrees moves the far corner of the largest piece here by under a millimetre, so
    a finer sweep would be answering below the resolution the outline was measured at.
    """

    resolution: float = 0.001
    """
    Edge length, in metres, of the pixels the two outlines are compared over, matching
    the rectified image the measured one came from.
    """

    def match(
        self,
        outline: np.ndarray,
        center: Tuple[float, float],
        hue: Optional[int],
    ) -> Optional[MatchedPiece]:
        """
        Recognise a measured outline.

        :param outline: The outline as ``(n, 2)`` world-frame ``(x, y)`` points.
        :param center: The world-frame ``(x, y)`` the outline is centred on, which each
            candidate is laid over.
        :param hue: The colour the outline was measured to be, or None where it had no
            colour to read.
        :return: The best fit, or None if no known piece covers the outline well enough.
        """
        candidates = [piece for piece in self.candidates if self._could_be(piece, hue)]
        if not candidates:
            return None
        measured = np.asarray(outline, dtype=float).reshape(-1, 2) - np.asarray(
            center, dtype=float
        )
        extent = max(
            [float(np.abs(measured).max())] + [piece.radius for piece in candidates]
        )
        drawn_measurement = self._draw(measured, extent)
        best = max(
            (self._best_turn(piece, drawn_measurement, extent) for piece in candidates),
            key=lambda fit: fit.overlap,
        )
        if best.overlap < self.minimum_overlap:
            return None
        return best

    def _could_be(self, piece: KnownPiece, hue: Optional[int]) -> bool:
        """
        Whether a piece's own colour is close enough to a measured one to be it.

        :param piece: The piece to consider.
        :param hue: The colour measured, or None where there was none to read.
        """
        if hue is None:
            return True
        return hue_distance(hue, piece.hue) <= self.hue_tolerance

    def _best_turn(
        self, piece: KnownPiece, drawn_measurement: np.ndarray, extent: float
    ) -> MatchedPiece:
        """
        Turn one piece until it covers a measured outline as well as it can.

        :param piece: The piece to lay over the outline.
        :param drawn_measurement: The measured outline, already drawn.
        :param extent: Half the width, in metres, of the square both are drawn in.
        :return: The best fit this piece reaches.
        """
        return max(
            (
                MatchedPiece(
                    piece=piece,
                    yaw=angle,
                    overlap=self._overlap(
                        drawn_measurement,
                        self._draw(piece.turned_outline(angle), extent),
                    ),
                )
                for angle in self._turns_of(piece)
            ),
            key=lambda fit: fit.overlap,
        )

    def _turns_of(self, piece: KnownPiece) -> List[float]:
        """
        The turns a piece is worth trying, which span one of its rotation periods about
        zero and so hold every orientation it can be told apart in.

        :param piece: The piece to turn.
        """
        if piece.rotation_period is None:
            return [0.0]
        steps = int(piece.rotation_period / 2 / self.angle_step)
        return list(np.arange(-steps, steps + 1) * self.angle_step)

    def _draw(self, outline: np.ndarray, extent: float) -> np.ndarray:
        """
        Draw an outline centred on the origin, filled in.

        :param outline: The outline as ``(n, 2)`` ``(x, y)`` points in metres.
        :param extent: Half the width of the square to draw it in, in metres.
        :return: The filled outline, one inside it and zero elsewhere.
        """
        side = int(round(2 * extent / self.resolution)) + 1
        canvas = np.zeros((side, side), dtype=np.uint8)
        pixels = np.round((outline + extent) / self.resolution).astype(np.int32)
        cv2.fillPoly(canvas, [pixels.reshape(-1, 1, 2)], 1)
        return canvas

    @staticmethod
    def _overlap(one: np.ndarray, other: np.ndarray) -> float:
        """
        How much of two drawn outlines coincide.

        :param one: The first outline, drawn.
        :param other: The second, drawn the same size.
        :return: The area they share divided by the area they cover together.
        """
        shared = int(np.count_nonzero(one & other))
        covered = int(np.count_nonzero(one | other))
        return shared / covered if covered else 0.0
