"""
The spatial types every implementation provides, generic over the type of their
coordinates.
"""

from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

from krrspatial.reference_frame import ReferenceFrame

# %% anything expressed in a reference frame

CoordinateT = TypeVar("CoordinateT")


class SpatialType(Generic[CoordinateT], SubClassSafeGeneric, Interface):
    """
    A spatial object whose coordinates are of one type.
    """

    reference_frame: ReferenceFrame | None
    """
    The frame its coordinates are expressed in; none if it is not tied to one.
    """


# %% positions and directions in a plane


class Coordinates2(SpatialType[CoordinateT], Interface):
    """
    A spatial object with coordinates along two axes.
    """

    x: CoordinateT
    """
    The coordinate along the first axis.
    """

    y: CoordinateT
    """
    The coordinate along the second axis.
    """


class Point2(Coordinates2[CoordinateT], Interface):
    """
    A position in a plane.
    """


class Vector2(Coordinates2[CoordinateT], Interface):
    """
    A direction and length in a plane.
    """
