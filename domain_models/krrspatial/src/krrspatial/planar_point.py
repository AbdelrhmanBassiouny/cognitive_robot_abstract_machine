from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrspatial.coordinate_system import CoordinateSystemT

# %% points given by two coordinates

CoordinateT = TypeVar("CoordinateT")
"""
What a coordinate of a point is stored as.
"""


class PlanarPoint(
    Generic[CoordinateSystemT, CoordinateT], SubClassSafeGeneric, Interface
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

    coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are given in; ``None`` where it is not known.
    """
