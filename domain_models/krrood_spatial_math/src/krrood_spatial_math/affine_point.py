from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood_spatial_math.coordinate_system import AffineFrameT, CoordinateRepresentation

# %% points given by two affine coordinates

CoordinateT = TypeVar("CoordinateT")
"""
The type a coordinate's real value is stored as, such as a float, or a symbolic
expression standing for a real number.
"""


class AffinePoint2D(
    CoordinateRepresentation[AffineFrameT],
    Generic[AffineFrameT, CoordinateT],
    Interface,
):
    """
    A point given by its two coordinates in an affine frame: its amounts along the
    frame's two axes from the frame's origin.

    .. note::
        Each implementation binds both parameters once, so one kind of frame has one
        point type.
    """

    x: CoordinateT
    """
    The amount along the frame's first axis.
    """

    y: CoordinateT
    """
    The amount along the frame's second axis.
    """
