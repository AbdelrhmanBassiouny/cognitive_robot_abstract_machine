"""
Writing on a picture: the one face and the one way of laying a line of text on a strip
of colour that every picture of a card shares.

A card is read as one figure, so the name of a level, the caption under a camera frame
and the title over the whole thing are all set the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont
from typing_extensions import Tuple

from semantic_digital_twin.world_description.geometry import Color

# %% the face everything is written in


class Face(StrEnum):
    """
    The faces a card writes in, named as the font is.
    """

    REGULAR = "DejaVu Sans"
    BOLD = "DejaVu Sans:bold"


def drawn(color: Color) -> Tuple[int, int, int]:
    """
    A colour of the twin as the channel values a picture is written on with.

    :param color: The colour the twin states.
    """
    return tuple(round(channel * 255) for channel in color.to_rgb())


def font(face: Face, size: int) -> ImageFont.FreeTypeFont:
    """
    The given face at the given size, found where matplotlib keeps its own copy of it,
    so a card is set the same on every machine that draws its charts.

    :param face: Which face.
    :param size: The size in pixels.
    """
    return ImageFont.truetype(
        font_manager.findfont(font_manager.FontProperties(face.value)), size
    )


# %% one line of text on a strip


@dataclass(frozen=True)
class Lettering:
    """
    How a line of text is set on a strip of colour.
    """

    size: int = 22
    """
    The height of the letters, in pixels.
    """

    face: Face = Face.REGULAR
    """
    The face they are set in.
    """

    color: Color = Color(0.1, 0.1, 0.12, 1.0)
    """
    What they are written in.
    """

    inset: int = 16
    """
    How far from the left edge of the strip the text starts, in pixels.
    """

    def band(self, text: str, width: int, height: int, background: Color) -> np.ndarray:
        """
        A strip of one colour with the text written across it, in the middle of its
        height.

        :param text: What to write.
        :param width: How wide the strip is, in pixels.
        :param height: How tall it is, in pixels.
        :param background: What the strip is.
        :return: The strip as red, green and blue.
        """
        strip = Image.new("RGB", (width, height), drawn(background))
        self.write_on(strip, text, (self.inset, height / 2))
        return np.asarray(strip)

    def write_on(
        self, picture: Image.Image, text: str, at: Tuple[float, float]
    ) -> None:
        """
        Write a line on the given picture, its left edge and vertical middle at the
        given point.

        :param picture: The picture to write on.
        :param text: What to write.
        :param at: Where the line's left edge and vertical middle go, in pixels.
        """
        ImageDraw.Draw(picture).text(
            at,
            text,
            fill=drawn(self.color),
            font=font(self.face, self.size),
            anchor="lm",
        )
