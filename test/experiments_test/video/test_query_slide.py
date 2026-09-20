"""
Tests for :mod:`experiments.video.query_slide`: the slide explains a query on one of
the plan's own, a part at a time as the narration names it, and the backends fit under
it.
"""

from __future__ import annotations

import numpy as np

from experiments.video.canvas import Area, CodeTypesetting, Ink
from experiments.video.query_slide import (
    QUERY_PARTS,
    QUERY_TEMPLATE,
    STEP_FADE,
    ExampleQuery,
    QuerySlide,
    SlideMoments,
)
from experiments.video.script import NarrationLines

MOMENTS = SlideMoments(
    template=0.0,
    parts=(0.5, 1.0, 2.0, 3.0),
    lines=(4.0, 7.0, 6.0, 5.0),
    open_field=8.0,
    meaning=9.0,
    grounding=10.0,
    computation=11.0,
    tree=12.0,
    choice=13.0,
)


def drawn(slide: QuerySlide, area, seconds: float) -> bool:
    """
    Whether anything darker than a card is drawn in an area of the slide at a moment.
    """
    frame = slide.frame_at(seconds)
    x, y, width, height = area.rounded()
    return bool(np.any(frame[y : y + height, x : x + width] < 200))


def test_the_example_leaves_one_field_open_where_it_is_written() -> None:
    query = ExampleQuery()
    assert query.open_field_line == 1
    first, after_last = query.open_field_span
    assert query.lines[1][first:after_last] == "..."


def test_the_template_names_every_part_the_definition_line_names() -> None:
    line = NarrationLines().definition.written
    assert "..." in QUERY_TEMPLATE
    for part in QUERY_PARTS:
        assert part.placeholder in QUERY_TEMPLATE
        assert part.named_by in line


def test_the_example_is_the_plans_grasp_query_and_the_lines_say_what_it_says() -> None:
    query, lines = ExampleQuery(), NarrationLines()
    assert "GraspDescription" in query.lines[0]
    assert "..." in lines.example.written and "three dots" in lines.example.said
    assert "intended meaning" in lines.meaning.written and "grounded" in lines.meaning.written


def test_the_lines_of_the_example_come_up_each_at_its_own_moment() -> None:
    slide = QuerySlide(moments=MOMENTS, held_for=14.0)
    lines = [
        Area(slide.line_at(number)[0], slide.line_at(number)[1] - 10, 300, 20)
        for number in range(len(slide.query.lines))
    ]
    # at 5.6 s the first and last lines are typed, the middle two not yet
    assert drawn(slide, lines[0], 5.0 + STEP_FADE) and drawn(slide, lines[3], 5.0 + STEP_FADE)
    assert not drawn(slide, lines[1], 5.0 + STEP_FADE) and not drawn(slide, lines[2], 5.0 + STEP_FADE)
    assert all(drawn(slide, line, 7.0 + STEP_FADE) for line in lines)


def test_the_open_field_is_marked_only_once_it_is_said() -> None:
    slide = QuerySlide(moments=MOMENTS, held_for=14.0)
    before, after = slide.frame_at(7.9), slide.frame_at(8.0 + STEP_FADE)
    x, y = slide.line_at(slide.query.open_field_line)
    first, _ = slide.query.open_field_span
    on_field = (int(y), int(x + CodeTypesetting(size=22).width_of(slide.query.lines[1][:first]) + 4))
    assert tuple(before[on_field]) == Ink.BUBBLE.rgb
    assert tuple(after[on_field]) == Ink.MARKER.rgb


def test_the_query_the_backends_and_the_choice_come_up_in_that_order() -> None:
    slide = QuerySlide(moments=MOMENTS, held_for=14.0)
    assert slide.duration == 14.0
    on_card = (int(slide.card.y + 4), int(slide.card.x + 4))
    on_root = (int(slide.root.y + 1), int(slide.root.centre[0]))
    on_pill = (int(slide.choice.y + 1), int(slide.choice.centre[0]))
    after_card = slide.frame_at(4.0 + STEP_FADE)
    assert tuple(after_card[on_card]) == Ink.BUBBLE.rgb
    assert tuple(after_card[on_root]) == (255, 255, 255) and tuple(after_card[on_pill]) == (255, 255, 255)
    assert not drawn(slide, slide.meaning_block, 8.9) and drawn(slide, slide.meaning_block, 9.0 + STEP_FADE)
    assert not drawn(slide, slide.grounding_block, 9.9) and drawn(slide, slide.grounding_block, 10.0 + STEP_FADE)
    after_tree = slide.frame_at(12.0 + STEP_FADE)
    assert tuple(after_tree[on_root]) == Ink.TEXT.rgb and tuple(after_tree[on_pill]) == (255, 255, 255)
    assert tuple(slide.frame_at(13.0 + STEP_FADE)[on_pill]) == Ink.ASKED.rgb


def test_the_template_and_its_parts_come_up_before_the_example() -> None:
    slide = QuerySlide(moments=MOMENTS, held_for=14.0)
    left, right = slide.part_span(QUERY_PARTS[1])
    label = Area(left, slide.template_at[1] + 20, right - left, 24)
    assert not drawn(slide, label, 0.9) and drawn(slide, label, 1.0 + STEP_FADE)
    left, right = slide.part_span(QUERY_PARTS[0])
    assert drawn(slide, Area(left, slide.template_at[1] + 20, right - left, 24), 0.5 + STEP_FADE)
    assert not drawn(slide, slide.card, 3.9)


def test_every_leaf_of_the_tree_lies_under_its_kind_and_above_the_subtitles() -> None:
    slide = QuerySlide()
    for kind_index, kind in enumerate(slide.tree.children):
        box = slide.kind(kind_index)
        for index in range(len(kind.children)):
            leaf = slide.leaf(kind_index, index)
            assert leaf.y > box.bottom and box.x <= leaf.x
            assert leaf.bottom <= slide.resolution.stage_height
    assert np.all(slide.frame_at(slide.moments.choice + STEP_FADE)[int(slide.resolution.stage_height) :] == 255)
