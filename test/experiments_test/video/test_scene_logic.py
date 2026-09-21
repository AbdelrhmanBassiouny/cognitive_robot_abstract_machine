"""
Tests for the parts of the video's scenes that need no recording: when the robot
counts as standing still, what the support reading says, how a box's edges are found,
how a film's speed-up sets a scene's length, and what a framing cuts off a picture.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from experiments.video.cache import SceneCache
from experiments.video.footage import (
    ACTING_FRAMING,
    SIDE_BY_SIDE_GAP,
    TABLE_FRAMING,
    CameraFilm,
    ExecutionFootage,
    Framing,
    SideBySide,
    TimedImage,
    ViewOfTheRun,
)
from experiments.video.perturbations import IdleStretches, RecordingStretch
from experiments.video.timeline import Resolution
from experiments.video.twin import BoxCorners, SupportReading, WorkingMemoryCheck

# %% boxes


@dataclass
class FlatViewpoint:
    """
    A view straight down: a point's x and y are its pixels, scaled.
    """

    def project(self, points: np.ndarray) -> np.ndarray:
        return points[:, :2] * 100.0 + 50.0


@dataclass
class TwinStandIn:
    """
    A twin whose every picture is blank, with a cube resting on a lid.
    """

    reading: SupportReading = field(
        default_factory=lambda: SupportReading(
            supported=BoxCorners(lower=np.array([0.5, 0.5, 0.099]), upper=np.array([0.7, 0.7, 0.3])),
            supporting=BoxCorners(lower=np.array([0.0, 0.0, 0.0]), upper=np.array([1.5, 1.0, 0.1])),
            vertical_overlap=0.001,
            maximum=0.01,
            holds=True,
        )
    )

    def viewpoint(self, progress: float) -> FlatViewpoint:
        return FlatViewpoint()

    def before_the_spawn(self) -> np.ndarray:
        return np.full((120, 200, 3), 255, dtype=np.uint8)

    def along_the_flight(self, progress: float) -> np.ndarray:
        return self.before_the_spawn()


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


def test_the_check_draws_the_boxes_the_band_and_the_verdict_at_the_moments_it_is_given() -> None:
    check = WorkingMemoryCheck(
        TwinStandIn(), flight_from=1.0, flight_for=1.0, boxes_for=3.0, boxes_at=(0.2, 0.6), band_at=1.2, verdict_at=2.0,
        resolution=Resolution(width=400, height=240),
    )
    assert check.duration == pytest.approx(5.0)
    landed = check.flight_from + check.flight_for

    def inked(seconds: float) -> int:
        picture = check.frame_at(seconds)[: int(check.resolution.stage_height) - 80]
        return int((picture.min(axis=2) < 250).sum())

    assert inked(landed + 0.1) == 0  # nothing drawn yet
    lid_box = inked(landed + 0.5)
    both_boxes = inked(landed + 1.1)
    banded = inked(landed + 1.5)
    assert 0 < lid_box < both_boxes < banded
    verdict = check.frame_at(landed + 2.5)
    assert not np.array_equal(verdict, check.frame_at(landed + 1.5))


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


# %% two cameras side by side


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


def test_a_view_reads_its_film_from_where_its_stretch_starts_through_its_framing() -> None:
    film = CountingFilm((100, 200, 3))
    view = ViewOfTheRun(film, from_second=15.5, framing=Framing(top=10, bottom=10), caption="by hand")
    picture = view.image_at(2.0)
    assert film.asked == [17.5]
    assert picture.shape == (80, 200, 3) and picture[0, 0, 0] == 17


def test_the_views_play_in_step_at_one_speed_beside_each_other_at_one_height() -> None:
    own = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=19.5, caption="the robot's own camera")
    by_hand = ViewOfTheRun(CountingFilm((150, 100, 3)), from_second=4.0, caption="a camera held by hand")
    scene = SideBySide((own, by_hand), length=28.0, speed=7.0)
    assert scene.duration == pytest.approx(4.0)
    left, right = scene.panels
    assert left.height == pytest.approx(right.height)
    assert left.right + SIDE_BY_SIDE_GAP == pytest.approx(right.x)
    assert left.width / left.height == pytest.approx(160 / 90, rel=1e-3)
    assert right.width / right.height == pytest.approx(100 / 150, rel=1e-3)
    assert right.right <= scene.resolution.width - SIDE_BY_SIDE_GAP
    scene.picture_at(2.0)
    assert own.film.asked[-1] == pytest.approx(19.5 + 14.0)
    assert by_hand.film.asked[-1] == pytest.approx(4.0 + 14.0)


def test_the_side_by_side_keeps_the_subtitle_band_clear_and_states_its_speed() -> None:
    own = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=0.0)
    by_hand = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=0.0)
    scene = SideBySide((own, by_hand), length=8.0, speed=4.0, caption="the cube put through the hole")
    frame = scene.picture_at(0.0)
    stage = scene.resolution.stage_height
    assert (frame[int(stage) :, :, :] == 255).all()
    assert max(panel.bottom for panel in scene.panels) < stage - 60
