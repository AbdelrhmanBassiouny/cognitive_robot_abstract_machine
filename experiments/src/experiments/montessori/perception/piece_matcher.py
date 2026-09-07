"""
Recognise a loose piece by laying the pieces this set is known to contain over the edges
the camera saw, and keeping the one that follows them best.

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
it is nor which one it is. The fit answers all of that at once, and refuses an outline no
known piece follows instead of reporting whichever threshold it happened to fall between.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Optional

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


# %% fitting them


@dataclass(frozen=True)
class PieceMatcher:
    """
    Recognises the piece standing at a believed place, by fitting each piece the belief
    allows and keeping whichever followed the edges best.
    """

    minimum_agreement: float = 0.62
    """
    How much of a piece's outline must lie along a seen edge before it is reported at
    all.

    On the real table a correctly recognised piece reaches between 0.63 and 0.86, while
    the best any *other* piece of the same colour reaches on the same spot is 0.62; this
    sits at that boundary, so a piece is refused rather than reported as its neighbour.
    """

    fitter: OutlineFitter = field(default_factory=OutlineFitter)
    """
    Places and turns one piece over the edges.
    """

    def match(
        self, edges: EdgeDistances, hypothesis: PieceHypothesis
    ) -> Optional[MatchedPiece]:
        """
        Recognise the piece a hypothesis expects, where it expects it.

        :param edges: The edges seen in the plane the piece's top face stands on.
        :param hypothesis: What is expected, and where it is believed to be.
        :return: The best fit, or None if no expected piece follows the edges well
            enough.
        """
        if not hypothesis.candidates:
            return None
        best = max(
            (self._fit(piece, edges, hypothesis) for piece in hypothesis.candidates),
            key=lambda fit: fit.outline_agreement,
        )
        if best.outline_agreement < self.minimum_agreement:
            return None
        return best

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
        placement = self.fitter.fit(
            piece,
            edges,
            center=hypothesis.place.center,
            radius=hypothesis.place.radius,
            angles=hypothesis.turns_of(piece, self.fitter.coarse_angle_step),
        )
        return MatchedPiece(
            piece=piece,
            center=placement.center,
            yaw=placement.yaw,
            outline_agreement=placement.outline_agreement,
        )
