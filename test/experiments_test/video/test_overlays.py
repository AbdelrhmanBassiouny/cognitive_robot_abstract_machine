"""
Tests for :mod:`experiments.video.overlays`: the progress bar drawn over the whole
video.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.canvas import DARK_THEME
from experiments.video.overlays import ProgressBar
from experiments.video.timeline import Resolution, Still, Timeline

RESOLUTION = Resolution(width=200, height=100)


@pytest.mark.parametrize("seconds", [0.0, 1.0, 2.0, 4.0])
def test_the_progress_bar_fills_the_top_of_the_frame_as_far_as_the_video_has_played(
    seconds: float,
) -> None:
    bar = ProgressBar(theme=DARK_THEME)
    drawn = bar.drawn_over(DARK_THEME.page_of(RESOLUTION), seconds, runs_for=4.0)
    played = round(RESOLUTION.width * seconds / 4.0)
    assert (drawn[: bar.thickness, :played] == DARK_THEME.accent).all()
    assert (drawn[: bar.thickness, played:] == DARK_THEME.panel).all()
    assert (drawn[bar.thickness :] == DARK_THEME.page).all()


def test_the_progress_bar_runs_on_across_the_scenes_of_a_timeline() -> None:
    bar = ProgressBar(theme=DARK_THEME)
    page = DARK_THEME.page_of(RESOLUTION)
    timeline = Timeline(
        [Still(page, held_for=2.0), Still(page, held_for=2.0)],
        frames_per_second=10,
        dissolve=0.0,
        overlays=[bar],
    )
    accent_columns = np.flatnonzero(
        (timeline.frame_at(3.0)[0] == DARK_THEME.accent).all(axis=1)
    )
    assert len(accent_columns) == round(RESOLUTION.width * 3.0 / timeline.duration)
