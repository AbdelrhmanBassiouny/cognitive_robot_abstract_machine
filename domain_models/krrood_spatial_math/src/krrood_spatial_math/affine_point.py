from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, Self, TypeVar

from krrood.patterns.interface import Interface
from krrood_spatial_math.coordinate_system import (
    AffineFrameT,
    CartesianFrameT,
    CoordinateRepresentation,
)

# %% points given by affine coordinates

CoordinateT = TypeVar("CoordinateT")
"""
The type a coordinate's real value is stored as, such as a float, or a symbolic
expression standing for a real number.
"""


class AffinePoint(
    CoordinateRepresentation[AffineFrameT],
    Generic[AffineFrameT, CoordinateT],
    Interface,
):
    """
    A point given by its coordinates in an affine frame: its amounts along the frame's
    axes from the frame's origin, one per axis of the frame.

    .. note::
        Each implementation binds both parameters once, so one kind of frame has one
        point type.
    """


class CartesianPoint(AffinePoint[CartesianFrameT, CoordinateT], Interface):
    """
    A point given in a Cartesian frame, whose orthonormal axes measure distances.
    """

    @abstractmethod
    def euclidean_distance(self, other: Self) -> CoordinateT:
        """
        :param other: A point given in the same frame.
        :return: The straight-line distance between this point and ``other``.
        """


# %% points given by two affine coordinates


class AffinePoint2D(AffinePoint[AffineFrameT, CoordinateT], Interface):
    """
    A point given by its two coordinates in an affine frame: its amounts along the
    frame's two axes from the frame's origin.
    """

    x: CoordinateT
    """
    The amount along the frame's first axis.
    """

    y: CoordinateT
    """
    The amount along the frame's second axis.
    """


# %% points given by three affine coordinates


class AffinePoint3D(AffinePoint[AffineFrameT, CoordinateT], Interface):
    """
    A point given by its three coordinates in an affine frame: its amounts along the
    frame's three axes from the frame's origin.
    """

    x: CoordinateT
    """
    The amount along the frame's first axis.
    """

    y: CoordinateT
    """
    The amount along the frame's second axis.
    """

    z: CoordinateT
    """
    The amount along the frame's third axis.
    """
