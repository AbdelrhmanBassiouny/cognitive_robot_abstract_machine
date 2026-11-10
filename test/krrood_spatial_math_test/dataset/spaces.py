from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Self

from krrood.patterns.interface import Interface
from krrood_spatial_math.affine_line import AffineLine
from krrood_spatial_math.affine_point import AffinePoint, AffinePointT
from krrood_spatial_math.affine_vector import AffineVector, AffineVectorT
from krrood_spatial_math.cartesian_frame_3d import CartesianFrame3D
from krrood_spatial_math.coordinate_system import (
    AffineCoordinateChange,
    AffineFrame,
    AffineFrameT,
    CoordinateT,
    RigidCoordinateChange,
)
from krrood_spatial_math.space import Space

# %% a plane whose frames differ by scaling each axis


class ScalablePlane(Space, Interface):
    """
    A plane whose frames differ by scaling and shifting each axis, so its coordinate
    changes are affine but not rigid.
    """


class ScalablePlaneFrame(AffineFrame[ScalablePlane, str], Interface):
    """
    An affine frame on a :class:`ScalablePlane`, called by a plain name.
    """


# %% points and vectors that store their coordinates


@dataclass
class StoredAffineVector(AffineVector[AffineFrameT, CoordinateT]):
    """
    A vector that stores its two coordinates and frame as given.
    """

    x: CoordinateT
    """
    The amount along the first axis.
    """

    y: CoordinateT
    """
    The amount along the second axis.
    """

    coordinate_system: AffineFrameT | None
    """
    The frame the coordinates are given in.
    """

    def __add__(self, other: Self) -> Self:
        return type(self)(self.x + other.x, self.y + other.y, self.coordinate_system)

    def __sub__(self, other: Self) -> Self:
        return type(self)(self.x - other.x, self.y - other.y, self.coordinate_system)

    def __mul__(self, factor: CoordinateT) -> Self:
        return type(self)(self.x * factor, self.y * factor, self.coordinate_system)


@dataclass
class StoredScalablePlaneVector(StoredAffineVector[ScalablePlaneFrame, float]):
    """
    A vector on a scalable plane that stores its coordinates as given.
    """


@dataclass
class StoredAffinePoint(AffinePoint[AffineFrameT, CoordinateT, AffineVectorT]):
    """
    A point that stores its two coordinates and frame as given.
    """

    x: CoordinateT
    """
    The first coordinate.
    """

    y: CoordinateT
    """
    The second coordinate.
    """

    coordinate_system: AffineFrameT | None
    """
    The frame the coordinates are given in.
    """

    def __sub__(self, other: Self) -> AffineVectorT:
        vector_type = self.get_type_of_generic_parameter(parameter=AffineVectorT)
        return vector_type(self.x - other.x, self.y - other.y, self.coordinate_system)

    def __add__(self, vector: AffineVectorT) -> Self:
        return type(self)(self.x + vector.x, self.y + vector.y, self.coordinate_system)


@dataclass
class StoredScalablePlanePoint(
    StoredAffinePoint[ScalablePlaneFrame, float, StoredScalablePlaneVector]
):
    """
    A point on a scalable plane that stores its coordinates as given.
    """


# %% lines that store their point and direction


@dataclass
class StoredAffineLine(AffineLine[AffinePointT, AffineVectorT]):
    """
    A line that stores its point and direction as given.
    """

    point: AffinePointT
    """
    The point the line passes through.
    """

    direction: AffineVectorT
    """
    The vector the line runs along.
    """


@dataclass
class StoredScalablePlaneLine(
    StoredAffineLine[StoredScalablePlanePoint, StoredScalablePlaneVector]
):
    """
    A line on a scalable plane that stores its point and direction as given.
    """


# %% coordinate changes of one kind each


@dataclass
class ScalingChange(AffineCoordinateChange[ScalablePlaneFrame]):
    """
    An affine change between two frames of one scalable plane.
    """


@dataclass
class CartesianFrame3DChange(RigidCoordinateChange[CartesianFrame3D]):
    """
    A rigid change between two Cartesian frames, such as from a gripper to the table.
    """
