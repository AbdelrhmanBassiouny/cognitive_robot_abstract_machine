from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrspatial.coordinate_system import CoordinateRepresentation, CoordinateSystemT

# %% points given by two coordinates

CoordinateT = TypeVar("CoordinateT")
"""
What a coordinate of a point is stored as.
"""


class PlanarPoint(
    CoordinateRepresentation[CoordinateSystemT],
    Generic[CoordinateSystemT, CoordinateT],
    Interface,
):
    """
    A point given by two coordinates in a coordinate system.

    .. note::
        Each implementation binds both parameters once, so one kind of coordinate system
        has one point type.
    """

    x: CoordinateT
    """
    The first coordinate.
    """

    y: CoordinateT
    """
    The second coordinate.
    """
