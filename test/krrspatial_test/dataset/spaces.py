from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from krrspatial.planar_point import CoordinateT, PlanarPoint, SpaceT
from krrspatial.space import ImageSpace

# %% images told apart by name


@dataclass(eq=False)
class NamedImage(ImageSpace):
    """
    An image space that only has a name.
    """

    name: str
    """
    What the image is called.
    """

    id: UUID = field(default_factory=uuid4)
    """
    The identifier serialized points refer to the image with.
    """


# %% points that store their coordinates


@dataclass
class StoredPlanarPoint(PlanarPoint[SpaceT, CoordinateT]):
    """
    A point that stores its coordinates and space as given.
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
    The space the coordinates are given in.
    """


@dataclass
class StoredImagePoint(StoredPlanarPoint[ImageSpace, float]):
    """
    A position on an image that stores its coordinates as given.
    """
