"""
The plane a depth image measures through a horizontal surface.

Where a camera stands is stated by the world and is only as good as the calibration it
was written down from; the table the camera looks at is flat and at a known height
whatever that calibration says. Fitting a plane through the points the depth image
measures at the table, in the frame the stated pose reports them in, therefore checks
the pose itself: a table that comes out tilted, or at the wrong height, is a camera pose
that is wrong by that tilt and that height.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from typing_extensions import Self

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.exceptions import (
    SurfaceNotSeenWhereTheWorldPutsIt,
)
from experiments.montessori.perception.surface_finding import MeasuredSurfaceFinder
from experiments.montessori.perception.surfaces import WorkspaceSurface

OUTLIER_SCATTER = 2.0
"""
How many times the points' typical scatter from the fitted plane a point may lie before
the next pass of the fit leaves it out.

Two rather than the customary three, because what is left out is not noise but a robot
arm or a board standing over the surface, whose points lie to one side of the plane and
pull it that way as long as any of them are kept.
"""

MEDIAN_TO_STANDARD_DEVIATION = 1.4826
"""
What the median absolute deviation of normally scattered values is multiplied by to
read as their standard deviation.
"""

FITTING_PASSES = 5
"""
How many times the plane is refitted with the outliers of the pass before left out.

Pieces standing on the surface and the odd bad depth reading are a small part of the
points and lie well off the plane, so a few passes are enough to fit the surface itself
rather than what rests on it; an arm reaching over the table takes a couple more,
measured on the capture that has one.
"""

NEGLIGIBLE_SCATTER = 1e-6
"""
A scatter, in metres, below which every point lies on the plane and nothing is left out.
"""

POSE_DRIFT = 0.15
"""
How far, in metres, a surface may stand from where the world puts it and still be read
as that surface when a camera pose is being checked.

Wide enough to hold the whole of a table a stated pose tilts by ten degrees or more,
since a band no wider than the depth noise keeps only the strip of such a table that
happens to cross the stated plane, and a plane fitted to that strip reads as level.
"""

VERTICAL = np.array([0.0, 0.0, 1.0])
"""
The direction a horizontal surface's normal points, in the frame poses are reported in.
"""


@dataclass(frozen=True)
class MeasuredPlane:
    """
    A plane fitted through measured points, in the frame the points were given in.
    """

    normal: np.ndarray
    """
    The plane's unit normal, pointing upward.
    """

    centroid: np.ndarray
    """
    The mean of the points it was fitted through, which lies on the plane.
    """

    residual: float
    """
    How far the points scatter from the plane, in metres: the median of their distances
    from it, read as a standard deviation.

    A median rather than a mean, so that a board or an arm standing in the band the
    points were read from does not widen the scatter the table's own points are judged
    against.
    """

    @property
    def tilt(self) -> float:
        """
        How far the plane leans from horizontal, in degrees.
        """
        return float(np.degrees(np.arccos(np.clip(self.normal @ VERTICAL, -1.0, 1.0))))

    @property
    def height(self) -> float:
        """
        How high the plane stands at its centroid, in metres.
        """
        return float(self.centroid[2])

    @classmethod
    def fit(
        cls,
        points: np.ndarray,
        outlier_scatter: float = OUTLIER_SCATTER,
        passes: int = FITTING_PASSES,
    ) -> Self:
        """
        Fit a plane through points, leaving out the outliers of each pass in the next.

        :param points: The points, shape ``(n, 3)``.
        :param outlier_scatter: How many standard deviations from the plane a point may
            lie before the next pass leaves it out.
        :param passes: How many times to refit.
        :return: The plane of the last pass.
        """
        kept = np.asarray(points, dtype=float).reshape(-1, 3)
        plane = cls._fit_once(kept)
        for _ in range(passes - 1):
            if plane.residual < NEGLIGIBLE_SCATTER:
                return plane
            distance = (kept - plane.centroid) @ plane.normal
            kept = kept[np.abs(distance) <= outlier_scatter * plane.residual]
            plane = cls._fit_once(kept)
        return plane

    @classmethod
    def _fit_once(cls, points: np.ndarray) -> Self:
        """
        The least-squares plane through points, with no outlier left out.

        :param points: The points, shape ``(n, 3)``.
        """
        centroid = points.mean(axis=0)
        _, _, rows = np.linalg.svd(points - centroid, full_matrices=False)
        normal = rows[2] if rows[2] @ VERTICAL >= 0.0 else -rows[2]
        distance = (points - centroid) @ normal
        return cls(
            normal=normal,
            centroid=centroid,
            residual=float(MEDIAN_TO_STANDARD_DEVIATION * np.median(np.abs(distance))),
        )

    @classmethod
    def of_surface(
        cls,
        frame: RgbdFrame,
        surface: WorkspaceSurface,
        scatter: float = POSE_DRIFT,
    ) -> Self:
        """
        The plane the depth image measures where the world puts a surface.

        Read in the frame the camera's stated pose reports points in, so a surface the
        world calls horizontal comes out tilted exactly as far as that pose is wrong.
        Whatever else stands within the band read -- pieces, a board -- is a small part
        of the points and far from the plane, and the fit leaves it out.

        :param frame: The camera data to read, carrying the camera's stated pose.
        :param surface: The surface as the world models it, which says where to read.
        :param scatter: How far a point may lie from the modelled plane and still be
            read as the surface's own, in metres.
        :raises SurfaceNotSeenWhereTheWorldPutsIt: If nothing stands at the modelled
            plane inside the surface's stretch.
        """
        points = MeasuredSurfaceFinder(scatter=scatter).points_standing_at(
            surface, frame
        )
        if not len(points):
            raise SurfaceNotSeenWhereTheWorldPutsIt(str(surface.name), surface.height)
        return cls.fit(points)
