from __future__ import annotations

from dataclasses import astuple, dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from krrimage.color import Color
from krrimage.coordinates import ImageBox, ImagePoint, Pixel, PixelBox, Resolution

# %% a colour image


@dataclass(frozen=True, eq=False)
class ColorImage:
    """
    An image of red, green and blue bytes, rows by columns by channel.

    Drawing returns a new image and leaves this one as it was.
    """

    pixels: NDArray[np.uint8]
    """
    The bytes, rows by columns by channel.
    """

    @classmethod
    def of_color(cls, resolution: Resolution, color: Color) -> ColorImage:
        """
        :param resolution: The size.
        :param color: What every pixel is set to.
        :return: An image that size of one colour.
        """
        return cls(
            np.full(
                (resolution.height, resolution.width, len(color.to_rgb())),
                tuple(color.to_rgb_bytes()),
                dtype=np.uint8,
            )
        )

    @property
    def resolution(self) -> Resolution:
        """
        The size of this image.
        """
        height, width = self.pixels.shape[:2]
        return Resolution(width=width, height=height)

    def pasted(self, picture: ColorImage, into: ImageBox) -> ColorImage:
        """
        :param picture: What to paste.
        :param into: Where, and how big; what leaves the image is cropped.
        :return: A copy with the picture resized into the box.
        """
        result = self.pixels.copy()
        box = PixelBox.nearest(into)
        shown = box.clipped_to(self.resolution)
        if box.is_empty or shown.is_empty:
            return ColorImage(result)
        resized = cv2.resize(
            picture.pixels, (box.width, box.height), interpolation=cv2.INTER_AREA
        )
        result[shown.top : shown.bottom, shown.left : shown.right] = resized[
            shown.top - box.top : shown.bottom - box.top,
            shown.left - box.left : shown.right - box.left,
        ]
        return ColorImage(result)

    def fitted(self, picture: ColorImage, into: ImageBox) -> ColorImage:
        """
        :param picture: What to paste.
        :param into: The room it may take.
        :return: A copy with the picture pasted as large as it goes into the room
            without distorting it, centred there.
        """
        resolution = picture.resolution
        return self.pasted(
            picture, into.largest_centred(resolution.width / resolution.height)
        )

    def dimmed(self, by: float) -> ColorImage:
        """
        :param by: How far towards white, from zero to one.
        :return: A copy faded towards white.
        """
        faded = self.pixels.astype(np.float32) * (1.0 - by) + 255.0 * by
        return ColorImage(np.clip(faded + 0.5, 0, 255).astype(np.uint8))

    def blended(self, other: ColorImage, weight: float) -> ColorImage:
        """
        :param other: The image shown when the weight is one.
        :param weight: How much of the other image shows, from zero to one.
        :return: A mix of this image and the other.
        """
        mixed = (
            self.pixels.astype(np.float32) * (1.0 - weight)
            + other.pixels.astype(np.float32) * weight
        )
        return ColorImage(np.clip(mixed + 0.5, 0, 255).astype(np.uint8))

    def framed(self, around: ImageBox, color: Color, thickness: int = 3) -> ColorImage:
        """
        :param around: The box.
        :param color: What the outline is drawn in.
        :param thickness: Pixels the outline is thick.
        :return: A copy with the box outlined.
        """
        result = self.pixels.copy()
        box = PixelBox.nearest(around)
        cv2.rectangle(
            result,
            (box.left, box.top),
            (box.right, box.bottom),
            tuple(color.to_rgb_bytes()),
            thickness,
        )
        return ColorImage(result)

    def filled(self, around: ImageBox, color: Color) -> ColorImage:
        """
        :param around: The box.
        :param color: What it is painted in.
        :return: A copy with the box painted over.
        """
        result = self.pixels.copy()
        box = PixelBox.nearest(around)
        cv2.rectangle(
            result,
            (box.left, box.top),
            (box.right, box.bottom),
            tuple(color.to_rgb_bytes()),
            cv2.FILLED,
        )
        return ColorImage(result)

    def lined(
        self, start: ImagePoint, end: ImagePoint, color: Color, thickness: int = 2
    ) -> ColorImage:
        """
        :param start: Where the line starts.
        :param end: Where it ends.
        :param color: What it is drawn in.
        :param thickness: Pixels it is thick.
        :return: A copy with a straight line drawn on it.
        """
        result = self.pixels.copy()
        cv2.line(
            result,
            astuple(Pixel.nearest(start)),
            astuple(Pixel.nearest(end)),
            tuple(color.to_rgb_bytes()),
            thickness,
            cv2.LINE_AA,
        )
        return ColorImage(result)

    def arrowed(
        self,
        start: ImagePoint,
        end: ImagePoint,
        color: Color,
        thickness: int = 2,
        head_length: float = 12.0,
    ) -> ColorImage:
        """
        :param start: Where the arrow starts.
        :param end: Where its head is.
        :param color: What it is drawn in.
        :param thickness: Pixels it is thick.
        :param head_length: Pixels the head is long, at most half the arrow.
        :return: A copy with an arrow drawn on it.
        """
        result = self.pixels.copy()
        length = max(np.hypot(end.x - start.x, end.y - start.y), 1.0)
        cv2.arrowedLine(
            result,
            astuple(Pixel.nearest(start)),
            astuple(Pixel.nearest(end)),
            tuple(color.to_rgb_bytes()),
            thickness,
            cv2.LINE_AA,
            tipLength=min(head_length / length, 0.5),
        )
        return ColorImage(result)
