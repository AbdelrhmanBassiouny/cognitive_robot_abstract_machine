"""
What else could have produced the edges seen where a thing might stand.

How much of an outline lies along a seen edge says how well that outline follows *some*
edge, and nothing about what put the edge there. Near the board that is not enough to
recognise anything by: the lid's border and the rims of its holes are long, sharp edges
that a piece template follows as closely as a real piece does, and measured on the
shipped captures a triangular prism laid on the board's middle reaches a higher figure
than every genuine piece resting on the lid. No level set on that figure separates them.

What does separate them is asking, of the edges actually seen at one place, which
account of them the picture bears out best. An account is read from both sides -- how
much of its own outline the picture holds an edge along, and how much of the edge there
its outline covers -- so an outline that follows part of a rim while leaving the rest of
it unaccounted for is weaker than one that covers the whole of it, however well its own
points sit. And the board is one of the accounts, since everything its own geometry
produces is known before anything is looked for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from typing_extensions import Self, Sequence

from experiments.montessori.perception.edges import EdgeDistances
from experiments.montessori.planar_geometry import points_along

# %% one account of one place


@dataclass(frozen=True)
class Explanation:
    """
    One account of what put the edges seen where a thing might stand.
    """

    outline_followed: float
    """
    How much of the account's own outline lies along an edge the camera saw.
    """

    edges_accounted_for: float
    """
    How much of the edge seen at that place lies along the account's outline.

    The half a fit's own agreement never asks. An account may follow the edges it stands
    on perfectly and still leave most of what is there unexplained, which is what a
    piece template laid across part of a hole's rim does.
    """

    @property
    def strength(self) -> float:
        """
        How well the account explains the picture, read from both sides at once.

        Their harmonic mean, so an account is held to whichever side it is weaker on:
        one that claims outline where nothing is, and one that leaves seen edges
        unaccounted for, are both wrong and in the same measure.
        """
        both = self.outline_followed + self.edges_accounted_for
        if both == 0.0:
            return 0.0
        return 2.0 * self.outline_followed * self.edges_accounted_for / both


NOTHING_EXPLAINED = Explanation(outline_followed=0.0, edges_accounted_for=0.0)
"""
The account that says nothing is there, which explains no edge and claims no outline.
"""


# %% the edges seen at one place


@dataclass(frozen=True)
class PlaceInThePicture:
    """
    The edges one look found where a thing might stand, and the reach every account of
    them is read at.

    Every account of one place is scored over the same edges, which is what makes two of
    them comparable: an account read over a wider stretch of picture than its rival would
    be answering an easier or a harder question rather than the same one.
    """

    edges: EdgeDistances
    """
    How far each point of the plane lies from the nearest edge seen in it.
    """

    seen_here: np.ndarray
    """
    Where the edges at this place stand, as ``(n, 2)`` world-frame points.
    """

    reach: float
    """
    How far, in metres, an outline and an edge may lie apart and still count as one.
    """

    outline_spacing: float
    """
    How far apart, in metres, the points an outline is read at stand.
    """

    middle: np.ndarray
    """
    Where the place is centred, as a world-frame ``(x, y)`` point.
    """

    span: float
    """
    How far, in metres, the place reaches from its middle.
    """

    @classmethod
    def around(
        cls,
        outline: np.ndarray,
        edges: EdgeDistances,
        seen: np.ndarray,
        reach: float,
        outline_spacing: float,
    ) -> Self:
        """
        The place one outline stands in: as far from its middle as the outline itself
        reaches, and the reach beyond that.

        :param outline: The outline that raises the place, as ``(n, 2)`` world-frame
            points.
        :param edges: The edges seen in the plane it lies in.
        :param seen: Where every edge in that plane stands, as ``(n, 2)`` world-frame
            points.
        :param reach: How far an outline and an edge may lie apart and still count as
            one, in metres.
        :param outline_spacing: How far apart the points an outline is read at stand.
        """
        middle = outline.mean(axis=0)
        span = float(np.linalg.norm(outline - middle, axis=1).max()) + reach
        return cls(
            edges=edges,
            seen_here=seen[np.linalg.norm(seen - middle, axis=1) <= span],
            reach=reach,
            outline_spacing=outline_spacing,
            middle=middle,
            span=span,
        )

    def holds(self, points: np.ndarray) -> np.ndarray:
        """
        Those of some points that stand in this place.

        :param points: World-frame ``(n, 2)`` points.
        """
        return points[np.linalg.norm(points - self.middle, axis=1) <= self.span]

    def explained_by(self, outline: np.ndarray) -> Explanation:
        """
        How well one outline accounts for the edges seen here.

        :param outline: The outline to lay over them, as ``(n, 2)`` world-frame corners.
        """
        if len(outline) == 0:
            return NOTHING_EXPLAINED
        return self.explained_by_points(points_along(outline, self.outline_spacing))

    def explained_by_points(self, points: np.ndarray) -> Explanation:
        """
        How well a set of outline points accounts for the edges seen here.

        :param points: World-frame ``(n, 2)`` points already spread along an outline.
        """
        if len(points) == 0:
            return NOTHING_EXPLAINED
        return Explanation(
            outline_followed=float(self.edges.agreement(points, self.reach)),
            edges_accounted_for=self._covered_by(points),
        )

    def _covered_by(self, points: np.ndarray) -> float:
        """
        How much of the edge seen here lies along a set of points.

        :param points: World-frame ``(n, 2)`` points of an account's outline.
        """
        if len(self.seen_here) == 0:
            return 0.0
        gaps = np.linalg.norm(
            self.seen_here[:, None, :] - points[None, :, :], axis=2
        ).min(axis=1)
        return float(np.clip(1.0 - gaps / self.reach, 0.0, None).mean())


# %% the outlines the board itself produces


@dataclass(frozen=True)
class BoardOutlines:
    """
    Where the board's own geometry puts an outline in one rectified plane.

    The lid's border and each hole cut through it are in the picture whether or not
    anything rests on the board, and where they are is known exactly once the board's
    layout has been fitted -- so an outline that follows one of them is accounted for by
    the board rather than by a piece.
    """

    corners: Sequence[np.ndarray] = ()
    """
    One ``(n, 2)`` world-frame outline per thing the board produces an edge along.
    """

    @classmethod
    def cast_onto(
        cls,
        outlines: Sequence[np.ndarray],
        lying_at: float,
        plane_height: float,
        seen_from: np.ndarray,
    ) -> Self:
        """
        Where outlines lying in one plane fall in a rectification onto another.

        A rectification onto a plane above the board places the board's own edges where
        the camera sees them against that plane, so they are cast onto it from where the
        camera stands -- the same reading of a raised thing's line of sight that
        :meth:`~experiments.montessori.perception.occupancy.OccupiedVolume.hides` takes
        from the other side.

        :param outlines: The outlines, each ``(n, 2)`` world-frame points.
        :param lying_at: Height of the plane they lie in, in metres.
        :param plane_height: Height of the plane they are wanted in, in metres.
        :param seen_from: Where the camera stands, as world-frame ``(x, y, z)``.
        """
        reach = (plane_height - seen_from[2]) / (lying_at - seen_from[2])
        return cls(
            corners=[
                seen_from[:2]
                + (np.asarray(outline, dtype=float) - seen_from[:2]) * reach
                for outline in outlines
            ]
        )

    def account_of(self, place: PlaceInThePicture) -> Explanation:
        """
        How well the board alone accounts for the edges seen at one place.

        Only the stretch of the board's own outlines that passes through the place is
        read, since an account is judged on the edges it stands over rather than on how
        much of the board it belongs to.

        :param place: The place to account for.
        """
        if not self.corners:
            return NOTHING_EXPLAINED
        points = place.holds(
            np.vstack(
                [
                    points_along(outline, place.outline_spacing)
                    for outline in self.corners
                ]
            )
        )
        return place.explained_by_points(points)


# %% deciding by comparison rather than by level


@dataclass(frozen=True)
class CompetingExplanations:
    """
    Settles what is reported at a place by comparing the accounts of it against each
    other, rather than by measuring one of them against a fixed level.
    """

    required_lead: float = 0.075
    """
    How much better an account must explain a place than the next before it is reported.

    What is stated here is a cost rather than a level: on this scene a wrong report and a
    piece not reported cost about the same -- a ghost is acted on once, a missed piece is
    looked for again on the next frame -- and this is the lead that follows from saying
    so, measured over the shipped captures. Telling the robot that a wrong report costs
    more raises it; the two are traded against each other monotonically, which
    ``test_montessori_detection_on_captures.py`` keeps answerable against the real
    camera rather than only asserted.
    """

    def is_reported(self, candidate: Explanation, *rivals: Explanation) -> bool:
        """
        Whether one account of a place is what the picture says is there.

        The account that says nothing is there is always among the rivals, so an account
        that explains next to nothing is refused without a level being set on it
        separately.

        :param candidate: The account being asked about.
        :param rivals: The other accounts of the same place.
        """
        return all(
            candidate.strength - rival.strength >= self.required_lead
            for rival in [NOTHING_EXPLAINED, *rivals]
        )

    def leads(self, candidate: Explanation, rival: Explanation) -> bool:
        """
        Whether one account of a place is clearly better than another.

        :param candidate: The account being asked about.
        :param rival: The account it is asked to beat.
        """
        return candidate.strength - rival.strength >= self.required_lead
