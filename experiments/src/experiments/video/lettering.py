"""
The faces a video writes in, found the same way on every machine.
"""

from __future__ import annotations

from enum import StrEnum

from matplotlib import font_manager
from PIL import ImageFont


class Face(StrEnum):
    """
    The faces a video writes in, named as the font is.
    """

    REGULAR = "DejaVu Sans"
    BOLD = "DejaVu Sans:bold"
    MONO = "DejaVu Sans Mono"


def font(face: Face, size: int) -> ImageFont.FreeTypeFont:
    """
    The given face at the given size, found where matplotlib keeps its own copy of it,
    so a picture is set the same on every machine that has matplotlib.

    :param face: Which face.
    :param size: The size in pixels.
    """
    return ImageFont.truetype(
        font_manager.findfont(font_manager.FontProperties(face.value)), size
    )
