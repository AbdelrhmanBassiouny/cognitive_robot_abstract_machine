"""
The pictures a video is made of, and drawing on them.

A frame is rows of columns of red, green and blue bytes. Colours are those of
:class:`~semantic_digital_twin.world_description.geometry.Color`, positions are
:class:`~semantic_digital_twin.spatial_types.spatial_types.Point2` and rectangles are
:class:`~semantic_digital_twin.world_description.geometry.PlanarBoundingBox`, all in
pixels from the frame's top left corner: ``x`` runs along the columns and ``y`` down the
rows, so a box's ``min_x`` is its left edge and its ``min_y`` its top edge.
"""

from __future__ import annotations

from dataclasses import dataclass


import cv2
import numpy as np
from PIL import Image, ImageDraw
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Point2,
)
from semantic_digital_twin.world_description.geometry import Color, PlanarBoundingBox
from typing_extensions import Tuple

# %% the size of a frame


@dataclass(frozen=True)
class Resolution:
    """
    The size every frame of a video has, and the room its scenes leave around what they
    show.
    """

    width: int
    """
    Columns of pixels.
    """

    height: int
    """
    Rows of pixels.
    """

    margin: int = 32
    """
    The margin every frame keeps all round, in pixels.
    """

    subtitle_band_share: float = 0.14
    """
    The share of the frame's height, at its bottom, left clear for the captions: two
    rows of them on a fixed baseline, with their margin.
    """

    @classmethod
    def standard(cls) -> Resolution:
        """
        :return: 720 rows by 1280 columns: sharp enough to read the smallest letters and
            small enough to encode minutes of video in a few megabytes.
        """
        return cls(width=1280, height=720)

    @property
    def shape(self) -> Tuple[int, int, int]:
        """
        The array shape of one frame this size.
        """
        return (self.height, self.width, 3)

    @property
    def stage_height(self) -> float:
        """
        How far down a scene may draw: the rows above the band left for subtitles.
        """
        return self.height * (1.0 - self.subtitle_band_share)

    @property
    def whole(self) -> PlanarBoundingBox:
        """
        The box covering a frame of this size.
        """
        return Frame.box(0, 0, self.width, self.height)

    @classmethod
    def of(cls, frame: Frame) -> Resolution:
        """
        :param frame: A frame.
        :return: Its size.
        """
        height, width = frame.pixels.shape[:2]
        return cls(width=width, height=height)

    def blank(self, grey: int = 255) -> Frame:
        """
        :param grey: The grey every pixel is set to.
        :return: A frame this size of one grey.
        """
        return Frame(np.full(self.shape, grey, dtype=np.uint8))


# %% a frame


@dataclass(frozen=True, eq=False)
class Frame:
    """
    One picture of the video: red, green and blue bytes, rows by columns by channel.

    Drawing returns a new frame and leaves this one as it was.
    """

    pixels: np.ndarray
    """
    The bytes, rows by columns by channel.
    """

    @property
    def resolution(self) -> Resolution:
        """
        The size of this frame.
        """
        return Resolution.of(self)

    @classmethod
    def of_color(cls, resolution: Resolution, color: Color) -> Frame:
        """
        :param resolution: The size.
        :param color: What every pixel is set to.
        :return: A frame that size of one colour.
        """
        return cls(np.full(resolution.shape, cls.bytes_of(color), dtype=np.uint8))

    @staticmethod
    def bytes_of(color: Color) -> Tuple[int, int, int]:
        """
        :param color: A colour.
        :return: Its red, green and blue as the bytes a frame holds; the opacity is not
            part of it.
        """
        red, green, blue = color.to_rgb()
        return round(red * 255), round(green * 255), round(blue * 255)

    @staticmethod
    def box(left: float, top: float, width: float, height: float) -> PlanarBoundingBox:
        """
        :param left: Pixels from the frame's left edge to the box's.
        :param top: Pixels from the frame's top edge to the box's.
        :param width: How many columns wide it is.
        :param height: How many rows tall it is.
        :return: The box in pixels from the frame's top left corner.
        """
        return PlanarBoundingBox(
            min_x=left,
            min_y=top,
            max_x=left + width,
            max_y=top + height,
            origin=HomogeneousTransformationMatrix(),
        )

    @staticmethod
    def fitting(room: PlanarBoundingBox, aspect: float) -> PlanarBoundingBox:
        """
        :param room: The space available.
        :param aspect: Width over height.
        :return: The largest box of that aspect centred in the room.
        """
        room_width, room_height = room.max_x - room.min_x, room.max_y - room.min_y
        if room_width / room_height > aspect:
            height = room_height
            width = height * aspect
        else:
            width = room_width
            height = width / aspect
        return Frame.box(
            room.min_x + (room_width - width) / 2,
            room.min_y + (room_height - height) / 2,
            width,
            height,
        )

    @staticmethod
    def rounded(box: PlanarBoundingBox) -> Tuple[int, int, int, int]:
        """
        :param box: A box.
        :return: Its left, top, width and height as whole pixels.
        """
        left, top = round(box.min_x), round(box.min_y)
        return left, top, round(box.max_x) - left, round(box.max_y) - top

    @staticmethod
    def _pixel(point: Point2) -> Tuple[int, int]:
        """
        :param point: A position.
        :return: Its column and row as whole pixels.
        """
        return round(float(point.x)), round(float(point.y))

    def pasted(self, picture: Frame, into: PlanarBoundingBox) -> Frame:
        """
        :param picture: What to paste.
        :param into: Where, and how big; what leaves the frame is cropped.
        :return: A copy with the picture resized into the box.
        """
        result = self.pixels.copy()
        left, top, width, height = self.rounded(into)
        if width <= 0 or height <= 0:
            return Frame(result)
        resized = cv2.resize(
            picture.pixels, (width, height), interpolation=cv2.INTER_AREA
        )
        frame_height, frame_width = result.shape[:2]
        x0, y0 = max(left, 0), max(top, 0)
        x1, y1 = min(left + width, frame_width), min(top + height, frame_height)
        if x1 <= x0 or y1 <= y0:
            return Frame(result)
        result[y0:y1, x0:x1] = resized[y0 - top : y1 - top, x0 - left : x1 - left]
        return Frame(result)

    def fitted(self, picture: Frame, into: PlanarBoundingBox) -> Frame:
        """
        :param picture: What to paste.
        :param into: The room it may take.
        :return: A copy with the picture pasted as large as it goes into the room
            without distorting it, centred there.
        """
        height, width = picture.pixels.shape[:2]
        return self.pasted(picture, self.fitting(into, width / height))

    def dimmed(self, by: float) -> Frame:
        """
        :param by: How far towards white, from zero to one.
        :return: A copy faded towards white.
        """
        faded = self.pixels.astype(np.float32) * (1.0 - by) + 255.0 * by
        return Frame(np.clip(faded + 0.5, 0, 255).astype(np.uint8))

    def blended(self, other: Frame, weight: float) -> Frame:
        """
        :param other: The frame shown when the weight is one.
        :param weight: How much of the other frame shows, from zero to one.
        :return: A mix of this frame and the other.
        """
        mixed = (
            self.pixels.astype(np.float32) * (1.0 - weight)
            + other.pixels.astype(np.float32) * weight
        )
        return Frame(np.clip(mixed + 0.5, 0, 255).astype(np.uint8))

    def darkened(self, over: PlanarBoundingBox, by: float) -> Frame:
        """
        A band shaded towards black, fading in from its top edge to its full darkness a
        third of the way down: what a caption is read on over footage.

        :param over: The band.
        :param by: How dark the band is at the bottom, from zero to one.
        :return: A copy with the band shaded.
        """
        result = self.pixels.copy()
        left, top, width, height = self.rounded(over)
        frame_height, frame_width = result.shape[:2]
        top, bottom = max(top, 0), min(top + height, frame_height)
        left, right = max(left, 0), min(left + width, frame_width)
        if bottom <= top or right <= left:
            return Frame(result)
        rows = np.arange(bottom - top, dtype=np.float32)
        weight = np.clip(rows / max((bottom - top) / 3.0, 1.0), 0.0, 1.0) * by
        band = result[top:bottom, left:right].astype(np.float32)
        band *= 1.0 - weight[:, None, None]
        result[top:bottom, left:right] = np.clip(band + 0.5, 0, 255).astype(np.uint8)
        return Frame(result)

    def shaded(self, over: PlanarBoundingBox, by: float, corner_radius: int) -> Frame:
        """
        :param over: The box.
        :param by: How dark it is, from zero to one.
        :param corner_radius: Pixels its corners are rounded by.
        :return: A copy with the box shaded evenly towards black, its corners rounded:
            what a caption is read on over any picture.
        """
        height, width = self.pixels.shape[:2]
        mask = Image.new("L", (width, height), 0)
        left, top, box_width, box_height = self.rounded(over)
        ImageDraw.Draw(mask).rounded_rectangle(
            (left, top, left + box_width - 1, top + box_height - 1),
            radius=corner_radius,
            fill=255,
        )
        weight = np.asarray(mask, dtype=np.float32)[..., None] / 255.0 * by
        darkened = self.pixels.astype(np.float32) * (1.0 - weight)
        return Frame(np.clip(darkened + 0.5, 0, 255).astype(np.uint8))

    def framed(
        self, around: PlanarBoundingBox, color: Color, thickness: int = 3
    ) -> Frame:
        """
        :param around: The box.
        :param color: What the outline is drawn in.
        :param thickness: Pixels the outline is thick.
        :return: A copy with the box outlined.
        """
        result = self.pixels.copy()
        left, top, width, height = self.rounded(around)
        cv2.rectangle(
            result,
            (left, top),
            (left + width, top + height),
            self.bytes_of(color),
            thickness,
        )
        return Frame(result)

    def filled(self, around: PlanarBoundingBox, color: Color) -> Frame:
        """
        :param around: The box.
        :param color: What it is painted in.
        :return: A copy with the box painted over.
        """
        result = self.pixels.copy()
        left, top, width, height = self.rounded(around)
        cv2.rectangle(
            result,
            (left, top),
            (left + width, top + height),
            self.bytes_of(color),
            -1,
        )
        return Frame(result)

    def lined(
        self, start: Point2, end: Point2, color: Color, thickness: int = 2
    ) -> Frame:
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
            self._pixel(start),
            self._pixel(end),
            self.bytes_of(color),
            thickness,
            cv2.LINE_AA,
        )
        return Frame(result)

    def arrowed(
        self,
        start: Point2,
        end: Point2,
        color: Color,
        thickness: int = 2,
        head_length: float = 12.0,
    ) -> Frame:
        """
        :param start: Where the arrow starts.
        :param end: Where its head is.
        :param color: What it is drawn in.
        :param thickness: Pixels it is thick.
        :param head_length: Pixels the head is long, at most half the arrow.
        :return: A copy with an arrow drawn on it.
        """
        result = self.pixels.copy()
        length = max(
            (
                (float(end.x) - float(start.x)) ** 2
                + (float(end.y) - float(start.y)) ** 2
            )
            ** 0.5,
            1.0,
        )
        cv2.arrowedLine(
            result,
            self._pixel(start),
            self._pixel(end),
            self.bytes_of(color),
            thickness,
            cv2.LINE_AA,
            tipLength=min(head_length / length, 0.5),
        )
        return Frame(result)
