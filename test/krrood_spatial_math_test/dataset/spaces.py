from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Self

from krrood.patterns.interface import Interface
from krrood_spatial_math.affine_point import AffinePoint2D, CoordinateT
from krrood_spatial_math.cartesian_frame_3d import CartesianFrame3D
from krrood_spatial_math.coordinate_system import (
    AffineCoordinateChange,
    AffineFrame,
    AffineFrameT,
    RigidCoordinateChange,
)
from krrood_spatial_math.space import Space

# %% a plane whose frames differ by scaling each axis


class ScalablePlane(Space, Interface):
    """
    A plane whose frames differ by scaling and shifting each axis, so its coordinate
    changes are affine but not rigid.
    """


class ScalablePlaneFrame(AffineFrame[ScalablePlane], Interface):
    """
    An affine frame on a :class:`ScalablePlane`.
    """


# %% points that store their coordinates


@dataclass
class StoredAffinePoint2D(AffinePoint2D[AffineFrameT, CoordinateT]):
    """
    A point that stores its coordinates and frame as given.
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


@dataclass
class StoredScalablePlanePoint(StoredAffinePoint2D[ScalablePlaneFrame, float]):
    """
    A point on a scalable plane that stores its coordinates as given.
    """


# %% coordinate changes that store their frames


@dataclass
class StoredCoordinateChange(AffineCoordinateChange[AffineFrameT]):
    """
    An affine coordinate change that only stores the frames it changes between.
    """

    source_coordinate_system: AffineFrameT | None
    """
    The frame the coordinates are given in.
    """

    target_coordinate_system: AffineFrameT | None
    """
    The frame the coordinates are changed into.
    """

    def inverse(self) -> Self:
        return type(self)(self.target_coordinate_system, self.source_coordinate_system)

    def __matmul__(self, other: Self) -> Self:
        return type(self)(other.source_coordinate_system, self.target_coordinate_system)


@dataclass
class StoredScalingChange(StoredCoordinateChange[ScalablePlaneFrame]):
    """
    A change between two frames of one scalable plane.
    """


@dataclass
class StoredFrameChange(
    StoredCoordinateChange[CartesianFrame3D], RigidCoordinateChange[CartesianFrame3D]
):
    """
    A rigid change between two Cartesian frames, such as from a gripper to the table.
    """
