from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.adapters.object_reference import IdentifiedObject
from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrspatial.space import ImagePlane, Space

# %% what coordinates are given in

SpaceT = TypeVar("SpaceT", bound=Space)
"""
The kind of space a coordinate system charts.
"""


class CoordinateSystem(
    Generic[SpaceT], SubClassSafeGeneric, IdentifiedObject, Interface
):
    """
    What the coordinates of a point are given in: an origin, axes and a unit on one
    space.

    Coordinates given in one coordinate system mean nothing in another, so values of two
    coordinate systems are combined only after changing one into the other.
    """

    space: SpaceT | None
    """
    The space this coordinate system charts; ``None`` where it is not known.
    """


class ImageCoordinateSystem(CoordinateSystem[ImagePlane], Interface):
    """
    Pixel coordinates on an image plane, from the top left corner of one image of it,
    with ``x`` along the columns and ``y`` down the rows.
    """


# %% changing coordinates within one space

CoordinateSystemT = TypeVar("CoordinateSystemT", bound=CoordinateSystem)
"""
The kind of coordinate system coordinates are given in.
"""


class CoordinateChange(Generic[CoordinateSystemT], SubClassSafeGeneric, Interface):
    """
    Turns coordinates given in one coordinate system into those of the same points in
    another coordinate system of the same space.

    .. note::
        Each implementation binds the kind of coordinate system once, so the kind of
        change a space allows is part of its type. A map between two spaces is a
        projection, not a coordinate change.
    """

    source_coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are given in; ``None`` where it is not known.
    """

    target_coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are changed into; ``None`` where it is not
    known.
    """
