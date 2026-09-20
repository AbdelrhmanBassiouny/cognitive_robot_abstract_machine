"""
Tests for :mod:`experiments.video.slides`: the opening and closing slides carry the
script's words and nothing that names anyone.
"""

from __future__ import annotations

import numpy as np

from experiments.video.canvas import Ink
from experiments.video.script import PAPER_ID, NarrationLines, VideoScript
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


def test_the_submission_line_carries_the_papers_number() -> None:
    assert f"Paper ID {PAPER_ID}" in VideoScript().submission_line
    assert "Paper ID 1234" in VideoScript(paper_id="1234").submission_line


def test_the_title_is_the_submitted_papers() -> None:
    assert VideoScript().title == (
        "A Unified Knowledge Representation and Reasoning Framework for "
        "Cognitive Architectures"
    )


def test_the_title_slide_shows_the_summary_only_once_its_line_starts() -> None:
    # at the video's own size: the slide's offsets are laid out for it
    without = TitleSlide(script=VideoScript(), held_for=6.0, fade=0.5)
    with_summary = TitleSlide(script=VideoScript(), held_for=6.0, fade=0.5, summary_at=3.0)
    assert np.array_equal(with_summary.frame_at(2.9), without.frame_at(2.9))
    later = with_summary.frame_at(4.0)
    height = with_summary.resolution.height
    # the summary sits below the submission line, above the subtitles' band
    lower_band = slice(int(height * 0.68), int(with_summary.resolution.stage_height))
    assert np.all(without.frame_at(4.0)[lower_band] == 255)
    assert np.any(later[lower_band] < 128)
    assert np.all(later[int(with_summary.resolution.stage_height) :] == 255)


def test_the_summary_is_said_in_the_slides_words() -> None:
    summary, line = VideoScript().summary, NarrationLines().summary
    assert summary[0].isupper() and summary.endswith(".")
    assert summary[0].lower() + summary[1:] in line.written
    for connected in ("perception", "memory", "probabilistic reasoning", "logical inference", "robot action"):
        assert connected in summary


def test_the_closing_slide_is_drawn_at_the_asked_size() -> None:
    frame = ClosingSlide(script=VideoScript(), resolution=SMALL).frame_at(1.0)
    assert frame.shape == SMALL.shape
    assert np.any(frame < 255)


def test_the_script_names_no_robot_by_default() -> None:
    assert VideoScript().robot_name == "the robot"
