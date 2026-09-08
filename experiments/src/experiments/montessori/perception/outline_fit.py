"""
Find where a known outline stands, by laying it over the edges the camera saw.

Everything this scene recognises is something whose shape is already known exactly: the
loose pieces have been measured, and the board's holes are cut into a mesh the robot
carries. So recognising one is placing it, and the answer to *where* is whichever
placement follows the seen edges best -- which is a search over positions and turns
rather than a reading of proportions.

The search runs twice: once coarsely and forgivingly over everything a belief allows,
and once finely around the placement that came back. How far the coarse search reaches
and which turns it tries are read from that belief, so a place known closely costs a
fraction of what an unguided pass over the same surface costs.
"""

from __future__ import annotations

from dataclasses import dataclass

import math

import numpy as np
from typing_extensions import List, Sequence

from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.planar_geometry import KnownOutline, PlanarPoint

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


# %% where a known outline turned out to stand


@dataclass(frozen=True, eq=False)
class Placement:
    """
    Where a known outline was fitted to, and how well the picture bore it out.
    """

    center: PlanarPoint
    """
    Where its own origin was fitted to, on the plane it lies in.
    """

    yaw: float
    """
    How far it is turned about the world frame's z-axis, in radians.

    Always the smallest turn that leaves it looking as it does, so a square is reported
    within an eighth of a turn of straight and a circle at zero.
    """

    outline_agreement: float
    """
    How much of its outline lay along an edge the camera saw.

    One is a perfect fit. A low value says no placement of it follows what is actually
    in the picture.
    """


# %% searching for it


@dataclass(frozen=True)
class OutlineFitter:
    """
    Places and turns a known outline until it follows the seen edges as closely as it
    can.
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
    How finely an outline is turned in the first search, in radians.
    """

    angle_step: float = math.radians(2.0)
    """
    How finely an outline is turned in the second search, in radians.

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

    coarse_outline_spacing: float = 0.002
    """
    How far apart those points stand in the first search.

    The coarse search only has to say which placement to look around, so an outline that
    covers hundreds of points can be compared at a fraction of them; one small enough
    that the saving does not matter leaves this at :attr:`outline_spacing`.
    """

    def fit(
        self,
        outline: KnownOutline,
        edges: EdgeDistances,
        center: PlanarPoint,
        radius: float,
        angles: Sequence[float],
    ) -> Placement:
        """
        Place and turn one known outline until it follows the edges as closely as it
        can.

        :param outline: The outline to lay over the edges.
        :param edges: The edges seen in the plane it lies in.
        :param center: Where on that plane it is believed to be.
        :param radius: How far, in metres, from that centre it may actually be.
        :param angles: The turns worth trying, in radians.
        :return: The best placement it reaches.
        """
        coarse = self._sweep(
            outline,
            edges,
            center,
            angles,
            radius,
            self.coarse_step,
            self.coarse_reach,
            self.coarse_outline_spacing,
        )
        return self._sweep(
            outline,
            edges,
            coarse.center,
            self._turns_around(outline, coarse.yaw),
            self.coarse_step,
            self.step,
            self.reach,
            self.outline_spacing,
        )

    def _sweep(
        self,
        outline: KnownOutline,
        edges: EdgeDistances,
        center: PlanarPoint,
        angles: Sequence[float],
        radius: float,
        step: float,
        reach: float,
        spacing: float,
    ) -> Placement:
        """
        Try one outline at every placement of a grid of positions and turns.

        :param outline: The outline to place.
        :param edges: The edges seen in the plane it lies in.
        :param center: Where on the plane the grid is centred.
        :param angles: The turns to try, in radians.
        :param radius: How far, in metres, the grid reaches from its centre.
        :param step: How far apart, in metres, the grid's positions stand.
        :param reach: How far an edge may lie from the outline and still count.
        :param spacing: How far apart the points the outline is compared at stand.
        :return: The best placement.
        """
        positions = self._lattice_across(center, radius, step)
        return max(
            (
                self._best_position(outline, edges, positions, angle, reach, spacing)
                for angle in angles
            ),
            key=lambda placement: placement.outline_agreement,
        )

    @staticmethod
    def _lattice_across(center: PlanarPoint, radius: float, step: float) -> np.ndarray:
        """
        The positions a search tries across a stretch of plane it was pointed at.

        The whole stretch is walked, out to the radius itself, because a radius given
        here says how far the search may move rather than how far the thing is believed
        to be -- the board's seed is the middle of whatever the lighting made dark, and
        the fit has to be able to reach the board from it.

        :param center: Where on the plane the search is pointed.
        :param radius: How far, in metres, it may move from there.
        :param step: How far apart, in metres, the positions stand.
        :return: The world-frame ``(n, 2)`` positions.
        """
        walk = np.arange(-radius, radius + step / 2, step)
        return np.stack(np.meshgrid(walk, walk, indexing="ij"), axis=-1).reshape(
            -1, 2
        ) + np.array([center.x, center.y])

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
        outline: KnownOutline,
        edges: EdgeDistances,
        positions: np.ndarray,
        angle: float,
        reach: float,
        spacing: float,
    ) -> Placement:
        """
        Where an outline turned to one angle follows the edges best.

        :param outline: The outline to place.
        :param edges: The edges seen in the plane it lies in.
        :param positions: The world-frame ``(n, 2)`` positions to try it at.
        :param angle: The turn to try it at, in radians.
        :param reach: How far an edge may lie from the outline and still count.
        :param spacing: How far apart the points the outline is compared at stand.
        :return: The best of those positions.
        """
        points = outline.outline_points(angle, spacing)
        agreements = edges.agreement(points[None, :, :] + positions[:, None, :], reach)
        best = int(np.argmax(agreements))
        return Placement(
            center=PlanarPoint(
                x=float(positions[best][0]), y=float(positions[best][1])
            ),
            yaw=outline.smallest_equivalent_turn(angle),
            outline_agreement=float(agreements[best]),
        )

    def _turns_around(self, outline: KnownOutline, angle: float) -> List[float]:
        """
        The turns worth trying either side of one the coarse search settled on, which
        reach a full coarse step in both directions.

        Refining a turn the coarse sweep already chose from what the belief allowed,
        rather than a second reading of the belief itself. An outline no turn changes
        answers with the one turn every candidate is equivalent to.

        :param outline: The outline to turn.
        :param angle: The turn to search around, in radians.
        """
        steps = int(round(self.coarse_angle_step / self.angle_step))
        turns = [
            outline.smallest_equivalent_turn(angle + offset * self.angle_step)
            for offset in range(-steps, steps + 1)
        ]
        return list(dict.fromkeys(turns))
