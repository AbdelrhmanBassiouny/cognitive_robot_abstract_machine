"""
Tests for :mod:`cramcorder.overlays`: the progress bar drawn over the whole video.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pytest

from cramcorder.frame import Frame, Resolution
from cramcorder.overlays import ProgressBar
from cramcorder.theme import VideoTheme
from cramcorder.timeline import Still, Timeline

FRAME_SIZE = Resolution(width=200, height=100)
RUNS_FOR = timedelta(seconds=4)


@pytest.mark.parametrize("played_seconds", [0.0, 1.0, 2.0, 4.0])
def test_the_progress_bar_fills_the_top_of_the_frame_as_far_as_the_video_has_played(
    played_seconds: float,
) -> None:
    theme = VideoTheme.dark()
    bar = ProgressBar(theme=theme)
    drawn = bar.drawn_over(
        theme.page_of(FRAME_SIZE), timedelta(seconds=played_seconds), RUNS_FOR
    ).pixels
    played = round(FRAME_SIZE.width * played_seconds / RUNS_FOR.total_seconds())
    assert (drawn[: bar.thickness, :played] == Frame.bytes_of(theme.accent)).all()
    assert (drawn[: bar.thickness, played:] == Frame.bytes_of(theme.panel)).all()
    assert (drawn[bar.thickness :] == Frame.bytes_of(theme.page)).all()


def test_the_progress_bar_runs_on_across_the_scenes_of_a_timeline() -> None:
    theme = VideoTheme.dark()
    page = theme.page_of(FRAME_SIZE)
    hold = timedelta(seconds=2)
    moment = timedelta(seconds=3)
    timeline = Timeline(
        [Still(page, held_for=hold), Still(page, held_for=hold)],
        frames_per_second=10,
        dissolve=timedelta(0),
        overlays=[ProgressBar(theme=theme)],
    )
    top_row = timeline.frame_at(moment).pixels[0]
    accent_columns = np.flatnonzero(
        (top_row == Frame.bytes_of(theme.accent)).all(axis=1)
    )
    assert len(accent_columns) == round(FRAME_SIZE.width * moment / timeline.duration)
