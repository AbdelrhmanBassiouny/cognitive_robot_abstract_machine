"""
Tests for :mod:`experiments.video.chapters`: the claim comes up large when a chapter
opens and shrinks into the pill that stays for the chapter.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.canvas import MARGIN, VIDEO_RESOLUTION, Ink
from experiments.video.chapters import PILL_HEIGHT, ChapterMark, InChapter, chaptered
from experiments.video.script import CHAPTERS
from experiments.video.timeline import Still

MARK = ChapterMark(CHAPTERS[1], len(CHAPTERS))


def page(shade: int = 255) -> Still:
    return Still(VIDEO_RESOLUTION.blank(shade), held_for=6.0)


def test_the_pill_stands_in_the_top_left_corner_in_the_videos_dark() -> None:
    frame = MARK.pill_drawn(page().picture)
    inside = (MARGIN + PILL_HEIGHT // 2, MARGIN + 4)
    assert tuple(frame[inside]) == Ink.TEXT.rgb
    assert frame[MARGIN - 2, MARGIN + 4].min() == 255
    assert frame[MARGIN + PILL_HEIGHT + 2, MARGIN + 4].min() == 255


def test_the_claim_comes_up_large_over_a_dimmed_page_and_shaded_footage() -> None:
    on_page = MARK.claim_drawn(page(240).picture, 1.0)
    assert on_page.min() < 128  # letters
    corner = on_page[VIDEO_RESOLUTION.height - 10, 10]
    assert 240 < corner.mean() < 255  # the page faded towards white
    on_footage = MARK.claim_drawn(page(120).picture, 1.0)
    assert on_footage[VIDEO_RESOLUTION.height - 10, 10].mean() < 120  # shaded
    assert on_footage.max() == 255  # white letters
    assert np.array_equal(MARK.claim_drawn(page().picture, 0.0), page().picture)


def test_a_scene_that_opens_the_chapter_shows_the_claim_then_the_pill_and_a_later_one_the_pill_alone() -> None:
    opening = InChapter(page(), MARK, opens=True, claim_for=2.0, fade=0.5)
    later = InChapter(page(), MARK)
    assert opening.duration == 6.0 and later.duration == 6.0
    assert opening.claim_at(1.0) == 1.0 and opening.claim_at(2.5) == 0.0 and later.claim_at(1.0) == 0.0
    assert np.array_equal(opening.picture_at(4.0), later.picture_at(4.0))
    assert not np.array_equal(opening.picture_at(1.0), later.picture_at(1.0))
    inside = (MARGIN + PILL_HEIGHT // 2, MARGIN + 4)
    assert tuple(later.picture_at(1.0)[inside]) == Ink.TEXT.rgb


def test_the_claim_can_wait_and_nothing_of_the_chapter_shows_before_it() -> None:
    scene = InChapter(page(), MARK, opens=True, claim_from=4.0, claim_for=1.0, fade=0.5)
    assert np.array_equal(scene.picture_at(1.0), page().picture)
    assert scene.claim_at(4.5) == 1.0
    assert scene.claim_at(5.5) == 0.0


def test_chaptered_scenes_share_the_mark_and_the_first_opens() -> None:
    scenes = chaptered([page(), page(), page()], MARK)
    assert [scene.opens for scene in scenes] == [True, False, False]
    assert all(scene.mark is MARK for scene in scenes)


def test_the_held_for_of_a_held_scene_is_reached_through_the_chapter() -> None:
    scene = InChapter(page(), MARK)
    scene.held_for = 9.0
    assert scene.scene.held_for == 9.0 and scene.duration == 9.0
    assert scene.dissolves_in
    with pytest.raises(AttributeError):
        _ = InChapter(Still.__new__(Still), MARK).held_for
