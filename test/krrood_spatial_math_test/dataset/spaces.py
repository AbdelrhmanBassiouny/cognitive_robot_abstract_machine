from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Self

from krrood.patterns.interface import Interface
from krrood_spatial_math.coordinate_system import (
    AffineCoordinateChange,
    CoordinateSystem,
    CoordinateSystemT,
    RigidCoordinateChange,
)
from krrood_spatial_math.planar_point import CoordinateT, PlanarPoint
from krrood_spatial_math.reference_frame import ReferenceFrame
from krrood_spatial_math.space import Space

# %% a plane whose coordinate systems differ by scaling each axis


class ScalablePlane(Space, Interface):
    """
    A plane whose coordinate systems differ by scaling and shifting each axis, so its
    coordinate changes are affine but not rigid.
    """


class ScalablePlaneCoordinateSystem(CoordinateSystem[ScalablePlane], Interface):
    """
    A coordinate system on a :class:`ScalablePlane`.
    """


# %% points that store their coordinates


@dataclass
class StoredPlanarPoint(PlanarPoint[CoordinateSystemT, CoordinateT]):
    """
    A point that stores its coordinates and coordinate system as given.
    """

    x: CoordinateT
    """
    The first coordinate.
    """

    y: CoordinateT
    """
    The second coordinate.
    """

    coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are given in.
    """


@dataclass
class StoredScalablePlanePoint(StoredPlanarPoint[ScalablePlaneCoordinateSystem, float]):
    """
    A point on a scalable plane that stores its coordinates as given.
    """


# %% coordinate changes that store their coordinate systems


@dataclass
class StoredCoordinateChange(AffineCoordinateChange[CoordinateSystemT]):
    """
    An affine coordinate change that only stores the coordinate systems it changes
    between.
    """

    source_coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are given in.
    """

    target_coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are changed into.
    """

    def inverse(self) -> Self:
        return type(self)(self.target_coordinate_system, self.source_coordinate_system)

    def __matmul__(self, other: Self) -> Self:
        return type(self)(other.source_coordinate_system, self.target_coordinate_system)


@dataclass
class StoredScalingChange(StoredCoordinateChange[ScalablePlaneCoordinateSystem]):
    """
    A change between two coordinate systems of one scalable plane.
    """


@dataclass
class StoredFrameChange(
    StoredCoordinateChange[ReferenceFrame], RigidCoordinateChange[ReferenceFrame]
):
    """
    A rigid change between two reference frames, such as from a gripper to the table.
    """
