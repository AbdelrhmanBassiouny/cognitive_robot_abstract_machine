"""
Tests for :mod:`experiments.video.canvas`: rectangles moved and fitted, pictures pasted
into frames, and text set on them.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.lettering import Face
from experiments.video.canvas import (
    changed_spans,
    DARK_THEME,
    NEUTRAL_THEME,
    CodeTypesetting,
    Token,
    tokenised,
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


# %% code, coloured


def test_a_line_of_code_comes_apart_into_calls_classes_names_strings_and_numbers() -> (
    None
):
    pieces = tokenised('an(entity(trial.episode).where(contains(name, "cube"), 3))')
    kinds = {piece: kind for piece, kind in pieces}
    assert kinds["an"] is Token.CALL and kinds["where"] is Token.CALL
    assert kinds["trial"] is Token.NAME and kinds["episode"] is Token.NAME
    assert kinds['"cube"'] is Token.STRING and kinds["3"] is Token.NUMBER
    assert kinds["("] is Token.PUNCTUATION
    assert tokenised("a(MotionEvent)")[2][1] is Token.CLASS
    assert (
        "".join(piece for piece, _ in pieces)
        == 'an(entity(trial.episode).where(contains(name, "cube"), 3))'
    )


def test_coloured_code_is_as_wide_as_the_same_line_in_one_ink_and_carries_its_inks() -> (
    None
):
    line = 'a(MotionEvent)("x")'
    code = CodeTypesetting(size=24)
    assert code.width_of(line) == Typesetting(size=24, face=Face.MONO).width_of(line)
    frame = code.written(np.full((60, 400, 3), 255, dtype=np.uint8), line, (10, 30))
    inks = {tuple(pixel) for pixel in frame.reshape(-1, 3)}
    assert (
        NEUTRAL_THEME.code_inks[Token.CLASS] in inks
        and NEUTRAL_THEME.code_inks[Token.STRING] in inks
        and NEUTRAL_THEME.code_inks[Token.CALL] in inks
    )


def test_the_changed_spans_of_a_line_are_the_pieces_that_differ_from_the_earlier_line() -> (
    None
):
    before = "    contains(tick.events, motion := a(MotionEvent)()),"
    after = "    contains(tick.events, pickup := a(PickUpEvent)()),"
    spans = changed_spans(before, after)
    assert [after[first:after_last] for first, after_last in spans] == [
        "pickup",
        "PickUpEvent",
    ]
    assert changed_spans(after, after) == []
    assert changed_spans("", "a(Tick)()") == [(0, 9)]


def test_a_marked_stretch_of_code_is_filled_behind_in_the_marker_and_nothing_else_is() -> (
    None
):
    line = "pickup := a(PickUpEvent)()"
    code = CodeTypesetting(size=24)
    blank = np.full((60, 600, 3), 255, dtype=np.uint8)
    marked = code.written(blank, line, (10, 30), marked=[(10, 24)])
    plain = code.written(blank, line, (10, 30))
    assert tuple(marked[30, int(10 + code.width_of(line[:12]))]) in {
        NEUTRAL_THEME.marker,
        NEUTRAL_THEME.code_inks[Token.CLASS],
    }
    assert tuple(marked[30, int(10 + code.width_of("pi") + 1)]) != NEUTRAL_THEME.marker
    assert NEUTRAL_THEME.marker in {tuple(pixel) for pixel in marked.reshape(-1, 3)}
    assert NEUTRAL_THEME.marker not in {tuple(pixel) for pixel in plain.reshape(-1, 3)}


# %% themes


def test_a_theme_fills_a_page_with_its_page_colour() -> None:
    page = DARK_THEME.page_of(RESOLUTION)
    assert page.shape == RESOLUTION.shape
    assert (page == DARK_THEME.page).all()


def test_text_set_in_a_theme_is_written_in_its_text_colour_and_typeface() -> None:
    lettering = DARK_THEME.typesetting(size=24, face=Face.BOLD)
    assert lettering.typeface == DARK_THEME.typeface
    written = lettering.written(DARK_THEME.page_of(RESOLUTION), "Theme", (10, 50))
    assert DARK_THEME.text in {tuple(pixel) for pixel in written.reshape(-1, 3)}


def test_code_is_coloured_in_the_inks_of_its_theme() -> None:
    line = 'Tick(name="pick")'
    code = CodeTypesetting(size=24, theme=DARK_THEME)
    written = code.written(DARK_THEME.page_of(Resolution(400, 60)), line, (10, 30))
    inks = {tuple(pixel) for pixel in written.reshape(-1, 3)}
    assert DARK_THEME.code_inks[Token.CLASS] in inks
    assert DARK_THEME.code_inks[Token.STRING] in inks
    assert NEUTRAL_THEME.code_inks[Token.CLASS] not in inks
