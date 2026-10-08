"""
Tests for :mod:`experiments.video.footage`: film framed, read from its file, filling the
frame at a speed with a second view in its corner, and a title over it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

from experiments.video.canvas import MARGIN, VIDEO_RESOLUTION
from experiments.video.encoding import H264Encoder
from experiments.video.footage import (
    INSET_WIDTH,
    Framing,
    FullBleedFootage,
    HeldInset,
    TitleOverFootage,
    VideoFilm,
    ViewOfTheRun,
)
from experiments.video.timeline import Resolution, Still, Timeline

# %% framing


def test_a_framing_cuts_the_margins_it_names_off_a_picture() -> None:
    picture = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)
    framed = Framing(top=1, left=2, right=1, bottom=0).of(picture)
    assert framed.shape == (5, 5, 3)
    assert (framed == picture[1:6, 2:7]).all()


# %% a film read from its file


def test_a_film_read_from_a_file_answers_its_last_image_past_its_end(
    tmp_path: Path,
) -> None:
    resolution = Resolution(width=64, height=48)
    frames_per_second = 10
    timeline = Timeline(
        [
            Still(resolution.blank(0), held_for=1.0),
            Still(resolution.blank(255), held_for=1.0),
        ],
        frames_per_second=frames_per_second,
        dissolve=0.0,
    )
    video = H264Encoder(size_budget=200_000, preset="fast").encode(
        timeline, tmp_path / "film.mp4"
    )
    film = VideoFilm(video)
    assert film.length == pytest.approx(timeline.duration)
    assert film.image_at(0.5).mean() < 16
    assert film.image_at(1.5).mean() > 239
    assert film.image_at(film.length).mean() > 239


# %% a stretch of a film, filling the frame


@dataclass
class CountingFilm:
    """
    A film whose every picture says which second it was asked for, in its red byte.
    """

    shape: tuple
    length: float = 100.0
    asked: list = field(default_factory=list)

    def image_at(self, seconds: float) -> np.ndarray:
        self.asked.append(seconds)
        picture = np.zeros(self.shape, dtype=np.uint8)
        picture[..., 0] = int(seconds)
        return picture


def test_a_view_reads_its_film_from_where_its_stretch_starts_through_its_framing() -> (
    None
):
    film = CountingFilm((100, 200, 3))
    view = ViewOfTheRun(film, from_second=15.5, framing=Framing(top=10, bottom=10))
    picture = view.image_at(2.0)
    assert film.asked == [17.5]
    assert picture.shape == (80, 200, 3) and picture[0, 0, 0] == 17


def test_the_footage_fills_the_frame_with_the_inset_in_the_corner_in_step() -> None:
    own = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=18.0)
    by_hand = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=2.5)
    scene = FullBleedFootage(by_hand, length=30.0, speed=2.0, inset=own)
    assert scene.duration == pytest.approx(15.0)
    frame = scene.picture_at(2.0)
    assert frame.shape == (VIDEO_RESOLUTION.height, VIDEO_RESOLUTION.width, 3)
    assert own.film.asked[-1] == pytest.approx(18.0 + 4.0)
    assert by_hand.film.asked[-1] == pytest.approx(2.5 + 4.0)
    inset = scene.inset_panel
    assert inset.width == INSET_WIDTH and inset.right == VIDEO_RESOLUTION.width - MARGIN
    assert inset.bottom <= VIDEO_RESOLUTION.stage_height
    # the main view fills the frame: the footage's second is in every corner's red byte
    assert (
        frame[VIDEO_RESOLUTION.height - 1, 0, 0] == 6
        and frame[VIDEO_RESOLUTION.height - 1, 0, 1] == 0
    )


def test_the_inset_holds_what_it_is_given_before_it_runs() -> None:
    own = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=18.0)
    by_hand = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=0.0)
    held = np.full((90, 160, 3), 200, dtype=np.uint8)
    scene = FullBleedFootage(
        by_hand, length=10.0, speed=1.0, inset=own, inset_held=HeldInset(held, 3.0)
    )
    assert (scene.inset_picture_at(1.0) == 200).all()
    assert scene.inset_picture_at(4.0)[0, 0, 0] == 22


def test_the_title_stands_over_the_footage_and_fades_out_when_told() -> None:
    footage = FullBleedFootage(
        ViewOfTheRun(CountingFilm((90, 160, 3)), 0.0), length=6.0, speed=1.0
    )
    titled = TitleOverFootage(footage, "A Title", "a line", title_for=4.0, fade=0.5)
    assert titled.duration == pytest.approx(6.0)
    assert titled.title_at(1.0) == 1.0 and titled.title_at(4.5) == 0.0
    with_title = titled.picture_at(1.0)
    without = titled.picture_at(5.0)
    assert not np.array_equal(with_title, without)
    assert np.array_equal(without, footage.picture_at(5.0))


def test_the_footage_lasts_the_stretch_divided_by_the_speed() -> None:
    film = CountingFilm((90, 160, 3))
    assert (
        FullBleedFootage(ViewOfTheRun(film, 8.0), length=32.0, speed=4.0).duration
        == 8.0
    )
    assert (
        FullBleedFootage(ViewOfTheRun(film, 0.0), length=20.0, speed=2.0).duration
        == 10.0
    )
