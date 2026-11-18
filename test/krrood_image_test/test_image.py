"""
Tests for colour images: their size, pictures pasted and fitted into them, and the
shapes drawn on them.
"""

from __future__ import annotations

import numpy as np

from krrood_image.color import Color
from krrood_image.coordinates import ImageBox, ImagePoint, Resolution
from krrood_image.image import ColorImage

# %% an image of one colour


def test_an_image_of_a_colour_holds_its_bytes(resolution: Resolution) -> None:
    """
    Every pixel of a uniform image holds the colour's red, green and blue bytes.
    """
    color = Color.from_hex(hex_color="#1F2328")
    image = ColorImage.uniform(resolution=resolution, color=color)
    assert (image.pixels == tuple(color.to_rgb_bytes())).all()


def test_an_image_knows_its_resolution(
    black_image: ColorImage, resolution: Resolution
) -> None:
    """
    An image reports the columns and rows its pixel array has.
    """
    assert black_image.resolution == resolution


# %% pasting


def test_pasting_resizes_the_picture_into_the_box(
    black_image: ColorImage, picture_color: Color
) -> None:
    """
    A pasted picture fills exactly its box and leaves both the pixels around it and the
    original image untouched.
    """
    picture = ColorImage.uniform(
        resolution=Resolution(width=10, height=10), color=picture_color
    )
    left, top, width, height = 20, 30, 40, 20
    result = black_image.pasted(
        picture=picture,
        into=ImageBox.from_corner_and_size(
            left=left, top=top, width=width, height=height
        ),
    )
    inside = result.pixels[top : top + height, left : left + width]
    assert (inside == tuple(picture_color.to_rgb_bytes())).all()
    assert result.pixels[top - 1, left].max() == 0
    assert result.pixels[top, left - 1].max() == 0
    assert black_image.pixels.max() == 0


def test_pasting_crops_what_falls_outside_the_image(
    black_image: ColorImage, picture_color: Color, resolution: Resolution
) -> None:
    """
    The part of a box that hangs over the edge is cut off, so the image keeps its size.
    """
    picture = ColorImage.uniform(
        resolution=Resolution(width=10, height=10), color=picture_color
    )
    left, top, width, height = 180, -10, 40, 30
    result = black_image.pasted(
        picture=picture,
        into=ImageBox.from_corner_and_size(
            left=left, top=top, width=width, height=height
        ),
    )
    shown = result.pixels[0 : top + height, left : resolution.width]
    assert (shown == tuple(picture_color.to_rgb_bytes())).all()
    assert result.resolution == resolution


def test_fitting_a_picture_keeps_its_aspect_ratio(
    black_image: ColorImage, picture_color: Color, resolution: Resolution
) -> None:
    """
    A wide picture fitted into a taller room fills its width and is centred vertically,
    leaving the rows above and below it unpainted.
    """
    picture = ColorImage.uniform(
        resolution=Resolution(width=40, height=10), color=picture_color
    )
    result = black_image.fitted(
        picture=picture, into=ImageBox.covering(resolution=resolution)
    )
    top, bottom = 25, 75
    assert (result.pixels[top:bottom, :] == tuple(picture_color.to_rgb_bytes())).all()
    assert result.pixels[top - 1, :].max() == 0
    assert result.pixels[bottom, :].max() == 0


# %% tone


def test_dimming_moves_towards_white(black_image: ColorImage) -> None:
    """
    Dimming black halfway gives the middle grey byte.
    """
    assert black_image.dimmed(by=0.5).pixels[0, 0, 0] == 128


def test_blending_mixes_two_images_by_the_weight(
    black_image: ColorImage, resolution: Resolution
) -> None:
    """
    A weight of zero keeps this image, one shows the other, and a half mixes them
    evenly.
    """
    light = ColorImage.uniform(resolution=resolution, color=Color.WHITE())
    white = np.iinfo(np.uint8).max
    assert black_image.blended(other=light, weight=0.0).pixels.max() == 0
    assert black_image.blended(other=light, weight=1.0).pixels.min() == white
    assert black_image.blended(other=light, weight=0.5).pixels[0, 0, 0] == 128


# %% shapes


def test_filling_a_box_paints_it_in_the_colour(black_image: ColorImage) -> None:
    """
    A filled box is painted inside and leaves the pixels outside it as they were.
    """
    color = Color.from_hex(hex_color="#FF8800")
    filled = black_image.filled(
        around=ImageBox.from_corner_and_size(left=10, top=10, width=20, height=20),
        color=color,
    )
    assert tuple(filled.pixels[20, 20]) == tuple(color.to_rgb_bytes())
    assert filled.pixels[50, 50].max() == 0


def test_framing_a_box_outlines_it_and_leaves_its_inside(
    black_image: ColorImage,
) -> None:
    """
    A framed box is drawn along its edge while its inside keeps the image's pixels.
    """
    framed = black_image.framed(
        around=ImageBox.from_corner_and_size(left=20, top=20, width=60, height=40),
        color=Color.WHITE(),
    )
    assert framed.pixels[20, 50].min() == np.iinfo(np.uint8).max
    assert framed.pixels[40, 50].max() == 0


def test_a_line_and_an_arrow_are_drawn_between_their_points(
    black_image: ColorImage,
) -> None:
    """
    A line and an arrow both cover the straight path between their ends, and the arrow
    also draws a head.
    """
    start, end = ImagePoint(x=10, y=50), ImagePoint(x=190, y=50)
    lined = black_image.lined(start=start, end=end, color=Color.WHITE())
    arrowed = black_image.arrowed(start=start, end=end, color=Color.WHITE())
    white = np.iinfo(np.uint8).max
    assert lined.pixels[50, 100].min() == white
    assert lined.pixels[10, 100].max() == 0
    assert arrowed.pixels[50, 100].min() == white
    assert np.count_nonzero(arrowed.pixels) > np.count_nonzero(lined.pixels)
