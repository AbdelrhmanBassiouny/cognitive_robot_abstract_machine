"""
The faces a video writes in, found the same way on every machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from matplotlib import font_manager
from PIL import ImageFont


class Face(Enum):
    """
    The faces a typeface sets text in.
    """

    REGULAR = auto()
    """
    Running text.
    """

    BOLD = auto()
    """
    Headings and values that stand out.
    """

    MONO = auto()
    """
    Code.
    """


@dataclass(frozen=True)
class Typeface:
    """
    The fonts a video sets each face in, named as matplotlib finds fonts.
    """

    regular: str = "DejaVu Sans"
    """
    The font of running text.
    """

    bold: str = "DejaVu Sans:bold"
    """
    The font of headings.
    """

    mono: str = "DejaVu Sans Mono"
    """
    The font of code.
    """

    def name_of(self, face: Face) -> str:
        """
        :param face: A face.
        :return: The font this typeface sets it in.
        """
        return {Face.REGULAR: self.regular, Face.BOLD: self.bold, Face.MONO: self.mono}[
            face
        ]

    def font(self, face: Face, size: int) -> ImageFont.FreeTypeFont:
        """
        The given face at the given size, found where matplotlib keeps fonts, so a
        picture is set the same on every machine that has the font; the default fonts
        come with matplotlib itself.

        :param face: Which face.
        :param size: The size in pixels.
        :raises ValueError: If no font of the face's name is installed.
        """
        found = font_manager.findfont(
            font_manager.FontProperties(self.name_of(face)), fallback_to_default=False
        )
        return ImageFont.truetype(found, size)
