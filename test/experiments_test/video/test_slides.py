"""
Tests for :mod:`experiments.video.slides`: the opening and closing slides carry the
script's words and nothing that names anyone.
"""

from __future__ import annotations

import numpy as np

from experiments.video.script import PAPER_ID_PLACEHOLDER, VideoScript
from experiments.video.slides import ClosingSlide, TitleSlide
from experiments.video.timeline import Resolution

SMALL = Resolution(width=640, height=360)


def test_the_title_slide_fades_in_from_white() -> None:
    slide = TitleSlide(script=VideoScript(), held_for=4.0, fade=1.0, resolution=SMALL)
    assert slide.frame_at(0.0).min() == 255
    assert slide.frame_at(3.0).min() < 128


def test_the_title_slide_lasts_as_long_as_asked() -> None:
    assert (
        TitleSlide(script=VideoScript(), held_for=4.0, resolution=SMALL).duration == 4.0
    )


def test_the_submission_line_carries_the_placeholder_until_the_id_is_known() -> None:
    assert PAPER_ID_PLACEHOLDER in VideoScript().submission_line
    assert "Paper ID 1234" in VideoScript(paper_id="1234").submission_line


def test_the_closing_slide_is_drawn_at_the_asked_size() -> None:
    frame = ClosingSlide(script=VideoScript(), resolution=SMALL).frame_at(1.0)
    assert frame.shape == SMALL.shape
    assert np.any(frame < 255)


def test_the_script_names_no_robot_by_default() -> None:
    assert VideoScript().robot_name == "the robot"
