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
from experiments.video.canvas import MARGIN, VIDEO_RESOLUTION
from experiments.video.footage import (
    FULL_BLEED_FRAMING,
    INSET_WIDTH,
    TABLE_FRAMING,
    CameraFilm,
    Framing,
    FullBleedFootage,
    HeldInset,
    TimedImage,
    TitleOverFootage,
    ViewOfTheRun,
)
from experiments.video.perturbations import (
    IdleStretches,
    PerturbationTile,
    PerturbingStretches,
    Phase,
    RecordingStretch,
)
from experiments.video.stages import PANEL_VISUAL
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
    [(0.0021, "overlap 2 mm ≤ 0.1 m"), (0.00012, "overlap 0.1 mm ≤ 0.1 m"), (0.15, "overlap 150 mm > 0.1 m")],
)
def test_the_reading_line_states_the_comparison_the_predicate_makes(overlap: float, expected: str) -> None:
    box = BoxCorners(lower=np.zeros(3), upper=np.ones(3))
    reading = SupportReading(supported=box, supporting=box, vertical_overlap=overlap, maximum=0.1, holds=overlap < 0.1)
    assert reading.reading_line == expected


# %% standing still


def test_the_check_draws_the_boxes_the_band_and_the_result_at_the_moments_it_is_given() -> None:
    check = WorkingMemoryCheck(
        TwinStandIn(), held_for=5.0, boxes_at=(0.2, 0.6), band_at=1.2, verdict_at=2.0,
        resolution=Resolution(width=400, height=240),
    )
    assert check.duration == pytest.approx(5.0)

    def inked(seconds: float) -> int:
        return int((check.frame_at(seconds).min(axis=2) < 250).sum())

    assert inked(0.1) == 0  # nothing drawn yet
    lid_box = inked(0.5)
    both_boxes = inked(1.1)
    banded = inked(1.5)
    assert 0 < lid_box < both_boxes < banded
    assert not np.array_equal(check.frame_at(2.5), check.frame_at(1.5))


def test_the_check_draws_at_the_panels_size_and_starts_on_the_landed_view() -> None:
    check = WorkingMemoryCheck(TwinStandIn())
    assert check.resolution == PANEL_VISUAL
    assert check.frame_at(0.0).shape == (PANEL_VISUAL.height, PANEL_VISUAL.width, 3)


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


def test_a_person_is_perturbing_through_the_stretches_measured(monkeypatch: pytest.MonkeyPatch) -> None:
    perturbing = PerturbingStretches.__new__(PerturbingStretches)
    monkeypatch.setattr(PerturbingStretches, "perturbing", [RecordingStretch(9.1, 25.3)], raising=False)
    assert not perturbing.perturbing_at(9.0)
    assert perturbing.perturbing_at(9.1) and perturbing.perturbing_at(25.3)
    assert not perturbing.perturbing_at(25.4)


@dataclass
class StretchesStandIn:
    """
    Stretches that hold the moments they are given.
    """

    held: list

    def idle_at(self, seconds: float) -> bool:
        return not self.perturbing_at(seconds)

    def perturbing_at(self, seconds: float) -> bool:
        return any(start <= seconds <= end for start, end in self.held)


def test_a_tile_is_badged_perturbation_over_executing_over_perceiving(monkeypatch: pytest.MonkeyPatch) -> None:
    tile = PerturbationTile.__new__(PerturbationTile)
    tile.film = StillFilm(np.zeros((1080, 1920, 3), dtype=np.uint8))  # type: ignore[assignment]
    tile.framing = Framing()
    tile.perturbing = StretchesStandIn([(5.0, 19.0)])  # type: ignore[assignment]
    tile.idle = StretchesStandIn([(0.0, 20.0)])  # type: ignore[assignment]
    monkeypatch.setattr(PerturbationTile, "_drawn_at", lambda self, image: (image.image, image.seconds > 30.0))
    assert tile.picture_at(10.0)[1] is Phase.PERTURBATION
    assert tile.picture_at(15.0)[1] is Phase.PERTURBATION  # robot idle, but a person is at the scene
    assert tile.picture_at(25.0)[1] is None  # idle, nothing drawn
    assert tile.picture_at(35.0)[1] is Phase.PERCEIVING
    tile.idle = StretchesStandIn([(0.0, 40.0)])  # type: ignore[assignment]
    assert tile.picture_at(35.0)[1] is Phase.EXECUTING


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
    film = CountingFilm((90, 160, 3))
    assert FullBleedFootage(ViewOfTheRun(film, 8.0), length=32.0, speed=4.0).duration == 8.0
    assert FullBleedFootage(ViewOfTheRun(film, 0.0), length=20.0, speed=2.0).duration == 10.0


# %% framing


def test_a_framing_cuts_the_margins_it_names_off_a_picture() -> None:
    picture = np.arange(6 * 8 * 3, dtype=np.uint8).reshape(6, 8, 3)
    framed = Framing(top=1, left=2, right=1, bottom=0).of(picture)
    assert framed.shape == (5, 5, 3)
    assert (framed == picture[1:6, 2:7]).all()


def test_the_table_framing_keeps_a_full_hd_recording_at_sixteen_by_nine() -> None:
    recording = np.zeros((1080, 1920, 3), dtype=np.uint8)
    height, width = TABLE_FRAMING.of(recording).shape[:2]
    assert (height, width) == (910, 1618)
    assert width / height == pytest.approx(16 / 9, abs=0.002)


def test_the_full_bleed_framing_cuts_an_upright_film_to_sixteen_by_nine() -> None:
    upright = np.zeros((1920, 1080, 3), dtype=np.uint8)
    height, width = FULL_BLEED_FRAMING.of(upright).shape[:2]
    assert width == 1080
    assert width / height == pytest.approx(16 / 9, abs=0.002)


@dataclass
class StillImage:
    image: np.ndarray
    seconds: float = 0.0


@dataclass
class StillFilm:
    """
    A film of one picture, whatever the moment.
    """

    picture: np.ndarray
    length: float = 1.0

    def at(self, seconds: float) -> StillImage:
        return StillImage(self.picture, seconds)


# %% the run seen from beside the table, with the robot's own view


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
    assert frame[VIDEO_RESOLUTION.height - 1, 0, 0] == 6 and frame[VIDEO_RESOLUTION.height - 1, 0, 1] == 0


def test_the_inset_holds_what_it_is_given_before_it_runs() -> None:
    own = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=18.0)
    by_hand = ViewOfTheRun(CountingFilm((90, 160, 3)), from_second=0.0)
    held = np.full((90, 160, 3), 200, dtype=np.uint8)
    scene = FullBleedFootage(by_hand, length=10.0, speed=1.0, inset=own, inset_held=HeldInset(held, 3.0))
    assert (scene.inset_picture_at(1.0) == 200).all()
    assert scene.inset_picture_at(4.0)[0, 0, 0] == 22


def test_the_title_stands_over_the_footage_and_fades_out_when_told() -> None:
    footage = FullBleedFootage(ViewOfTheRun(CountingFilm((90, 160, 3)), 0.0), length=6.0, speed=1.0)
    titled = TitleOverFootage(footage, "A Title", "a line", title_for=4.0, fade=0.5)
    assert titled.duration == pytest.approx(6.0)
    assert titled.title_at(1.0) == 1.0 and titled.title_at(4.5) == 0.0
    with_title = titled.picture_at(1.0)
    without = titled.picture_at(5.0)
    assert not np.array_equal(with_title, without)
    assert np.array_equal(without, footage.picture_at(5.0))
