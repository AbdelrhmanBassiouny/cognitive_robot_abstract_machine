"""
Tests for :mod:`experiments.video.slides`: the opening and closing slides carry the
script's words and nothing that names anyone.
"""

from __future__ import annotations

import numpy as np

from experiments.video.canvas import Ink
from experiments.video.script import PAPER_ID, VideoScript
from experiments.video.slides import ClosingSlide, TitleSlide
from experiments.video.taxonomy import STEP_FADE, TaxonomySlide
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


def test_the_closing_slide_is_drawn_at_the_asked_size() -> None:
    frame = ClosingSlide(script=VideoScript(), resolution=SMALL).frame_at(1.0)
    assert frame.shape == SMALL.shape
    assert np.any(frame < 255)


def test_the_script_names_no_robot_by_default() -> None:
    assert VideoScript().robot_name == "the robot"


# %% the taxonomy slide


def test_the_taxonomy_slide_shows_the_query_the_tree_and_the_choice_in_that_order() -> None:
    slide = TaxonomySlide(steps_at=(0.0, 2.0, 4.0), held_for=6.0)
    assert slide.duration == 6.0
    on_card = (int(slide.card.y + 4), int(slide.card.x + 4))
    on_root = (int(slide.root.y + 1), int(slide.root.centre[0]))
    on_pill = (int(slide.choice.y + 1), int(slide.choice.centre[0]))
    after_query = slide.frame_at(STEP_FADE)
    assert tuple(after_query[on_card]) == Ink.BUBBLE.rgb
    assert tuple(after_query[on_root]) == (255, 255, 255) and tuple(after_query[on_pill]) == (255, 255, 255)
    after_tree = slide.frame_at(2.0 + STEP_FADE)
    assert tuple(after_tree[on_root]) == Ink.TEXT.rgb and tuple(after_tree[on_pill]) == (255, 255, 255)
    assert tuple(slide.frame_at(4.0 + STEP_FADE)[on_pill]) == Ink.ASKED.rgb


def test_every_leaf_of_the_taxonomy_lies_under_its_kind_and_above_the_subtitles() -> None:
    slide = TaxonomySlide()
    for kind_index, kind in enumerate(slide.tree.children):
        box = slide.kind(kind_index)
        for index in range(len(kind.children)):
            leaf = slide.leaf(kind_index, index)
            assert leaf.y > box.bottom and box.x <= leaf.x
            assert leaf.bottom <= slide.resolution.stage_height
