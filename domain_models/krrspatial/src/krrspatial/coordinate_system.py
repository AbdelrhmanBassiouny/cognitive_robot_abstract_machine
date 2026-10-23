from __future__ import annotations

from abc import abstractmethod

from typing_extensions import Generic, Self, TypeVar

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


# %% values given in a coordinate system

CoordinateSystemT = TypeVar("CoordinateSystemT", bound=CoordinateSystem)
"""
The kind of coordinate system coordinates are given in.
"""


class CoordinateRepresentation(
    Generic[CoordinateSystemT], SubClassSafeGeneric, Interface
):
    """
    A geometric value, such as a point, a direction or an orientation, given by its
    coordinates in a coordinate system.

    .. seealso::
        T. De Laet, S. Bellens and H. Bruyninckx, "Geometric Relations Between Rigid
        Bodies (Part 1): Semantics for Standardization", IEEE Robotics & Automation
        Magazine, 2013, which separates a geometric value from its coordinates.
    """

    coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are given in; ``None`` where it is not known.
    """


# %% changing coordinates within one space


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

    @abstractmethod
    def inverse(self) -> Self:
        """
        :return: The change from the target coordinate system back to the source one.
        """

    @abstractmethod
    def __matmul__(self, other: Self) -> Self:
        """
        :param other: The change applied first, whose target coordinate system is the
            source one of this change.
        :return: The change that applies the other change and then this one.
        """


class AffineCoordinateChange(CoordinateChange[CoordinateSystemT], Interface):
    """
    A coordinate change that scales, shears, rotates or reflects the axes and shifts the
    origin.

    It keeps straight lines, parallel lines and ratios of lengths along one line.
    """


class RigidCoordinateChange(AffineCoordinateChange[CoordinateSystemT], Interface):
    """
    An affine coordinate change that only rotates the axes and shifts the origin.

    It also keeps distances and angles.
    """
