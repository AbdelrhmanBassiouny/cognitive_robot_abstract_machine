from __future__ import annotations

from dataclasses import dataclass

from krrood.patterns.interface import Interface
from krrood_spatial_math.affine_point import AffinePoint2D, AffinePoint3D, CoordinateT
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


class ScalablePlaneFrame(AffineFrame[ScalablePlane, str], Interface):
    """
    An affine frame on a :class:`ScalablePlane`, called by a plain name.
    """


class ScalableSpace(Space, Interface):
    """
    A three-dimensional space whose frames differ by scaling and shifting each axis.
    """


class ScalableSpaceFrame(AffineFrame[ScalableSpace, str], Interface):
    """
    An affine frame on a :class:`ScalableSpace`, called by a plain name.
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


@dataclass
class StoredAffinePoint3D(AffinePoint3D[AffineFrameT, CoordinateT]):
    """
    A three-dimensional point that stores its coordinates and frame as given.
    """

    x: CoordinateT
    """
    The first coordinate.
    """

    y: CoordinateT
    """
    The second coordinate.
    """

    z: CoordinateT
    """
    The third coordinate.
    """

    coordinate_system: AffineFrameT | None
    """
    The frame the coordinates are given in.
    """


@dataclass
class StoredScalableSpacePoint(StoredAffinePoint3D[ScalableSpaceFrame, float]):
    """
    A point in a scalable space that stores its coordinates as given.
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
