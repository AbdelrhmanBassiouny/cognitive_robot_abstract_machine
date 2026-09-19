"""
Tests for :mod:`experiments.video.canvas`: rectangles moved and fitted, pictures pasted
into frames, and text set on them.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.canvas import (
    Anchor,
    Area,
    Typesetting,
    dimmed,
    fitted,
    pasted,
)
from experiments.video.timeline import Resolution

RESOLUTION = Resolution(width=200, height=100)

# %% rectangles


def test_a_rectangle_moves_part_of_the_way_towards_another() -> None:
    halfway = Area(0, 0, 10, 10).towards(Area(100, 50, 30, 20), 0.5)
    assert (halfway.x, halfway.y, halfway.width, halfway.height) == (50, 25, 20, 15)


def test_fitting_keeps_the_aspect_and_centres_in_the_room() -> None:
    room = Area(0, 0, 200, 100)
    square = room.fitting(1.0)
    assert (square.x, square.y, square.width, square.height) == (50, 0, 100, 100)
    wide = room.fitting(4.0)
    assert (wide.x, wide.y, wide.width, wide.height) == (0, 25, 200, 50)


def test_inset_shrinks_all_round() -> None:
    assert Area(10, 10, 100, 50).inset(5) == Area(15, 15, 90, 40)


# %% pasting


def test_pasting_resizes_the_picture_into_the_rectangle() -> None:
    frame = RESOLUTION.blank(0)
    picture = np.full((10, 10, 3), 200, dtype=np.uint8)
    result = pasted(frame, picture, Area(20, 30, 40, 20))
    assert result[30:50, 20:60].min() == 200
    assert result[29, 20].max() == 0 and result[30, 19].max() == 0
    assert frame.max() == 0


def test_pasting_crops_what_falls_outside_the_frame() -> None:
    frame = RESOLUTION.blank(0)
    picture = np.full((10, 10, 3), 200, dtype=np.uint8)
    result = pasted(frame, picture, Area(180, -10, 40, 30))
    assert result[0:20, 180:200].min() == 200
    assert result.shape == frame.shape


def test_fitting_a_picture_keeps_its_aspect() -> None:
    frame = RESOLUTION.blank(0)
    picture = np.full((10, 40, 3), 200, dtype=np.uint8)
    result = fitted(frame, picture, Area(0, 0, 200, 100))
    assert result[25:75, :].min() == 200
    assert result[24, :].max() == 0 and result[75, :].max() == 0


def test_dimming_moves_towards_white() -> None:
    assert dimmed(RESOLUTION.blank(0), 0.5)[0, 0, 0] == 128


# %% writing


def test_text_is_written_where_asked() -> None:
    frame = RESOLUTION.blank(255)
    written = Typesetting(size=20).written(frame, "ab", (10, 50), Anchor.LEFT_MIDDLE)
    rows, columns = np.nonzero(written[:, :, 0] < 128)
    assert 10 <= columns.min() < 15
    assert 40 <= rows.min() < 50 <= rows.max() < 62


def test_wrapping_breaks_at_spaces_to_fit_the_width() -> None:
    setting = Typesetting(size=20)
    wide = setting.width_of("one two three four")
    wrapped = setting.wrapped("one two three four", wide / 2)
    assert wrapped.count("\n") >= 1
    assert all(setting.width_of(line) <= wide / 2 for line in wrapped.split("\n"))
    assert wrapped.replace("\n", " ") == "one two three four"
