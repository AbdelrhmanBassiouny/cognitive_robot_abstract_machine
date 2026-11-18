"""
Fixtures for the colour image tests: the size of the images drawn on, a black image of
that size and the colour pasted onto it.
"""

from __future__ import annotations

import pytest

from krrood_image.color import Color
from krrood_image.coordinates import Resolution
from krrood_image.image import ColorImage

# %% images to draw on


@pytest.fixture
def resolution() -> Resolution:
    """
    The size of the images drawn on, wider than it is tall.
    """
    return Resolution(width=200, height=100)


@pytest.fixture
def black_image(resolution: Resolution) -> ColorImage:
    """
    An image of that size, every pixel black.
    """
    return ColorImage.uniform(resolution=resolution, color=Color.BLACK())


@pytest.fixture
def picture_color() -> Color:
    """
    The one colour of the pictures pasted onto the black image.
    """
    return Color.from_hex(hex_color="#C8C8C8")
