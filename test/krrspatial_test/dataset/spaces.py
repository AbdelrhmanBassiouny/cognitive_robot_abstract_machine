from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from krrspatial.coordinate_system import (
    CoordinateChange,
    CoordinateSystemT,
    ImageCoordinateSystem,
)
from krrspatial.planar_point import CoordinateT, PlanarPoint
from krrspatial.space import ImagePlane

# %% image planes and their coordinate systems, told apart by name


@dataclass(eq=False)
class NamedImagePlane(ImagePlane):
    """
    An image plane that only has a name.
    """

    name: str
    """
    What the plane is called.
    """


@dataclass(eq=False)
class NamedImageCoordinateSystem(ImageCoordinateSystem):
    """
    An image coordinate system that only has a name and the plane it charts.
    """

    name: str
    """
    What the coordinate system is called.
    """

    space: ImagePlane | None = None
    """
    The plane the coordinate system charts.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier serialized points refer to the coordinate system with.
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
class StoredImagePoint(StoredPlanarPoint[ImageCoordinateSystem, float]):
    """
    A position on an image that stores its coordinates as given.
    """


# %% coordinate changes that store their coordinate systems


@dataclass
class StoredCoordinateChange(CoordinateChange[CoordinateSystemT]):
    """
    A coordinate change that only stores the coordinate systems it changes between.
    """

    source_coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are given in.
    """

    target_coordinate_system: CoordinateSystemT | None
    """
    The coordinate system the coordinates are changed into.
    """


@dataclass
class StoredImageCoordinateChange(StoredCoordinateChange[ImageCoordinateSystem]):
    """
    A change between two coordinate systems of one image plane, such as from a crop to
    the whole image.
    """
