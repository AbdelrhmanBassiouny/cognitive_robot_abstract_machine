"""
Vectors of an affine space: the translations that move its points.
"""

from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, Self, TypeVar

from krrood.patterns.interface import Interface
from krrood_spatial_math.coordinate_system import (
    AffineFrameT,
    CartesianFrameT,
    CoordinateRepresentation,
    CoordinateT,
)

# %% vectors given by affine coordinates


class AffineVector(
    CoordinateRepresentation[AffineFrameT],
    Generic[AffineFrameT, CoordinateT],
    Interface,
):
    """
    A translation of an affine space, given by its amounts along the axes of an affine
    frame.

    A vector has no position: a change of frame turns its axes but never shifts it.
    """

    @abstractmethod
    def __add__(self, other: Self) -> Self:
        """
        :param other: A vector given in the same frame.
        :return: The translation by this vector followed by ``other``.
        """

    @abstractmethod
    def __sub__(self, other: Self) -> Self:
        """
        :param other: A vector given in the same frame.
        :return: The vector that ``other`` has to be followed by to give this one.
        """

    @abstractmethod
    def __mul__(self, factor: CoordinateT) -> Self:
        """
        :param factor: The number every coordinate is multiplied by.
        :return: This vector stretched by ``factor``.
        """


AffineVectorT = TypeVar("AffineVectorT", bound=AffineVector)
"""
The kind of vector the points of an affine space are moved by.
"""


class CartesianVector(AffineVector[CartesianFrameT, CoordinateT], Interface):
    """
    A vector given in a Cartesian frame, whose orthonormal axes measure lengths and
    angles.
    """

    @abstractmethod
    def norm(self) -> CoordinateT:
        """
        :return: The length of this vector.
        """

    @abstractmethod
    def dot(self, other: Self) -> CoordinateT:
        """
        :param other: A vector given in the same frame.
        :return: The product of both lengths and the cosine of the angle between them.
        """


CartesianVectorT = TypeVar("CartesianVectorT", bound=CartesianVector)
"""
The kind of vector the points of a Euclidean space are moved by.
"""
