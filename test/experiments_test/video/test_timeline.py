"""
Tests for :mod:`experiments.video.timeline`: scenes laid end to end, dissolving into one
another, and read out as a stream of frames at a fixed rate.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.timeline import (
    Frame,
    Resolution,
    Scene,
    Still,
    Timeline,
    eased,
)

RESOLUTION = Resolution(width=64, height=32)


def flat(value: int) -> Frame:
    """
    A frame of one grey value.
    """
    return np.full((RESOLUTION.height, RESOLUTION.width, 3), value, dtype=np.uint8)


# %% one scene


def test_a_still_shows_the_same_frame_for_its_whole_duration() -> None:
    still = Still(picture=flat(200), held_for=1.5)
    assert still.duration == 1.5
    assert np.array_equal(still.frame_at(0.0), flat(200))
    assert np.array_equal(still.frame_at(1.4), flat(200))


def test_a_scene_refuses_a_moment_outside_its_duration() -> None:
    still = Still(picture=flat(0), held_for=1.0)
    with pytest.raises(ValueError):
        still.frame_at(1.0)


# %% the timeline


def test_the_timeline_lays_scenes_end_to_end_without_a_dissolve() -> None:
    timeline = Timeline(
        scenes=[Still(flat(10), 0.5), Still(flat(20), 0.25)],
        frames_per_second=4,
        dissolve=0.0,
    )
    frames = list(timeline.frames())
    assert timeline.duration == 0.75
    assert len(frames) == 3
    assert [int(frame[0, 0, 0]) for frame in frames] == [10, 10, 20]


def test_a_dissolve_blends_the_end_of_one_scene_into_the_start_of_the_next() -> None:
    timeline = Timeline(
        scenes=[Still(flat(0), 1.0), Still(flat(100), 1.0)],
        frames_per_second=4,
        dissolve=0.5,
    )
    assert timeline.duration == 1.5
    values = [int(frame[0, 0, 0]) for frame in timeline.frames()]
    assert len(values) == 6
    assert values[:2] == [0, 0]
    assert values[-2:] == [100, 100]
    # the two frames in the dissolve climb from the first scene towards the second
    assert 0 <= values[2] < values[3] < 100


def test_the_timeline_rejects_scenes_of_different_sizes() -> None:
    other = np.zeros((RESOLUTION.height, RESOLUTION.width + 1, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        list(
            Timeline(
                scenes=[Still(flat(0), 0.25), Still(other, 0.25)],
                frames_per_second=4,
                dissolve=0.0,
            ).frames()
        )


# %% easing


@pytest.mark.parametrize("progress, expected", [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)])
def test_easing_keeps_the_ends_and_the_middle(progress: float, expected: float) -> None:
    assert eased(progress) == pytest.approx(expected)


def test_easing_starts_and_ends_slowly() -> None:
    assert eased(0.1) < 0.1
    assert eased(0.9) > 0.9


def test_easing_clamps_beyond_its_range() -> None:
    assert eased(-1.0) == 0.0
    assert eased(2.0) == 1.0


def test_a_scene_may_draw_down_to_the_band_left_for_subtitles() -> None:
    from experiments.video.timeline import SUBTITLE_BAND_SHARE

    resolution = Resolution(width=1600, height=900)
    assert resolution.stage_height == pytest.approx(900 * (1 - SUBTITLE_BAND_SHARE))
    assert 0.10 <= SUBTITLE_BAND_SHARE <= 0.15


# %% a scene that cuts in


class Cut(Still):
    """
    A still that cuts in rather than dissolving.
    """

    @property
    def dissolves_in(self) -> bool:
        return False


def test_a_scene_that_cuts_in_takes_no_dissolve_from_the_scene_before() -> None:
    timeline = Timeline(scenes=[Still(flat(10), 1.0), Cut(flat(20), 1.0), Still(flat(30), 1.0)], frames_per_second=10, dissolve=0.5)
    assert timeline.dissolve_into(1) == 0.0 and timeline.dissolve_into(2) == 0.5 and timeline.dissolve_into(0) == 0.0
    assert timeline.duration == pytest.approx(2.5)
    assert timeline.starts() == pytest.approx([0.0, 1.0, 1.5])
    assert int(timeline.frame_at(1.0)[0, 0, 0]) == 20  # no blend at the cut
    assert int(timeline.frame_at(0.9)[0, 0, 0]) == 10
    assert 20 < int(timeline.frame_at(1.75)[0, 0, 0]) < 30  # the dissolve after it as usual
