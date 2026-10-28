from __future__ import annotations

import pytest

from krrimage.color import Color
from krrimage.coordinates import Resolution
from krrimage.image import ColorImage

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
    return ColorImage.of_color(resolution, Color.BLACK())


@pytest.fixture
def picture_color() -> Color:
    """
    The one colour of the pictures pasted onto the black image.
    """
    return Color.from_hex("#C8C8C8")
