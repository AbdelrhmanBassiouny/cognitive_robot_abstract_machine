"""
Points of an affine space, given by their coordinates in an affine frame.
"""

from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, Self, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.mixin import Mixin
from krrood_spatial_math.coordinate_system import (
    AffineFrameT,
    CartesianFrameT,
    CoordinateRepresentation,
    CoordinateT,
)
from krrood_spatial_math.vector import VectorT

# %% points given in an affine frame


class Point(
    CoordinateRepresentation[AffineFrameT],
    Generic[AffineFrameT, CoordinateT, VectorT],
    Interface,
):
    """
    A point of an affine space, given by its amounts along an affine frame's axes from
    the frame's origin. The difference of two points is a vector, and a point moved by a
    vector is a point; two points never add up to a point.

    .. note::
        Each implementation binds every parameter once, so one kind of frame has one
        point type. The frame's space fixes how many coordinates a point has.
    """

    coordinates: tuple[CoordinateT, ...]
    """
    The amounts along the axes of the frame from its origin, one per axis, in the order
    of the axes.
    """

    @abstractmethod
    def __sub__(self, other: Self) -> VectorT:
        """
        :param other: A point given in the same frame.
        :return: The vector that moves ``other`` onto this point.
        """

    @abstractmethod
    def __add__(self, vector: VectorT) -> Self:
        """
        :param vector: A vector given in the same frame.
        :return: This point moved by ``vector``.
        """


PointT = TypeVar("PointT", bound=Point)
"""
The kind of point of an affine space.
"""


# %% points whose frame kind measures the distances between them


class MetricPoint(Point[CartesianFrameT, CoordinateT, VectorT], Mixin):
    """
    A point given in a Cartesian frame, whose distances to other points the kind of that
    frame measures.

    .. note::
        :meth:`euclidean_distance` gives the metric of
        :class:`~krrood_spatial_math.coordinate_system.CartesianFrame` on the value
        itself, so it reads like the point's own.
    """

    def euclidean_distance(self, other: Self) -> CoordinateT:
        """
        :param other: A point given in the same frame.
        :return: The straight-line distance between this point and ``other``.
        """
        frame_kind = self.get_type_of_generic_parameter(parameter=CartesianFrameT)
        return frame_kind.distance(first=self, second=other)
