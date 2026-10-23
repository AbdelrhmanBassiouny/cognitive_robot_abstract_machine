"""
Positions and boxes on an image, in pixels from its top left corner.

``x`` runs along the columns and ``y`` down the rows, so a box's lower corner is its top
left one.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.bounds import Bounds
from krrspatial.coordinate_system import ImageCoordinateSystem
from krrspatial.planar_point import PlanarPoint

# %% the size of an image


@dataclass(frozen=True)
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


# %% positions anywhere on an image


@dataclass
class ImagePoint(PlanarPoint[ImageCoordinateSystem, float]):
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


@dataclass
class ImageBox(Bounds[ImagePoint]):
    """
    An axis-aligned box on an image, its edges anywhere between pixels.
    """

    @classmethod
    def from_corner_and_size(
        cls, left: float, top: float, width: float, height: float
    ) -> ImageBox:
        """
        :param left: Pixels from the image's left edge to the box's.
        :param top: Pixels from the image's top edge to the box's.
        :param width: How many columns wide it is.
        :param height: How many rows tall it is.
        :return: The box of that size with its top left corner there.
        """
        return cls(ImagePoint(left, top), ImagePoint(left + width, top + height))

    @classmethod
    def covering(cls, resolution: Resolution) -> ImageBox:
        """
        :param resolution: The size of an image.
        :return: The box covering a whole image of that size.
        """
        return cls.from_corner_and_size(0, 0, resolution.width, resolution.height)

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

    def largest_centred(self, aspect_ratio: float) -> ImageBox:
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
            self.left + (self.width - width) / 2,
            self.top + (self.height - height) / 2,
            width,
            height,
        )


# %% whole pixels


@dataclass(frozen=True)
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
    def nearest(cls, point: ImagePoint) -> Pixel:
        """
        :param point: A position on an image.
        :return: The pixel it falls on.
        """
        return cls(round(point.x), round(point.y))


@dataclass
class PixelBox(Bounds[Pixel]):
    """
    A box of whole pixels of an image, from its top left pixel to its bottom right one.
    """

    @classmethod
    def between(cls, left: int, top: int, right: int, bottom: int) -> PixelBox:
        """
        :param left: The column of its left edge.
        :param top: The row of its top edge.
        :param right: The column just right of it.
        :param bottom: The row just below it.
        :return: The box of the pixels between those edges.
        """
        return cls(Pixel(left, top), Pixel(right - 1, bottom - 1))

    @classmethod
    def nearest(cls, box: ImageBox) -> PixelBox:
        """
        :param box: A box on an image.
        :return: The whole pixels it covers, its edges rounded to the nearest.
        """
        return cls.between(
            round(box.left), round(box.top), round(box.right), round(box.bottom)
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

    def clipped_to(self, resolution: Resolution) -> PixelBox:
        """
        :param resolution: The size of an image.
        :return: The part of the box inside an image that size; empty if none is.
        """
        return PixelBox.between(
            max(self.left, 0),
            max(self.top, 0),
            min(self.right, resolution.width),
            min(self.bottom, resolution.height),
        )
