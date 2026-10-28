"""
Tests for colour images: their size, pictures pasted and fitted into them, and the
shapes drawn on them.
"""

from __future__ import annotations

import numpy as np

from krrimage.color import Color
from krrimage.coordinates import ImageBox, ImagePoint, Resolution
from krrimage.image import ColorImage

# %% an image of one colour


def test_an_image_of_a_colour_holds_its_bytes(resolution: Resolution) -> None:
    color = Color.from_hex("#1F2328")
    image = ColorImage.of_color(resolution, color)
    assert (image.pixels == tuple(color.to_rgb_bytes())).all()


def test_an_image_knows_its_resolution(
    black_image: ColorImage, resolution: Resolution
) -> None:
    assert black_image.resolution == resolution


# %% pasting


def test_pasting_resizes_the_picture_into_the_box(
    black_image: ColorImage, picture_color: Color
) -> None:
    picture = ColorImage.of_color(Resolution(10, 10), picture_color)
    left, top, width, height = 20, 30, 40, 20
    result = black_image.pasted(
        picture, ImageBox.from_corner_and_size(left, top, width, height)
    )
    inside = result.pixels[top : top + height, left : left + width]
    assert (inside == tuple(picture_color.to_rgb_bytes())).all()
    assert result.pixels[top - 1, left].max() == 0
    assert result.pixels[top, left - 1].max() == 0
    assert black_image.pixels.max() == 0


def test_pasting_crops_what_falls_outside_the_image(
    black_image: ColorImage, picture_color: Color, resolution: Resolution
) -> None:
    picture = ColorImage.of_color(Resolution(10, 10), picture_color)
    left, top, width, height = 180, -10, 40, 30
    result = black_image.pasted(
        picture, ImageBox.from_corner_and_size(left, top, width, height)
    )
    shown = result.pixels[0 : top + height, left : resolution.width]
    assert (shown == tuple(picture_color.to_rgb_bytes())).all()
    assert result.resolution == resolution


def test_fitting_a_picture_keeps_its_aspect_ratio(
    black_image: ColorImage, picture_color: Color, resolution: Resolution
) -> None:
    picture = ColorImage.of_color(Resolution(40, 10), picture_color)
    result = black_image.fitted(picture, ImageBox.covering(resolution))
    top, bottom = 25, 75
    assert (result.pixels[top:bottom, :] == tuple(picture_color.to_rgb_bytes())).all()
    assert result.pixels[top - 1, :].max() == 0
    assert result.pixels[bottom, :].max() == 0


# %% tone


def test_dimming_moves_towards_white(black_image: ColorImage) -> None:
    assert black_image.dimmed(0.5).pixels[0, 0, 0] == 128


def test_blending_mixes_two_images_by_the_weight(
    black_image: ColorImage, resolution: Resolution
) -> None:
    light = ColorImage.of_color(resolution, Color.WHITE())
    assert black_image.blended(light, 0.0).pixels.max() == 0
    assert black_image.blended(light, 1.0).pixels.min() == 255
    assert black_image.blended(light, 0.5).pixels[0, 0, 0] == 128


# %% shapes


def test_filling_a_box_paints_it_in_the_colour(black_image: ColorImage) -> None:
    color = Color.from_hex("#FF8800")
    filled = black_image.filled(ImageBox.from_corner_and_size(10, 10, 20, 20), color)
    assert tuple(filled.pixels[20, 20]) == tuple(color.to_rgb_bytes())
    assert filled.pixels[50, 50].max() == 0


def test_framing_a_box_outlines_it_and_leaves_its_inside(
    black_image: ColorImage,
) -> None:
    framed = black_image.framed(
        ImageBox.from_corner_and_size(20, 20, 60, 40), Color.WHITE()
    )
    assert framed.pixels[20, 50].min() == 255
    assert framed.pixels[40, 50].max() == 0


def test_a_line_and_an_arrow_are_drawn_between_their_points(
    black_image: ColorImage,
) -> None:
    start, end = ImagePoint(10, 50), ImagePoint(190, 50)
    lined = black_image.lined(start, end, Color.WHITE())
    arrowed = black_image.arrowed(start, end, Color.WHITE())
    assert lined.pixels[50, 100].min() == 255
    assert lined.pixels[10, 100].max() == 0
    assert arrowed.pixels[50, 100].min() == 255
    assert np.count_nonzero(arrowed.pixels) > np.count_nonzero(lined.pixels)
