"""
Points of an affine space, given by their coordinates in an affine frame.
"""

from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, Self, TypeVar

from krrood.patterns.interface import Interface
from krrood_spatial_math.affine_vector import AffineVectorT, CartesianVectorT
from krrood_spatial_math.coordinate_system import (
    AffineFrameT,
    CartesianFrameT,
    CoordinateRepresentation,
    CoordinateT,
)

# %% points given by affine coordinates


class AffinePoint(
    CoordinateRepresentation[AffineFrameT],
    Generic[AffineFrameT, CoordinateT, AffineVectorT],
    Interface,
):
    """
    A point given by its coordinates in an affine frame: its amounts along the frame's
    axes from the frame's origin, one per axis of the frame.

    The difference of two points is a vector, and a point moved by a vector is a point;
    two points never add up to a point.

    .. note::
        Each implementation binds every parameter once, so one kind of frame has one
        point type. The frame's space fixes how many coordinates a point has.
    """

    @abstractmethod
    def __sub__(self, other: Self) -> AffineVectorT:
        """
        :param other: A point given in the same frame.
        :return: The vector that moves ``other`` onto this point.
        """

    @abstractmethod
    def __add__(self, vector: AffineVectorT) -> Self:
        """
        :param vector: A vector given in the same frame.
        :return: This point moved by ``vector``.
        """


AffinePointT = TypeVar("AffinePointT", bound=AffinePoint)
"""
The kind of point of an affine space.
"""


class CartesianPoint(
    AffinePoint[CartesianFrameT, CoordinateT, CartesianVectorT], Interface
):
    """
    A point given in a Cartesian frame, whose orthonormal axes measure distances.
    """

    @abstractmethod
    def euclidean_distance(self, other: Self) -> CoordinateT:
        """
        :param other: A point given in the same frame.
        :return: The straight-line distance between this point and ``other``.
        """
