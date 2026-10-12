"""
Tests for :mod:`cramcorder.footage` and :mod:`cramcorder.footage_scenes`:

film framed, read from its file, filling the frame at a speed with a second view in its
corner, and a title over it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
from semantic_digital_twin.spatial_types.spatial_types import Point2

from cramcorder.encoding import EncoderPreset, H264Encoder
from cramcorder.footage import (
    Film,
    FootageFrame,
    Framing,
    VideoFilm,
    ViewOfTheRun,
)
from cramcorder.footage_scenes import (
    FootageScene,
    InsetStill,
    TitleOverFootage,
)
from cramcorder.frame import Frame, Resolution
from cramcorder.timeline import Still, Timeline
from cramcorder.typesetting import Anchor

NO_TIME = timedelta(0)
CAMERA_SIZE = Resolution(width=160, height=90)
STILL_GREY = 200


def seconds(amount: float) -> timedelta:
    """
    :return: That many seconds.
    """
    return timedelta(seconds=amount)


# %% framing


def test_a_framing_cuts_the_margins_it_names_off_a_picture() -> None:
    rows, columns = 6, 8
    pixels = np.arange(rows * columns * 3, dtype=np.uint8).reshape(rows, columns, 3)
    framing = Framing(top=1, left=2, right=1, bottom=0)
    framed = framing.of(Frame(pixels)).pixels
    assert framed.shape == (
        rows - framing.top - framing.bottom,
        columns - framing.left - framing.right,
        3,
    )
    assert (framed == pixels[1:6, 2:7]).all()


# %% a film read from its file


def test_a_film_read_from_a_file_answers_its_last_image_past_its_end(
    tmp_path: Path,
) -> None:
    resolution = Resolution(width=64, height=48)
    hold = seconds(1)
    timeline = Timeline(
        [
            Still(resolution.blank(0), held_for=hold),
            Still(resolution.blank(255), held_for=hold),
        ],
        frames_per_second=10,
        dissolve=NO_TIME,
    )
    video = H264Encoder(size_budget=200_000, preset=EncoderPreset.FAST).encode(
        timeline, tmp_path / "film.mp4"
    )
    film = VideoFilm(video)
    dark_limit, light_limit = 16, 239
    assert film.length.total_seconds() == pytest.approx(
        timeline.duration.total_seconds(), abs=0.1
    )
    assert film.image_at(seconds(0.5)).pixels.mean() < dark_limit
    assert film.image_at(seconds(1.5)).pixels.mean() > light_limit
    assert film.image_at(film.length).pixels.mean() > light_limit


# %% a stretch of a film, filling the frame


@dataclass
class CountingFilm(Film):
    """
    A film whose every picture says which second it was asked for, in its red byte.
    """

    resolution: Resolution = CAMERA_SIZE
    length: timedelta = seconds(100)
    asked: list = field(default_factory=list)

    def image_at(self, moment: timedelta) -> Frame:
        self.asked.append(moment)
        pixels = np.zeros(self.resolution.shape, dtype=np.uint8)
        pixels[..., 0] = int(moment.total_seconds())
        return Frame(pixels)


def test_a_view_reads_its_film_from_where_its_stretch_starts_through_its_framing() -> (
    None
):
    film = CountingFilm(Resolution(width=200, height=100))
    starts_at, into = seconds(15.5), seconds(2)
    framing = Framing(top=10, bottom=10)
    picture = ViewOfTheRun(film, starts_at=starts_at, framing=framing).image_at(into)
    assert film.asked == [starts_at + into]
    assert picture.pixels.shape == (80, 200, 3)
    assert picture.pixels[0, 0, 0] == int((starts_at + into).total_seconds())


def test_the_footage_fills_the_frame_with_the_inset_in_the_corner_in_step() -> None:
    inset_start, main_start = seconds(18), seconds(2.5)
    length, speed, moment = seconds(30), 2.0, seconds(2)
    own = ViewOfTheRun(CountingFilm(), starts_at=inset_start)
    by_hand = ViewOfTheRun(CountingFilm(), starts_at=main_start)
    scene = FootageScene(by_hand, length=length, speed=speed, inset=own)
    assert scene.duration == length / speed
    frame = scene.picture_at(moment)
    assert frame.resolution == scene.resolution
    assert own.film.asked[-1] == inset_start + moment * speed
    assert by_hand.film.asked[-1] == main_start + moment * speed
    inset = scene.inset_panel
    assert inset.max_x - inset.min_x == scene.inset_width
    assert inset.max_x == scene.resolution.width - scene.resolution.margin
    assert inset.max_y <= scene.resolution.stage_height
    # the main view fills the frame: the footage's second is in every corner's red byte
    bottom_left = frame.pixels[scene.resolution.height - 1, 0]
    assert bottom_left[0] == int((main_start + moment * speed).total_seconds())
    assert bottom_left[1] == 0


def test_the_inset_shows_what_it_is_given_before_it_runs() -> None:
    inset_start, shown_for = seconds(18), seconds(3)
    own = ViewOfTheRun(CountingFilm(), starts_at=inset_start)
    by_hand = ViewOfTheRun(CountingFilm(), starts_at=NO_TIME)
    picture = CAMERA_SIZE.blank(STILL_GREY)
    scene = FootageScene(
        by_hand,
        length=seconds(10),
        speed=1.0,
        inset=own,
        inset_still=InsetStill(picture, shown_for),
    )
    assert (scene.inset_picture_at(seconds(1)).pixels == STILL_GREY).all()
    later = seconds(4)
    assert scene.inset_picture_at(later).pixels[0, 0, 0] == int(
        (inset_start + later).total_seconds()
    )


def test_the_title_stands_over_the_footage_and_fades_out_when_told() -> None:
    footage = FootageScene(
        ViewOfTheRun(CountingFilm(), NO_TIME), length=seconds(6), speed=1.0
    )
    title_for, fade = seconds(4), seconds(0.5)
    titled = TitleOverFootage(
        footage, "A Title", "a line", title_for=title_for, fade=fade
    )
    assert titled.duration == footage.duration
    assert titled.title_at(seconds(1)) == 1.0
    assert titled.title_at(title_for + fade) == 0.0
    with_title = titled.picture_at(seconds(1))
    after_the_fade = seconds(5)
    without = titled.picture_at(after_the_fade)
    assert not np.array_equal(with_title.pixels, without.pixels)
    assert np.array_equal(without.pixels, footage.picture_at(after_the_fade).pixels)


@pytest.mark.parametrize(
    "length, speed", [(seconds(32), 4.0), (seconds(20), 2.0)], ids=["fast", "slow"]
)
def test_the_footage_lasts_the_stretch_divided_by_the_speed(
    length: timedelta, speed: float
) -> None:
    scene = FootageScene(
        ViewOfTheRun(CountingFilm(), NO_TIME), length=length, speed=speed
    )
    assert scene.duration == length / speed


def test_footage_at_its_own_pace_carries_no_speed_badge() -> None:
    scene = FootageScene(
        ViewOfTheRun(CountingFilm(), NO_TIME), length=seconds(5), speed=1.0
    )
    main = scene.main.image_at(NO_TIME)
    unbadged = scene.resolution.blank(0).pasted(main, scene.resolution.whole)
    assert np.array_equal(scene.picture_at(NO_TIME).pixels, unbadged.pixels)


# %% badges


def test_a_badge_stands_at_the_corner_it_is_anchored_to() -> None:
    resolution = Resolution(width=400, height=200)
    footage = FootageFrame(role_taker=resolution.blank(0))
    corner = Point2(300, 100)
    text = "×2"
    for anchor in (Anchor.LEFT_TOP, Anchor.RIGHT_TOP, Anchor.RIGHT_MIDDLE):
        badged = footage.badged(text, corner, anchor).pixels
        changed_rows, changed_columns = np.nonzero(badged.max(axis=2))
        if anchor is Anchor.LEFT_TOP:
            assert changed_columns.min() >= float(corner.x)
            assert changed_rows.min() >= float(corner.y)
        else:
            assert changed_columns.max() <= float(corner.x)
        if anchor is Anchor.RIGHT_MIDDLE:
            assert changed_rows.max() <= float(corner.y)


def test_the_speed_badge_stands_in_the_top_right_corner_inside_the_margin() -> None:
    resolution = Resolution(width=400, height=200)
    badged = FootageFrame(role_taker=resolution.blank(0)).speed_badged(4.0).pixels
    rows, columns = np.nonzero(badged.max(axis=2))
    assert columns.max() <= resolution.width - resolution.margin
    assert rows.min() >= resolution.margin
