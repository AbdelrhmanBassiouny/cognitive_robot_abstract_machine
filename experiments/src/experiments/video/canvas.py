"""
Drawing on a frame: where things go, what they are written in, and the colours the
figure already uses, so every scene of the video looks like one piece with the paper.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np
from PIL import Image, ImageDraw
from typing_extensions import Optional, Sequence, Tuple

from experiments.paper.lettering import Face, font
from experiments.video.timeline import Frame, Resolution

Rgb = Tuple[int, int, int]
"""
A colour as red, green and blue bytes.
"""

VIDEO_RESOLUTION = Resolution(width=1280, height=720)
"""
The size the video is drawn at: the conference asks for at least 480 rows, and 720 is
what the byte limit leaves room for over three minutes.
"""

# %% the colours


class Ink(Enum):
    """
    The colours the framework figure is drawn in, for the video to write in the same.
    """

    TEXT = (0x1F, 0x23, 0x28)
    MUTED = (0x6B, 0x72, 0x80)
    HAIRLINE = (0xCF, 0xD4, 0xDC)
    BUBBLE = (0xF6, 0xF7, 0xF9)
    PAPER = (0xFF, 0xFF, 0xFF)
    PERCEPTION = (0x0F, 0x76, 0x6E)
    PERCEPTION_FILL = (0xD9, 0xF0, 0xEC)
    SIMULATION = (0x1D, 0x4E, 0xD8)
    SIMULATION_FILL = (0xDB, 0xE7, 0xFB)
    PROBABILISTIC = (0xB4, 0x53, 0x09)
    PROBABILISTIC_FILL = (0xFD, 0xEB, 0xD0)
    RULES = (0x6D, 0x28, 0xD9)
    RULES_FILL = (0xEB, 0xE4, 0xFB)
    FIRED = (0x15, 0x80, 0x3D)
    FAILED = (0xB9, 0x1C, 0x1C)

    @property
    def rgb(self) -> Rgb:
        """
        The colour as bytes.
        """
        return self.value


# %% where things go


@dataclass(frozen=True)
class Area:
    """
    A stretch of a frame, in pixels from its top left corner.
    """

    x: float
    """
    Its left edge.
    """

    y: float
    """
    Its top edge.
    """

    width: float
    """
    How wide it is.
    """

    height: float
    """
    How tall it is.
    """

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def centre(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def aspect(self) -> float:
        """
        Width over height.
        """
        return self.width / self.height

    def towards(self, other: Area, progress: float) -> Area:
        """
        The rectangle part of the way from this one to another.

        :param other: Where it ends up.
        :param progress: How far along, from zero to one.
        """
        return Area(
            x=self.x + (other.x - self.x) * progress,
            y=self.y + (other.y - self.y) * progress,
            width=self.width + (other.width - self.width) * progress,
            height=self.height + (other.height - self.height) * progress,
        )

    def inset(self, by: float) -> Area:
        """
        :param by: How far in from every edge, in pixels.
        :return: The rectangle shrunk by that much all round.
        """
        return Area(
            self.x + by, self.y + by, self.width - 2 * by, self.height - 2 * by
        )

    def fitting(self, aspect: float) -> Area:
        """
        The largest rectangle of the given aspect centred in this one.

        :param aspect: Width over height.
        """
        if self.aspect > aspect:
            height = self.height
            width = height * aspect
        else:
            width = self.width
            height = width / aspect
        return Area(
            self.x + (self.width - width) / 2,
            self.y + (self.height - height) / 2,
            width,
            height,
        )

    def rounded(self) -> Tuple[int, int, int, int]:
        """
        Left, top, width and height as whole pixels.
        """
        left, top = int(round(self.x)), int(round(self.y))
        return left, top, int(round(self.right)) - left, int(round(self.bottom)) - top

    @classmethod
    def whole(cls, resolution: Resolution) -> Area:
        """
        :return: The rectangle covering a frame of the given size.
        """
        return cls(0, 0, resolution.width, resolution.height)


# %% pasting


def pasted(frame: Frame, picture: Frame, into: Area) -> Frame:
    """
    A copy of the frame with a picture resized into a rectangle of it, cropped to the
    frame where the rectangle leaves it.

    :param frame: The frame drawn on.
    :param picture: What to paste.
    :param into: Where, and how big.
    """
    result = frame.copy()
    left, top, width, height = into.rounded()
    if width <= 0 or height <= 0:
        return result
    resized = cv2.resize(picture, (width, height), interpolation=cv2.INTER_AREA)
    frame_height, frame_width = frame.shape[:2]
    x0, y0 = max(left, 0), max(top, 0)
    x1, y1 = min(left + width, frame_width), min(top + height, frame_height)
    if x1 <= x0 or y1 <= y0:
        return result
    result[y0:y1, x0:x1] = resized[y0 - top : y1 - top, x0 - left : x1 - left]
    return result


def fitted(frame: Frame, picture: Frame, into: Area) -> Frame:
    """
    A copy of the frame with a picture pasted as large as it goes into a rectangle
    without distorting it, centred there.

    :param frame: The frame drawn on.
    :param picture: What to paste.
    :param into: The room it may take.
    """
    return pasted(frame, picture, into.fitting(picture.shape[1] / picture.shape[0]))


def dimmed(frame: Frame, by: float) -> Frame:
    """
    A copy of the frame faded towards white.

    :param frame: The frame.
    :param by: How far towards white, from zero to one.
    """
    faded = frame.astype(np.float32) * (1.0 - by) + 255.0 * by
    return np.clip(faded + 0.5, 0, 255).astype(np.uint8)


def framed(frame: Frame, around: Area, color: Rgb, thickness: int = 3) -> Frame:
    """
    A copy of the frame with a rectangle outlined on it.
    """
    result = frame.copy()
    left, top, width, height = around.rounded()
    cv2.rectangle(result, (left, top), (left + width, top + height), color, thickness)
    return result


def filled(frame: Frame, around: Area, color: Rgb) -> Frame:
    """
    A copy of the frame with a rectangle painted over it.
    """
    result = frame.copy()
    left, top, width, height = around.rounded()
    cv2.rectangle(result, (left, top), (left + width, top + height), color, -1)
    return result


# %% writing


class Anchor(Enum):
    """
    Which point of a line of text is put where it is written, as the drawing library
    names anchors.
    """

    LEFT_MIDDLE = "lm"
    CENTRE_MIDDLE = "mm"
    RIGHT_MIDDLE = "rm"
    LEFT_TOP = "lt"
    CENTRE_TOP = "mt"


@dataclass(frozen=True)
class Typesetting:
    """
    How a line of text is written on a frame.
    """

    size: int = 24
    """
    The height of the letters, in pixels.
    """

    face: Face = Face.REGULAR
    """
    The face they are set in.
    """

    color: Rgb = Ink.TEXT.rgb
    """
    What they are written in.
    """

    def written(
        self,
        frame: Frame,
        text: str,
        at: Tuple[float, float],
        anchor: Anchor = Anchor.LEFT_MIDDLE,
    ) -> Frame:
        """
        A copy of the frame with the text written on it.

        :param frame: The frame written on.
        :param text: What to write; new lines break it.
        :param at: Where the anchor goes, in pixels.
        :param anchor: Which point of the text goes there.
        """
        picture = Image.fromarray(frame)
        ImageDraw.Draw(picture).multiline_text(
            at,
            text,
            fill=self.color,
            font=font(self.face, self.size),
            anchor=anchor.value if "\n" not in text else anchor.value[0] + "a",
            align="center" if anchor.value[0] == "m" else "left",
            spacing=self.size * 0.35,
        )
        return np.asarray(picture)

    def width_of(self, text: str) -> float:
        """
        :param text: One line.
        :return: How many pixels wide it is set.
        """
        return font(self.face, self.size).getlength(text)

    def wrapped(self, text: str, width: float) -> str:
        """
        The text broken into lines no wider than given, at spaces.

        :param text: What to break.
        :param width: The widest a line may be, in pixels.
        """
        lines: list[str] = []
        line = ""
        for word in text.split():
            candidate = word if not line else f"{line} {word}"
            if self.width_of(candidate) <= width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return "\n".join(lines)
