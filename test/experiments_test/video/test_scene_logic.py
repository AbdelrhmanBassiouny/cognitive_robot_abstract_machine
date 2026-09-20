"""
Tests for the parts of the video's scenes that need no recording: when the robot
counts as standing still, what the support reading says, how a box's edges are found,
how a film's speed-up sets a scene's length, and what a framing cuts off a picture.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from experiments.video.cache import SceneCache
from experiments.video.footage import (
    ACTING_FRAMING,
    TABLE_FRAMING,
    CameraFilm,
    ExecutionFootage,
    Framing,
    TimedImage,
)
from experiments.video.perturbations import IdleStretches, RecordingStretch
from experiments.video.twin import BoxCorners, SupportReading

# %% boxes


def test_a_box_has_twelve_edges_each_joining_corners_that_differ_in_one_axis() -> None:
    box = BoxCorners(lower=np.zeros(3), upper=np.ones(3))
    assert len(box.edges) == 12
    corners = box.corners
    for a, b in box.edges:
        assert np.count_nonzero(corners[a] != corners[b]) == 1


def test_boxes_intersect_where_they_overlap_and_not_otherwise() -> None:
    lower = BoxCorners(lower=np.array([0.0, 0.0, 0.0]), upper=np.array([1.0, 1.0, 1.0]))
    resting = BoxCorners(lower=np.array([0.2, 0.2, 0.998]), upper=np.array([0.4, 0.4, 1.2]))
    band = lower.intersected(resting)
    assert band is not None
    assert band.upper[2] - band.lower[2] == pytest.approx(0.002)
    apart = BoxCorners(lower=np.array([2.0, 2.0, 2.0]), upper=np.array([3.0, 3.0, 3.0]))
    assert lower.intersected(apart) is None


# %% the support reading


@pytest.mark.parametrize(
    "overlap, expected",
    [(0.0021, "vertical overlap 2 mm < 0.1 m"), (0.00012, "vertical overlap 0.1 mm < 0.1 m"), (0.15, "vertical overlap 150 mm ≥ 0.1 m")],
)
def test_the_reading_line_states_the_comparison_the_predicate_makes(overlap: float, expected: str) -> None:
    box = BoxCorners(lower=np.zeros(3), upper=np.ones(3))
    reading = SupportReading(supported=box, supporting=box, vertical_overlap=overlap, maximum=0.1, holds=overlap < 0.1)
    assert reading.reading_line == expected


# %% standing still


def test_a_stretch_holds_its_ends() -> None:
    stretch = RecordingStretch(1.0, 2.0)
    assert stretch.holds(1.0) and stretch.holds(2.0) and not stretch.holds(2.01)


def test_the_robot_stands_still_outside_its_motions_with_a_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    idle = IdleStretches.__new__(IdleStretches)
    monkeypatch.setattr(IdleStretches, "moving", [RecordingStretch(9.5, 22.5)], raising=False)
    assert idle.idle_at(5.0)
    assert not idle.idle_at(10.0)
    assert not idle.idle_at(22.0)
    assert idle.idle_at(30.0)


# %% the film


def timed(seconds: float) -> TimedImage:
    """
    An image stamp with nothing behind it.
    """
    return TimedImage(seconds, SceneCache("unused"), "none")


def test_a_film_answers_the_image_taken_last_before_a_moment() -> None:
    film = CameraFilm.__new__(CameraFilm)
    film.__dict__["images"] = [timed(0.0), timed(0.3), timed(0.7)]
    assert film.at(0.5).seconds == 0.3
    assert film.at(0.0).seconds == 0.0
    assert film.length == 0.7


def test_the_footage_lasts_the_stretch_divided_by_the_speed() -> None:
    film = CameraFilm.__new__(CameraFilm)
    film.__dict__["images"] = [timed(0.0), timed(40.0)]
    assert ExecutionFootage(film, from_second=8.0, speed=4.0).duration == 8.0
    assert ExecutionFootage(film, from_second=0.0, to_second=20.0, speed=2.0).duration == 10.0


# %% framing


def test_a_framing_cuts_the_margins_it_names_off_a_picture() -> None:
    picture = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)
    framed = Framing(top=1, left=2, right=1, bottom=0).of(picture)
    assert framed.shape == (5, 5, 3)
    assert (framed == picture[1:6, 2:7]).all()


@pytest.mark.parametrize("framing, size", [(TABLE_FRAMING, (910, 1618)), (ACTING_FRAMING, (1020, 1813))])
def test_a_framing_keeps_a_full_hd_recording_at_sixteen_by_nine(framing: Framing, size: tuple) -> None:
    recording = np.zeros((1080, 1920, 3), dtype=np.uint8)
    height, width = framing.of(recording).shape[:2]
    assert (height, width) == size
    assert width / height == pytest.approx(16 / 9, abs=0.002)


def test_the_acting_framing_keeps_more_of_the_top_and_the_left_than_the_tables() -> None:
    assert ACTING_FRAMING.top < TABLE_FRAMING.top and ACTING_FRAMING.left < TABLE_FRAMING.left


@dataclass
class StillImage:
    image: np.ndarray


@dataclass
class StillFilm:
    """
    A film of one picture, whatever the moment.
    """

    picture: np.ndarray
    length: float = 1.0

    def at(self, seconds: float) -> StillImage:
        return StillImage(self.picture)


def test_the_footage_shows_the_recording_through_its_framing() -> None:
    picture = np.zeros((1080, 1920, 3), dtype=np.uint8)
    picture[:170, :, :] = 255  # what lies above the table is white
    footage = ExecutionFootage(StillFilm(picture), speed=1.0, framing=TABLE_FRAMING)  # type: ignore[arg-type]
    frame = footage.picture_at(0.0)
    assert (frame[2:40, frame.shape[1] // 2] == 0).all()
    unframed = ExecutionFootage(StillFilm(picture), speed=1.0, framing=Framing())  # type: ignore[arg-type]
    assert (unframed.picture_at(0.0)[2:40, frame.shape[1] // 2] == 255).all()
