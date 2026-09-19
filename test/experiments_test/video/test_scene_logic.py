"""
Tests for the parts of the video's scenes that need no recording: when the robot
counts as standing still, what the support reading says, how a box's edges are found,
and how a film's speed-up sets a scene's length.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.footage import CameraFilm, ExecutionFootage, TimedImage
from experiments.video.perturbations import IdleStretches, Stretch
from experiments.video.timeline import Resolution
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
    stretch = Stretch(1.0, 2.0)
    assert stretch.holds(1.0) and stretch.holds(2.0) and not stretch.holds(2.01)


def test_the_robot_stands_still_outside_its_motions_with_a_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    idle = IdleStretches.__new__(IdleStretches)
    monkeypatch.setattr(IdleStretches, "moving", [Stretch(9.5, 22.5)], raising=False)
    assert idle.idle_at(5.0)
    assert not idle.idle_at(10.0)
    assert not idle.idle_at(22.0)
    assert idle.idle_at(30.0)


# %% the film


def test_a_film_answers_the_image_taken_last_before_a_moment() -> None:
    film = CameraFilm.__new__(CameraFilm)
    blank = Resolution(4, 4).blank()
    film.__dict__["images"] = [TimedImage(0.0, blank), TimedImage(0.3, blank), TimedImage(0.7, blank)]
    assert film.at(0.5).seconds == 0.3
    assert film.at(0.0).seconds == 0.0
    assert film.length == 0.7


def test_the_footage_lasts_the_stretch_divided_by_the_speed() -> None:
    film = CameraFilm.__new__(CameraFilm)
    film.__dict__["images"] = [TimedImage(0.0, Resolution(4, 4).blank()), TimedImage(40.0, Resolution(4, 4).blank())]
    assert ExecutionFootage(film, from_second=8.0, speed=4.0).duration == 8.0
    assert ExecutionFootage(film, from_second=0.0, to_second=20.0, speed=2.0).duration == 10.0
