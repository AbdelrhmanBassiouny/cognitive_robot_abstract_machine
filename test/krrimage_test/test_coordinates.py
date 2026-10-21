"""
Tests for positions and boxes on an image.
"""

from __future__ import annotations

from krrimage.coordinates import ImageBox, ImagePoint, Pixel, PixelBox, Resolution

# %% boxes anywhere on an image


def test_a_box_from_its_corner_and_size_has_that_corner_and_size() -> None:
    left, top, width, height = 1.5, 2.5, 10.0, 4.0
    box = ImageBox.from_corner_and_size(left, top, width, height)
    assert (box.left, box.top, box.width, box.height) == (left, top, width, height)
    assert box.lower == ImagePoint(left, top)


def test_the_box_covering_an_image_covers_every_pixel(resolution: Resolution) -> None:
    assert PixelBox.nearest(ImageBox.covering(resolution)) == PixelBox.between(
        0, 0, resolution.width, resolution.height
    )


def test_the_largest_centred_box_keeps_the_aspect_ratio(
    resolution: Resolution,
) -> None:
    room = ImageBox.covering(resolution)
    square = room.largest_centred(1.0)
    assert PixelBox.nearest(square) == PixelBox.between(50, 0, 150, 100)
    wide = room.largest_centred(4.0)
    assert PixelBox.nearest(wide) == PixelBox.between(0, 25, 200, 75)


# %% whole pixels


def test_a_position_falls_on_the_nearest_pixel() -> None:
    assert Pixel.nearest(ImagePoint(3.4, 7.6)) == Pixel(column=3, row=8)


def test_a_pixel_box_runs_from_its_top_left_pixel_to_its_bottom_right_one() -> None:
    left, top, width, height = 10, 20, 10, 5
    box = PixelBox.between(left, top, left + width, top + height)
    assert box.lower == Pixel(column=left, row=top)
    assert box.upper == Pixel(column=left + width - 1, row=top + height - 1)
    assert (box.width, box.height) == (width, height)


def test_a_box_clipped_to_an_image_is_cut_at_its_edges(
    resolution: Resolution,
) -> None:
    hanging_over = PixelBox.between(-10, 90, 40, 120)
    assert hanging_over.clipped_to(resolution) == PixelBox.between(
        0, 90, 40, resolution.height
    )


def test_a_box_outside_an_image_covers_no_pixel_of_it(
    resolution: Resolution,
) -> None:
    beyond = PixelBox.between(resolution.width + 5, 0, resolution.width + 15, 10)
    assert beyond.clipped_to(resolution).is_empty is True
