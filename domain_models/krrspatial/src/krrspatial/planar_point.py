from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrspatial.space import Space

# %% points given by two coordinates

SpaceT = TypeVar("SpaceT", bound=Space)
"""
The kind of space a point is given in.
"""

CoordinateT = TypeVar("CoordinateT")
"""
What a coordinate of a point is stored as.
"""


class PlanarPoint(Generic[SpaceT, CoordinateT], SubClassSafeGeneric, Interface):
    """
    A point given by two coordinates in a space.

    .. note::
        Each implementation binds both parameters once, so one space has one point type.
    """

    x: CoordinateT
    """
    The first coordinate.
    """

    y: CoordinateT
    """
    The second coordinate.
    """

    space: SpaceT | None
    """
    The space the coordinates are given in; ``None`` where it is not known.
    """
