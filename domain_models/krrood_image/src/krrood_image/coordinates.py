"""
The plane images lie on, and positions, displacements and boxes on an image, in pixels
from its top left corner.

``x`` runs along the columns and ``y`` down the rows, so a box's lower corner is its top
left one.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Self

from krrood.bounds import Bounds
from krrood.patterns.identifier_and_name import NameT
from krrood.patterns.interface import Interface
from krrood_spatial_math.coordinate_system import AffineFrame
from krrood_spatial_math.point import Point
from krrood_spatial_math.space import EuclideanSpace2Dimensional
from krrood_spatial_math.vector import Vector

# %% the plane images lie on, and the coordinate systems on it


class ImagePlane(EuclideanSpace2Dimensional, Interface):
    """
    The plane a camera shows its scene on; every image the camera takes, and every crop
    and resize of one, lies on the same plane.
    """


class ImageCoordinateSystem(AffineFrame[ImagePlane, NameT], Interface):
    """
    Pixel coordinates on an image plane, from the top left corner of one image of it,
    with ``x`` along the columns and ``y`` down the rows.

    Its axes are one pixel long, so two image coordinate systems of one plane differ by
    scaling and shifting each axis.
    """


# %% the size of an image


@dataclass(frozen=True, kw_only=True)
class Resolution:
    """
    How many columns and rows of pixels an image has.
    """

    width: int
    """
    Columns of pixels.
    """

    height: int
    """
    Rows of pixels.
    """


# %% displacements and positions anywhere on an image


@dataclass(kw_only=True)
class ImageVector(Vector[ImageCoordinateSystem, float]):
    """
    A displacement across an image, in pixels.
    """

    x: float
    """
    Pixels to the right.
    """

    y: float
    """
    Pixels down.
    """

    coordinate_system: ImageCoordinateSystem | None = None
    """
    The image coordinate system the displacement is given in; ``None`` where it is not
    known.
    """

    @property
    def coordinates(self) -> tuple[float, float]:
        """
        The pixels along ``x`` and then along ``y``, the order of the image axes.
        """
        return self.x, self.y

    def __add__(self, other: Self) -> Self:
        return type(self)(
            x=self.x + other.x,
            y=self.y + other.y,
            coordinate_system=self.coordinate_system,
        )

    def __sub__(self, other: Self) -> Self:
        return type(self)(
            x=self.x - other.x,
            y=self.y - other.y,
            coordinate_system=self.coordinate_system,
        )

    def __mul__(self, factor: float) -> Self:
        return type(self)(
            x=self.x * factor,
            y=self.y * factor,
            coordinate_system=self.coordinate_system,
        )


@dataclass(kw_only=True)
class ImagePoint(Point[ImageCoordinateSystem, float, ImageVector]):
    """
    A position on an image, anywhere between its pixels.
    """

    x: float
    """
    Pixels from the image's left edge.
    """

    y: float
    """
    Pixels from the image's top edge.
    """

    coordinate_system: ImageCoordinateSystem | None = None
    """
    The image coordinate system the position is given in; ``None`` where it is not
    known.
    """

    @property
    def coordinates(self) -> tuple[float, float]:
        """
        The pixels along ``x`` and then along ``y``, the order of the image axes.
        """
        return self.x, self.y

    def __sub__(self, other: Self) -> ImageVector:
        return ImageVector(
            x=self.x - other.x,
            y=self.y - other.y,
            coordinate_system=self.coordinate_system,
        )

    def __add__(self, vector: ImageVector) -> Self:
        return type(self)(
            x=self.x + vector.x,
            y=self.y + vector.y,
            coordinate_system=self.coordinate_system,
        )


# %% boxes anywhere on an image


@dataclass(kw_only=True)
class ImageBox(Bounds[ImagePoint]):
    """
    An axis-aligned box on an image, its edges anywhere between pixels.
    """

    @classmethod
    def from_corner_and_size(
        cls, *, left: float, top: float, width: float, height: float
    ) -> ImageBox:
        """
        :param left: Pixels from the image's left edge to the box's.
        :param top: Pixels from the image's top edge to the box's.
        :param width: How many columns wide it is.
        :param height: How many rows tall it is.
        :return: The box of that size with its top left corner there.
        """
        return cls(
            lower=ImagePoint(x=left, y=top),
            upper=ImagePoint(x=left + width, y=top + height),
        )

    @classmethod
    def covering(cls, *, resolution: Resolution) -> ImageBox:
        """
        :param resolution: The size of an image.
        :return: The box covering a whole image of that size.
        """
        return cls.from_corner_and_size(
            left=0, top=0, width=resolution.width, height=resolution.height
        )

    @property
    def left(self) -> float:
        """
        Pixels from the image's left edge to the box's.
        """
        return self.lower.x

    @property
    def top(self) -> float:
        """
        Pixels from the image's top edge to the box's.
        """
        return self.lower.y

    @property
    def right(self) -> float:
        """
        Pixels from the image's left edge to the box's right edge.
        """
        return self.upper.x

    @property
    def bottom(self) -> float:
        """
        Pixels from the image's top edge to the box's bottom edge.
        """
        return self.upper.y

    @property
    def width(self) -> float:
        """
        How many columns wide it is.
        """
        return self.right - self.left

    @property
    def height(self) -> float:
        """
        How many rows tall it is.
        """
        return self.bottom - self.top

    def largest_centred(self, *, aspect_ratio: float) -> ImageBox:
        """
        :param aspect_ratio: Width over height.
        :return: The largest box of that aspect ratio centred in this one.
        """
        if self.width / self.height > aspect_ratio:
            height = self.height
            width = height * aspect_ratio
        else:
            width = self.width
            height = width / aspect_ratio
        return ImageBox.from_corner_and_size(
            left=self.left + (self.width - width) / 2,
            top=self.top + (self.height - height) / 2,
            width=width,
            height=height,
        )


# %% whole pixels


@dataclass(frozen=True, kw_only=True)
class Pixel:
    """
    The pixel at a column and row of an image.
    """

    column: int
    """
    Pixels from the image's left edge.
    """

    row: int
    """
    Pixels from the image's top edge.
    """

    @classmethod
    def nearest(cls, *, point: ImagePoint) -> Pixel:
        """
        :param point: A position on an image.
        :return: The pixel it falls on.
        """
        return cls(column=round(point.x), row=round(point.y))


@dataclass(kw_only=True)
class PixelBox(Bounds[Pixel]):
    """
    A box of whole pixels of an image, from its top left pixel to its bottom right one.
    """

    @classmethod
    def between(cls, *, left: int, top: int, right: int, bottom: int) -> PixelBox:
        """
        :param left: The column of its left edge.
        :param top: The row of its top edge.
        :param right: The column just right of it.
        :param bottom: The row just below it.
        :return: The box of the pixels between those edges.
        """
        return cls(
            lower=Pixel(column=left, row=top),
            upper=Pixel(column=right - 1, row=bottom - 1),
        )

    @classmethod
    def nearest(cls, *, box: ImageBox) -> PixelBox:
        """
        :param box: A box on an image.
        :return: The whole pixels it covers, its edges rounded to the nearest.
        """
        return cls.between(
            left=round(box.left),
            top=round(box.top),
            right=round(box.right),
            bottom=round(box.bottom),
        )

    @property
    def left(self) -> int:
        """
        The column of its left edge.
        """
        return self.lower.column

    @property
    def top(self) -> int:
        """
        The row of its top edge.
        """
        return self.lower.row

    @property
    def right(self) -> int:
        """
        The column just right of the box.
        """
        return self.upper.column + 1

    @property
    def bottom(self) -> int:
        """
        The row just below the box.
        """
        return self.upper.row + 1

    @property
    def width(self) -> int:
        """
        How many columns wide it is.
        """
        return self.right - self.left

    @property
    def height(self) -> int:
        """
        How many rows tall it is.
        """
        return self.bottom - self.top

    @property
    def is_empty(self) -> bool:
        """
        Whether it covers no pixel.
        """
        return self.width <= 0 or self.height <= 0

    def visible_part(self, *, resolution: Resolution) -> PixelBox:
        """
        :param resolution: The size of an image.
        :return: The part of the box inside an image that size; empty if none is.
        """
        return PixelBox.between(
            left=max(self.left, 0),
            top=max(self.top, 0),
            right=min(self.right, resolution.width),
            bottom=min(self.bottom, resolution.height),
        )
