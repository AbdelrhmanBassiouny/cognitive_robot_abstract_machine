"""
Recognise a loose piece by laying the pieces this set is known to contain over the edges
the camera saw, and keeping the one that follows them best.

Rather than measuring proportions of an outline and deciding from thresholds what shape
they suggest (which is how the holes in the board's lid are still read, see
:class:`~experiments.montessori.perception.footprint.CrossSectionClassifier`), each known
piece is placed and turned until its own outline lies along the edges in the picture. The
set is small and every piece in it has been measured, so the question is not *what shape
is this* but *which of these four is it, where, and how is it turned* -- a question with
a far narrower answer, and one whose answer carries how well it fitted.

Fitting to edges rather than to a segmented colour is what lets a piece be recognised on
a mirror-finish table (see
:mod:`~experiments.montessori.perception.edges`): the colour of a piece runs on into its
own reflection, so a coloured region says roughly where a piece is but neither how large
it is nor which one it is. The fit answers all of that at once, and refuses an outline no
known piece follows instead of reporting whichever threshold it happened to fall between.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from typing_extensions import List, Optional, Sequence

from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.perception.hypotheses import PieceHypothesis
from experiments.montessori.pieces import KnownPiece, points_along
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


# %% the grid a sweep walks


def offsets_within(radius: float, step: float) -> np.ndarray:
    """
    The offsets a sweep tries either side of the place it is centred on.

    Counted outwards from that centre rather than inwards from the edge of the reach, so
    that widening the reach only *adds* placements: a grid laid out from its own edge is
    re-phased by every change to how far it reaches, and a peak one reach lands on the
    next steps over. That shows up as an answer that is not monotonic in the reach,
    which is the same giveaway a rectification re-framed off its own lattice gives, and
    it went unseen while every belief reached exactly as far as every other.

    A reach is a bound rather than a suggestion, so the grid stops inside it: a belief
    says a thing is no further than this from the place it names.

    :param radius: How far, in metres, the grid reaches from its centre.
    :param step: How far apart, in metres, the grid's positions stand.
    :return: The offsets, in metres, in increasing order.
    """
    outwards = np.arange(int(radius / step) + 1) * step
    return np.concatenate([-outwards[:0:-1], outwards])


# %% fitting them


@dataclass(frozen=True)
class PieceMatcher:
    """
    Recognises the piece standing at a believed place.

    The search runs twice: once coarsely and forgivingly, over everything the belief
    allows, and once finely around the placement that came back, to settle its position
    and its turn. How far the coarse search reaches, which turns it tries and which
    pieces it tries there are all read from the belief, so a place known closely costs a
    fraction of what an unguided pass over the same surface costs.
    """

    minimum_agreement: float = 0.62
    """
    How much of a piece's outline must lie along a seen edge before it is reported at
    all.

    On the real table a correctly recognised piece reaches between 0.63 and 0.86, while
    the best any *other* piece of the same colour reaches on the same spot is 0.62; this
    sits at that boundary, so a piece is refused rather than reported as its neighbour.
    """

    coarse_step: float = 0.003
    """
    How far apart, in metres, the placements of the first search stand.
    """

    step: float = 0.001
    """
    How far apart, in metres, the placements of the second search stand, matching the
    rectified image's own resolution.
    """

    coarse_angle_step: float = math.radians(6.0)
    """
    How finely a piece is turned in the first search, in radians.
    """

    angle_step: float = math.radians(2.0)
    """
    How finely a piece is turned in the second search, in radians.

    Two degrees moves the far corner of the largest piece here by under a millimetre, so
    a finer sweep would be answering below the resolution the edges were found at.
    """

    coarse_reach: float = 0.008
    """
    How far, in metres, an edge may lie from an outline and still count in the first
    search.

    Wide on purpose: the first search only has to find which placement to look around,
    and a reach narrower than the step it walks in would step over the answer.
    """

    reach: float = 0.003
    """
    How far, in metres, an edge may lie from an outline and still count in the second
    search.
    """

    outline_spacing: float = 0.002
    """
    How far apart, in metres, the points an outline is compared to the picture at stand.
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
        coarse = self._sweep(
            piece,
            edges,
            hypothesis.place.center,
            hypothesis.turns_of(piece, self.coarse_angle_step),
            hypothesis.place.radius,
            self.coarse_step,
            self.coarse_reach,
        )
        return self._sweep(
            piece,
            edges,
            coarse.center,
            self._turns_around(piece, coarse.yaw),
            self.coarse_step,
            self.step,
            self.reach,
        )

    def _sweep(
        self,
        piece: KnownPiece,
        edges: EdgeDistances,
        center: PlanarPoint,
        angles: Sequence[float],
        radius: float,
        step: float,
        reach: float,
    ) -> MatchedPiece:
        """
        Try one piece at every placement of a grid of positions and turns.

        :param piece: The piece to place.
        :param edges: The edges seen in the plane its top face stands on.
        :param center: Where on the plane the grid is centred.
        :param angles: The turns to try, in radians.
        :param radius: How far, in metres, the grid reaches from its centre.
        :param step: How far apart, in metres, the grid's positions stand.
        :param reach: How far an edge may lie from the outline and still count.
        :return: The best placement.
        """
        positions = self.placements_within(center, radius, step)
        return max(
            (
                self._best_position(piece, edges, positions, angle, reach)
                for angle in angles
            ),
            key=lambda fit: fit.outline_agreement,
        )

    @staticmethod
    def placements_within(
        center: PlanarPoint, radius: float, step: float
    ) -> np.ndarray:
        """
        The positions a sweep tries about the place it is centred on.

        Laid out from that centre outwards along both axes, so that widening the reach
        only adds positions and the answer is monotonic in it.

        :param center: Where on the plane the grid is centred.
        :param radius: How far, in metres, the grid reaches from its centre.
        :param step: How far apart, in metres, the grid's positions stand.
        :return: The world-frame ``(n, 2)`` positions, the centre among them.
        """
        walk = offsets_within(radius, step)
        return np.stack(np.meshgrid(walk, walk, indexing="ij"), axis=-1).reshape(
            -1, 2
        ) + np.array([center.x, center.y])

    def _best_position(
        self,
        piece: KnownPiece,
        edges: EdgeDistances,
        positions: np.ndarray,
        angle: float,
        reach: float,
    ) -> MatchedPiece:
        """
        Where a piece turned to one angle follows the edges best.

        :param piece: The piece to place.
        :param edges: The edges seen in the plane its top face stands on.
        :param positions: The world-frame ``(n, 2)`` positions to try it at.
        :param angle: The turn to try it at, in radians.
        :param reach: How far an edge may lie from the outline and still count.
        :return: The best of those positions.
        """
        outline = points_along(piece.turned_outline(angle), self.outline_spacing)
        agreements = edges.agreement(outline[None, :, :] + positions[:, None, :], reach)
        best = int(np.argmax(agreements))
        return MatchedPiece(
            piece=piece,
            center=PlanarPoint(
                x=float(positions[best][0]), y=float(positions[best][1])
            ),
            yaw=piece.smallest_equivalent_turn(angle),
            outline_agreement=float(agreements[best]),
        )

    def _turns_around(self, piece: KnownPiece, angle: float) -> List[float]:
        """
        The turns worth trying either side of one the coarse search settled on, which
        reach a full coarse step in both directions.

        Refining a turn the coarse sweep already chose from what the belief allowed,
        rather than a second reading of the belief itself.

        :param piece: The piece to turn.
        :param angle: The turn to search around, in radians.
        """
        if piece.rotation_period is None:
            return [0.0]
        steps = int(round(self.coarse_angle_step / self.angle_step))
        return list(angle + np.arange(-steps, steps + 1) * self.angle_step)
