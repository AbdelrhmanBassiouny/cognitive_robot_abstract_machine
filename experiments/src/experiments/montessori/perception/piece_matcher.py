"""
Recognise a loose piece by laying the pieces this set is known to contain over the edges
the camera saw, and reporting how well each of them follows those edges.

Rather than measuring proportions of an outline and deciding from thresholds what shape
they suggest, each known piece is placed and turned until its own outline lies along the
edges in the picture. The set is small and every piece in it has been measured, so the
question is not *what shape is this* but *which of these four is it, where, and how is it
turned* -- a question with a far narrower answer, and one whose answer carries how well
it fitted. The board's own holes are recognised the same way, as one rigid layout (see
:class:`~experiments.montessori.hole_geometry.BoardHoleLayout`), so the sweep itself
lives in :mod:`~experiments.montessori.perception.outline_fit` and is shared.

Fitting to edges rather than to a segmented colour is what lets a piece be recognised on
a mirror-finish table (see
:mod:`~experiments.montessori.perception.edges`): the colour of a piece runs on into its
own reflection, so a coloured region says roughly where a piece is but neither how large
it is nor which one it is. The fit answers all of that at once, and every
candidate's answer is kept, so what is really standing there is settled by comparing the
accounts of that place rather than by a level one outline happened to clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from typing_extensions import List, Sequence

from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.hypotheses import PieceHypothesis
from experiments.montessori.perception.outline_fit import OutlineFitter
from experiments.montessori.pieces import KnownPiece
from experiments.montessori.planar_geometry import PlanarPoint

# %% what a fit came to


@dataclass(frozen=True, eq=False)
class MatchedPiece:
    """
    Which known piece the edges were recognised as, and where it stands.
    """

    piece: KnownPiece
    """
    The piece the edges were recognised as.
    """

    center: PlanarPoint
    """
    Where its own centre was fitted to, on the plane it stands on.
    """

    yaw: float
    """
    How far it is turned about the world frame's z-axis, in radians.

    Always the smallest turn that leaves the piece looking as it does, so a square is
    reported within an eighth of a turn of straight and a circle at zero.
    """

    outline_agreement: float
    """
    How much of this piece's own outline lay along an edge the camera saw.

    One is a perfect fit. A low value says no placement of this piece follows what is
    actually in the picture.
    """

    @property
    def outline(self) -> np.ndarray:
        """
        Where this piece's own outline lies, as ``(n, 2)`` world-frame points.
        """
        return self.piece.turned_outline(self.yaw) + np.array(
            [self.center.x, self.center.y]
        )


# %% fitting them


@dataclass(frozen=True)
class PieceMatcher:
    """
    Fits each piece a belief allows at the place it names, and says how well each of
    them followed the edges there.
    """

    fitter: OutlineFitter = field(default_factory=OutlineFitter)
    """
    Places and turns one piece over the edges.
    """

    def fits(
        self, edges: EdgeDistances, hypothesis: PieceHypothesis
    ) -> List[MatchedPiece]:
        """
        Fit every piece a hypothesis allows, best first.

        Nothing is refused here. How well an outline follows some edge says nothing about
        what put that edge there, so which fit -- if any -- is what is really standing
        there is settled by comparing the accounts of that place against each other (see
        :mod:`~experiments.montessori.perception.explanations`), and the fits this
        returns are what that comparison is made between.

        :param edges: The edges seen in the plane the piece's top face stands on.
        :param hypothesis: What is expected, and where it is believed to be.
        :return: One fit per candidate the belief allows, best-fitted first.
        """
        return sorted(
            (self._fit(piece, edges, hypothesis) for piece in hypothesis.candidates),
            key=lambda fit: fit.outline_agreement,
            reverse=True,
        )

    def match_at(
        self,
        edges: EdgeDistances,
        hypothesis: PieceHypothesis,
        angles: Sequence[float],
    ) -> List[MatchedPiece]:
        """
        Fit every piece a hypothesis allows at the one place it names, best first.

        Scores each candidate where it is said to stand instead of searching for where
        it stands, which is what makes this the cheap reading of a piece something else
        has already located. Nothing is refused here, for the reason :meth:`fits`
        records.

        :param edges: The edges seen in the plane the piece's top face stands on.
        :param hypothesis: What is expected, and the place it is believed to stand at.
        :param angles: The turns, in radians, it may be standing at.
        :return: One fit per candidate the belief allows, best-fitted first.
        """
        return sorted(
            (
                self._placed(piece, edges, hypothesis.place.center, 0.0, angles)
                for piece in hypothesis.candidates
            ),
            key=lambda fit: fit.outline_agreement,
            reverse=True,
        )

    def _fit(
        self, piece: KnownPiece, edges: EdgeDistances, hypothesis: PieceHypothesis
    ) -> MatchedPiece:
        """
        Place and turn one piece until its outline follows the edges as closely as it
        can.

        :param piece: The piece to lay over the edges.
        :param edges: The edges seen in the plane its top face stands on.
        :param hypothesis: What is believed about where it stands.
        :return: The best placement this piece reaches.
        """
        return self._placed(
            piece,
            edges,
            hypothesis.place.center,
            hypothesis.place.radius,
            hypothesis.turns_of(piece, self.fitter.coarse_angle_step),
        )

    def _placed(
        self,
        piece: KnownPiece,
        edges: EdgeDistances,
        center: PlanarPoint,
        radius: float,
        angles: Sequence[float],
    ) -> MatchedPiece:
        """
        The best placement one piece reaches over a stretch of plane and a set of turns.

        :param piece: The piece to lay over the edges.
        :param edges: The edges seen in the plane its top face stands on.
        :param center: Where on that plane the search is centred.
        :param radius: How far, in metres, it may stand from that centre.
        :param angles: The turns to try, in radians.
        """
        placement = self.fitter.fit(
            piece, edges, center=center, radius=radius, angles=angles
        )
        return MatchedPiece(
            piece=piece,
            center=placement.center,
            yaw=placement.yaw,
            outline_agreement=placement.outline_agreement,
        )
