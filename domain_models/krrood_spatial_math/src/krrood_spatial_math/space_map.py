"""
Maps that send the points of one space to the points of another.
"""

from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood_spatial_math.affine_point import CoordinateT

# %% maps from the points of one space to the points of another

PreimagePointT = TypeVar("PreimagePointT")
"""
The kind of point a space map takes, given in a coordinate system of its source space.
"""

ImagePointT = TypeVar("ImagePointT")
"""
The kind of point a space map gives, in a coordinate system of its target space.
"""

ProjectionLineT = TypeVar("ProjectionLineT")
"""
The kind of line, such as a straight line or a ray, of the source points a space map
sends to one image point.
"""


class SpaceMap(
    Generic[PreimagePointT, ImagePointT, ProjectionLineT, CoordinateT],
    SubClassSafeGeneric,
    Interface,
):
    """
    Sends each point of one space to a point of another space of lower dimension, such
    as 3D space onto a plane or onto a camera's image.

    Every image point is the image of the points on one line, its
    :meth:`projection_line`, and :meth:`unproject` picks one of them. For every image
    point ``p`` and position ``t``, ``project(unproject(p, t)) == p``.

    .. note::
        A space map relates two spaces, so it is never a coordinate change, which stays
        within one space.
    """

    @abstractmethod
    def project(self, point: PreimagePointT) -> ImagePointT:
        """
        :param point: A point of the source space.
        :return: The point of the target space ``point`` is sent to.
        """

    @abstractmethod
    def projection_line(self, point: ImagePointT) -> ProjectionLineT:
        """
        :param point: A point of the target space.
        :return: The line of every source point :meth:`project` sends to ``point``.
        """

    @abstractmethod
    def unproject(
        self, point: ImagePointT, position_along_line: CoordinateT
    ) -> PreimagePointT:
        """
        :param point: A point of the target space.
        :param position_along_line: How many direction lengths the returned point lies
            from the point the :meth:`projection_line` of ``point`` is given by.
        :return: The point at ``position_along_line`` on the :meth:`projection_line` of
            ``point``.
        """
