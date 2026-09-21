"""
Tests for :mod:`experiments.video.query_slide`: the introduction in three beats on one
slide, each coming up as the narration reaches it.
"""

from __future__ import annotations

import numpy as np

from experiments.video.canvas import CLAIM_SIZE, Area, CodeTypesetting, Ink
from experiments.video.query_slide import (
    CODE_SIZE,
    MOVE,
    STEP_FADE,
    BackendKind,
    ExampleQuery,
    IntroductionMoments,
    IntroductionSlide,
)
from experiments.video.script import NarrationLines, VideoScript

MOMENTS = IntroductionMoments(example=0.0, open_field=2.0, gloss=3.0, backends=6.0, hero=12.0)


def slide_with(moments: IntroductionMoments = MOMENTS) -> IntroductionSlide:
    script = VideoScript()
    return IntroductionSlide(script.backend_choice, script.principle, script.statement_label, script.backends_label, moments=moments, held_for=16.0)


def drawn(slide: IntroductionSlide, area: Area, seconds: float) -> bool:
    """
    Whether anything darker than a card is drawn in an area of the slide at a moment.
    """
    frame = slide.frame_at(seconds)
    x, y, width, height = area.rounded()
    return bool(np.any(frame[y : y + height, x : x + width] < 200))


def test_the_example_leaves_one_field_open_where_it_is_written() -> None:
    query = ExampleQuery()
    assert query.open_field_line == 1
    first, last = query.open_field_span
    assert query.lines[1][first:last] == "..."


def test_the_example_is_the_plans_grasp_query_and_the_line_says_what_it_shows() -> None:
    query = ExampleQuery()
    assert query.lines[0] == "a(GraspDescription)("
    said = NarrationLines().query.written
    assert "left hand" in said and "from the top" in said and "`...`" in said and "left open" in said
    assert "GraspDescription" not in said


def test_the_gloss_is_unlabelled_plain_words_naming_no_meaning_or_grounding() -> None:
    query = ExampleQuery()
    assert query.gloss.startswith("a grasp with the left hand")
    for word in ("meaning", "grounding", "grounded"):
        assert word not in query.gloss


def test_the_open_field_is_marked_only_once_it_is_said() -> None:
    slide = slide_with()
    card = slide.middle_card
    x, y = card.x + CODE_SIZE, card.y + CODE_SIZE / 2 + CODE_SIZE * 1.4 * 1.5
    first, _ = slide.query.open_field_span
    on_field = (int(y), int(x + CodeTypesetting(size=CODE_SIZE).width_of(slide.query.lines[1][:first]) + 4))
    assert tuple(slide.frame_at(1.9)[on_field]) == Ink.BUBBLE.rgb
    assert tuple(slide.frame_at(2.0 + STEP_FADE)[on_field]) == Ink.MARKER.rgb


def test_the_query_then_the_gloss_then_the_backends_then_the_hero_come_up_in_turn() -> None:
    slide = slide_with()
    assert slide.duration == 16.0
    gloss = Area(slide.resolution.width / 2 - 300, slide.middle_card.bottom + 30, 600, 60)
    assert not drawn(slide, gloss, 2.9) and drawn(slide, gloss, 3.0 + STEP_FADE)
    x, y = slide.backend(1, 2)
    choice = Area(x, y - 12, 300, 24)
    assert not drawn(slide, choice, 5.9) and drawn(slide, choice, 6.0 + MOVE + STEP_FADE)
    # the query has shrunk to the top: its middle card's place is clear
    middle = slide.middle_card
    assert drawn(slide, Area(middle.x, middle.y + 32, 40, 16), 5.9)
    assert not drawn(slide, Area(middle.x, middle.y + 32, 40, 16), 6.0 + MOVE + STEP_FADE)
    assert drawn(slide, Area(slide.top_card.x + 20, slide.top_card.y + 12, 120, 24), 6.0 + MOVE + STEP_FADE)
    divider = Area(slide.choice.right + 8, slide.divider_y - 3, 40, 6)
    assert not drawn(slide, divider, 11.9) and drawn(slide, divider, 12.0 + STEP_FADE)
    # the backends have given way to the hero
    box_edge = Area(300, slide.choice.y - 2, 200, 4)
    assert drawn(slide, box_edge, 11.9) and not drawn(slide, box_edge, 12.0 + STEP_FADE)
    hero = Area(slide.resolution.width / 2 - 200, (slide.divider_y + 40 + slide.resolution.stage_height) / 2 - CLAIM_SIZE, 400, 2 * CLAIM_SIZE)
    assert drawn(slide, hero, 12.0 + STEP_FADE)


def test_the_hero_frame_names_the_statement_above_the_divider_and_the_backends_below() -> None:
    script = VideoScript()
    assert script.statement_label == "the statement" and script.backends_label == "backends"
    assert script.principle == "Backends differ in source and mechanism, never in the description."
    assert NarrationLines().principle.written.startswith("Backends differ in their source of information and their mechanism")


def test_the_backends_lie_under_their_kinds_above_the_captions_in_the_figures_colours() -> None:
    slide = slide_with()
    names = {name for kind in slide.kinds for name, _ in kind.backends}
    assert names == {"WorkingMemory", "LongTermMemory", "PerceptionBackend", "RippleDownRulesBackend", "ProbabilisticBackend"}
    for kind_index, kind in enumerate(slide.kinds):
        box = slide.kind(kind_index)
        for index in range(len(kind.backends)):
            x, y = slide.backend(kind_index, index)
            assert y > box.bottom and box.x <= x
            assert y + 20 <= slide.resolution.stage_height
    assert np.all(slide.frame_at(MOMENTS.backends + MOVE + STEP_FADE)[int(slide.resolution.stage_height) :] == 255)
    assert isinstance(slide.kinds[0], BackendKind) and [kind.name for kind in slide.kinds] == ["Selective", "Generative"]
