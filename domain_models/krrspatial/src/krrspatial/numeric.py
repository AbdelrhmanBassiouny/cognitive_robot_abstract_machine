"""
Spatial types whose coordinates are plain numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from typing_extensions import Generic, Self, TypeVar, overload

from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

from krrspatial.exceptions import DifferentReferenceFrames
from krrspatial.reference_frame import ReferenceFrame
from krrspatial.spatial_types import (
    CoordinateT,
    Coordinates2,
    Point2,
    SpatialType,
    Vector2,
)

# %% coordinates along two axes


@dataclass
class NumericCoordinates2(Coordinates2[CoordinateT]):
    """
    A spatial object in a plane that stores its two coordinates as numbers.
    """

    x: CoordinateT
    """
    The coordinate along the first axis.
    """

    y: CoordinateT
    """
    The coordinate along the second axis.
    """

    reference_frame: ReferenceFrame | None = None
    """
    The frame its coordinates are expressed in; none if it is not tied to one.
    """

    def _ensure_same_reference_frame(self, other: SpatialType) -> None:
        """
        :param other: The object this one is combined with.
        :raises DifferentReferenceFrames: If the two are expressed in different frames.
        """
        if other.reference_frame != self.reference_frame:
            raise DifferentReferenceFrames(self, other)


# %% directions in a plane


@dataclass
class NumericVector2(NumericCoordinates2[CoordinateT], Vector2[CoordinateT]):
    """
    A direction and length in a plane, as numbers.
    """

    def __add__(self, other: Self) -> Self:
        """
        :param other: The vector to add.
        :return: The sum of both vectors.
        """
        self._ensure_same_reference_frame(other)
        return type(self)(self.x + other.x, self.y + other.y, self.reference_frame)

    def __sub__(self, other: Self) -> Self:
        """
        :param other: The vector to subtract.
        :return: The difference of both vectors.
        """
        self._ensure_same_reference_frame(other)
        return type(self)(self.x - other.x, self.y - other.y, self.reference_frame)

    def __neg__(self) -> Self:
        """
        :return: The vector of the same length pointing the opposite way.
        """
        return type(self)(-self.x, -self.y, self.reference_frame)


@dataclass
class FloatVector2(NumericVector2[float]):
    """
    A direction and length in a plane, anywhere between whole numbers.
    """

    def norm(self) -> float:
        """
        :return: Its Euclidean length.
        """
        return math.hypot(self.x, self.y)


@dataclass
class IntegerVector2(NumericVector2[int]):
    """
    A direction and length in a plane, in whole steps along each axis.
    """


# %% positions in a plane

VectorT = TypeVar("VectorT", bound=NumericVector2)


@dataclass
class NumericPoint2(
    NumericCoordinates2[CoordinateT],
    Point2[CoordinateT],
    Generic[CoordinateT, VectorT],
    SubClassSafeGeneric,
):
    """
    A position in a plane, as numbers, whose differences are vectors of the bound vector
    type.
    """

    def __add__(self, offset: VectorT) -> Self:
        """
        :param offset: How far to move.
        :return: The position that far from this one.
        """
        self._ensure_same_reference_frame(offset)
        return type(self)(self.x + offset.x, self.y + offset.y, self.reference_frame)

    @overload
    def __sub__(self, other: Self) -> VectorT: ...

    @overload
    def __sub__(self, other: VectorT) -> Self: ...

    def __sub__(self, other: Self | VectorT) -> VectorT | Self:
        """
        :param other: A position, or how far to move back.
        :return: The vector from the given position to this one, or the position that
            far back from this one.
        """
        self._ensure_same_reference_frame(other)
        if isinstance(other, NumericVector2):
            return type(self)(self.x - other.x, self.y - other.y, self.reference_frame)
        vector_type = self.get_type_of_generic_parameter(VectorT)
        return vector_type(self.x - other.x, self.y - other.y, self.reference_frame)


@dataclass
class FloatPoint2(NumericPoint2[float, FloatVector2]):
    """
    A position in a plane, anywhere between whole numbers.
    """


@dataclass
class IntegerPoint2(NumericPoint2[int, IntegerVector2]):
    """
    A position in a plane at whole numbers along each axis, such as a pixel.
    """

    @classmethod
    def nearest(cls, point: FloatPoint2) -> IntegerPoint2:
        """
        :param point: A position anywhere between whole numbers.
        :return: The whole-number position nearest to it, in its frame.
        """
        return cls(round(point.x), round(point.y), point.reference_frame)
