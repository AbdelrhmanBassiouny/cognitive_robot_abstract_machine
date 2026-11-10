"""
Maps that send the points of one space to the points of another.
"""

from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood_spatial_math.affine_line import AffineLine
from krrood_spatial_math.affine_point import AffinePoint
from krrood_spatial_math.coordinate_system import CoordinateT

# %% maps from the points of one space to the points of another

SourcePointT = TypeVar("SourcePointT", bound=AffinePoint)
"""
The kind of point a space map takes, given in a frame of its source space.
"""

TargetPointT = TypeVar("TargetPointT", bound=AffinePoint)
"""
The kind of point a space map gives, in a frame of its target space.
"""

ProjectionLineT = TypeVar("ProjectionLineT", bound=AffineLine)
"""
The kind of line, such as a straight line or a ray, of the source points a space map
sends to one target point.
"""


class SpaceMap(
    Generic[SourcePointT, TargetPointT, ProjectionLineT, CoordinateT],
    SubClassSafeGeneric,
    Interface,
):
    """
    Sends each point of one space to a point of another space of lower dimension, such
    as 3D space onto a plane or onto a camera's image.

    Every target point is where the source points on one line, its
    :meth:`projection_line`, are sent, and :meth:`unproject` picks one of them. For
    every target point ``p`` and position ``t``, ``project(unproject(p, t)) == p``.

    .. note::
        A space map relates two spaces, so it is never a coordinate change, which stays
        within one space.
    """

    @abstractmethod
    def project(self, point: SourcePointT) -> TargetPointT:
        """
        :param point: A point of the source space.
        :return: The point of the target space ``point`` is sent to.
        """

    @abstractmethod
    def projection_line(self, point: TargetPointT) -> ProjectionLineT:
        """
        :param point: A point of the target space.
        :return: The line of every source point :meth:`project` sends to ``point``.
        """

    @abstractmethod
    def unproject(
        self, point: TargetPointT, position_along_line: CoordinateT
    ) -> SourcePointT:
        """
        :param point: A point of the target space.
        :param position_along_line: How many direction lengths the returned point lies
            from the point the :meth:`projection_line` of ``point`` is given by.
        :return: The point at ``position_along_line`` on the :meth:`projection_line` of
            ``point``.
        """


# %% projections along the normal of a plane


class OrthogonalProjection(
    SpaceMap[SourcePointT, TargetPointT, ProjectionLineT, CoordinateT], Interface
):
    """
    Sends each point of a space onto a plane in it, straight along the plane's normal.

    The :meth:`projection_line` of a point on the plane is the normal through it, whose
    direction is of unit length, so the position along that line is the height above the
    plane.
    """
