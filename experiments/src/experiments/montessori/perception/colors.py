"""
The colours each kind of detection is drawn in, wherever it is drawn.

Kept in one place so a piece looks the same in rviz as it does in the camera window, and
a reader comparing the two is not misled by the same thing wearing two colours.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Tuple

from semantic_digital_twin.world_description.geometry import Color

# %% writing a colour into an image


@dataclass(frozen=True)
class BgrPixel:
    """
    A pixel of an 8-bit image as OpenCV draws one: blue first, then green, then red,
    each a whole number of steps.
    """

    full_intensity: int = 255
    """
    The step a part of the colour reaches when it is at its strongest.
    """

    def value_of(self, color: Color) -> Tuple[int, int, int]:
        """
        :param color: The colour to write into the pixel.
        :return: The pixel's blue, green and red parts.
        """
        return tuple(
            round(part * self.full_intensity) for part in (color.B, color.G, color.R)
        )


# %% what each kind is drawn in


PIECE_COLOR = Color(0.1, 0.9, 0.3)
"""
Colour a loose piece is drawn in.
"""

HOLE_COLOR = Color(1.0, 0.6, 0.0)
"""
Colour a hole in the board is drawn in.
"""

BOARD_COLOR = Color(0.3, 0.5, 1.0)
"""
Colour the board itself is drawn in.
"""

LABEL_COLOR = Color(1.0, 1.0, 1.0)
"""
Colour a detection's name is written in.
"""
