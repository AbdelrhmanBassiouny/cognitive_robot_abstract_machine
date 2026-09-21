"""
Tests for :mod:`experiments.video.figure`: the paper's figure compiled stage by stage
for the video, from its own source.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.canvas import Area, Ink
from experiments.video.stages import (
    ARROW_AIR,
    ARROW_ROOM,
    COLUMN_GAP,
    MAGNIFIED_SHARE,
    MARK_FADE,
    POINTER_AIR,
    POINTER_LENGTH,
    POINTER_MOVE,
    QUERY_COLUMN_WIDTH,
    TAB_HEIGHT,
    Answering,
    FigureOnCanvas,
    Magnified,
    Mark,
    Pointer,
    Spotlight,
    highlighted,
    marked,
)
from experiments.video.timeline import Resolution, Still

from experiments.video.figure import (
    FigureBox,
    FrameworkFigure,
    GraspChartBar,
    PlanAction,
    RunReadings,
    Slot,
)


@pytest.mark.parametrize(
    "slot, stage",
    [
        (Slot.PERCEPTION, 1),
        (Slot.SIMULATION, 2),
        (Slot.PROBABILISTIC, 3),
        (Slot.RULES, 4),
    ],
)
def test_each_slot_knows_the_stage_its_answer_completes(slot: Slot, stage: int) -> None:
    assert slot.stage == stage


def test_the_input_carries_the_stage_the_focus_and_the_readings() -> None:
    figure = FrameworkFigure(
        stage=2,
        focus=Slot.PROBABILISTIC,
        readings=RunReadings(
            resolved_lines={Slot.PERCEPTION: ["cube_1", "  at (1, 2, 3) m,"]},
            grasps=[GraspChartBar("LEFT", "TOP", 0.3, chosen=True)],
            support_reading="overlap 2 mm ≤ 0.1 m",
        ),
    )
    assert figure.as_input() == {
        "stage": 2,
        "bubble_only": True,
        "focus": "probabilistic",
        "resolved_lines": {"perception": ["cube_1", "  at (1, 2, 3) m,"]},
        "grasps": [{"approach": "LEFT", "alignment": "TOP", "p": 0.3, "chosen": True}],
        "support_reading": "overlap 2 mm ≤ 0.1 m",
    }


def test_the_input_names_the_panels_only_when_asked_to() -> None:
    assert "panel_titles" not in FrameworkFigure().as_input()
    named = FrameworkFigure(panel_titles={Slot.RULES: "RippleDownRulesBackend"})
    assert named.as_input()["panel_titles"] == {"rules": "RippleDownRulesBackend"}


def test_the_figure_compiles_with_the_panels_renamed() -> None:
    titles = {slot: f"{slot.value.title()}Backend" for slot in Slot}
    picture = FrameworkFigure(stage=1, panel_titles=titles).drawn(width=400)
    assert picture.shape[1] == 400


def test_the_figure_compiles_to_a_picture_of_the_asked_width() -> None:
    picture = FrameworkFigure(stage=0, focus=Slot.PERCEPTION).drawn(width=400)
    assert picture.shape[1] == 400
    assert picture.dtype == np.uint8
    assert picture.shape[2] == 3


def test_more_stages_draw_more_ink() -> None:
    empty = FrameworkFigure(stage=0).drawn(width=400)
    full = FrameworkFigure(stage=4).drawn(width=400)
    assert empty.shape == full.shape
    assert (full < 128).sum() > (empty < 128).sum()


def test_the_geometry_places_the_panels_in_one_column_between_the_plans() -> None:
    geometry = FrameworkFigure(stage=0).geometry
    panels = [geometry.panels[slot] for slot in Slot]
    assert len({panel.x for panel in panels}) == 1
    assert geometry.plan.x + geometry.plan.width < panels[0].x
    assert panels[0].x + panels[0].width < geometry.resolved.x
    assert [panel.y for panel in panels] == sorted(panel.y for panel in panels)
    assert geometry.height < geometry.width


def test_the_geometry_boxes_every_open_slot_inside_the_plan_in_the_choices_order() -> None:
    geometry = FrameworkFigure(stage=0).geometry
    plan = geometry.plan
    for slot in Slot:
        box = geometry.slots[slot]
        assert plan.x <= box.x and box.x + box.width <= plan.x + plan.width
        assert plan.y <= box.y and box.y + box.height <= plan.y + plan.height
    tops = [geometry.slots[slot].y for slot in Slot]
    assert tops == sorted(tops)
    nested, outer = geometry.slots[Slot.SIMULATION], geometry.slots[Slot.PERCEPTION]
    assert outer.y < nested.y and nested.y + nested.height <= outer.y + outer.height


def test_the_geometry_cuts_the_plan_into_its_two_actions_one_over_the_other() -> None:
    geometry = FrameworkFigure(stage=0).geometry
    pick_up, insertion = geometry.actions[PlanAction.PICK_UP], geometry.actions[PlanAction.INSERTION]
    assert pick_up.y + pick_up.height == pytest.approx(insertion.y)
    assert pick_up.width == insertion.width == geometry.plan.width
    assert geometry.slots[Slot.PROBABILISTIC].y + geometry.slots[Slot.PROBABILISTIC].height < insertion.y
    assert insertion.y < geometry.slots[Slot.RULES].y


def test_the_geometry_boxes_every_answer_inside_the_resolved_plan_in_the_slots_order() -> None:
    geometry = FrameworkFigure(stage=len(Slot)).geometry
    resolved = geometry.resolved
    for slot in Slot:
        answer = geometry.answers[slot]
        assert resolved.x <= answer.x and answer.x + answer.width <= resolved.x + resolved.width
        assert resolved.y <= answer.y and answer.y + answer.height <= resolved.y + resolved.height
    tops = [geometry.answers[slot].y for slot in Slot]
    assert tops == sorted(tops)


def test_the_geometry_boxes_each_ellipsis_of_the_plan_inside_the_slot_that_leaves_the_field_open() -> None:
    geometry = FrameworkFigure(stage=0).geometry
    assert set(geometry.open_fields) == {Slot.PROBABILISTIC, Slot.RULES}
    for slot, field in geometry.open_fields.items():
        sub_query = geometry.slots[slot]
        assert sub_query.x < field.x and field.x + field.width < sub_query.x + sub_query.width
        assert sub_query.y < field.y and field.y + field.height < sub_query.y + sub_query.height
        # three characters of code, wider than tall but not by much
        assert field.height < field.width < field.height * 2


def test_the_plan_is_filled_in_where_its_backend_has_answered_and_the_readings_say_with_what() -> None:
    readings = RunReadings(
        filled_values={Slot.PROBABILISTIC: "LEFT", Slot.RULES: "CUBE"},
        filled_lines={Slot.PERCEPTION: ["cube_1  # CYAN, CUBE", "  at (1, 2, 3) m,"]},
    )
    assert readings.as_input() == {
        "filled_values": {"probabilistic": "LEFT", "rules": "CUBE"},
        "filled_lines": {"perception": ["cube_1  # CYAN, CUBE", "  at (1, 2, 3) m,"]},
    }
    open_plan = FrameworkFigure(stage=0, readings=readings).geometry
    grasp_answered = FrameworkFigure(stage=Slot.PROBABILISTIC.stage, readings=readings).geometry
    # the grasp's `...` is gone, its box as wide and tall as before; the hole's is still open
    assert Slot.PROBABILISTIC in open_plan.open_fields and Slot.PROBABILISTIC not in grasp_answered.open_fields
    assert Slot.RULES in grasp_answered.open_fields
    filled, open_ = grasp_answered.slots[Slot.PROBABILISTIC], open_plan.slots[Slot.PROBABILISTIC]
    assert (filled.width, filled.height) == (open_.width, open_.height)
    # the cube's description, two lines in place of four, leaves a shorter box
    assert grasp_answered.slots[Slot.PERCEPTION].height < open_plan.slots[Slot.PERCEPTION].height
    # what was filled in is boxed: the value where the `...` was, the lines of the cube
    assert not open_plan.filled_fields
    assert set(grasp_answered.filled_fields) == {Slot.PERCEPTION, Slot.PROBABILISTIC}
    value, was = grasp_answered.filled_fields[Slot.PROBABILISTIC], open_plan.open_fields[Slot.PROBABILISTIC]
    # where the dots stood (the box above has shrunk, so the rows lie higher), four letters wide
    assert (value.x, value.height) == (was.x, was.height) and value.width > was.width
    assert value.y - grasp_answered.slots[Slot.PROBABILISTIC].y == pytest.approx(was.y - open_plan.slots[Slot.PROBABILISTIC].y)
    lines, box = grasp_answered.filled_fields[Slot.PERCEPTION], grasp_answered.slots[Slot.PERCEPTION]
    assert box.x < lines.x and lines.x + lines.width < box.x + box.width
    assert box.y < lines.y and lines.y + lines.height < box.y + box.height


# %% the close-up over the figure


def test_the_close_up_carries_the_backends_name_on_a_tab_once_grown() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0, focus=Slot.RULES), resolution=Resolution(width=640, height=360))
    work = Still(np.full((90, 160, 3), 200, dtype=np.uint8), held_for=2.0)
    hue = (0x6D, 0x28, 0xD9)
    named = Spotlight(shown, shown, Slot.RULES, work, hue, title="RippleDownRulesBackend", grow=0.5, shrink=0.5)
    bare = Spotlight(shown, shown, Slot.RULES, work, hue, grow=0.5, shrink=0.5)
    where = named.close_up
    on_tab = (int(where.y - 4 - TAB_HEIGHT / 2), int(where.x + 4))
    assert tuple(named.frame_at(1.0)[on_tab]) == hue
    assert tuple(bare.frame_at(1.0)[on_tab]) != hue
    assert tuple(named.frame_at(0.0)[on_tab]) != hue


# %% a backend answering its sub-query beside it


def answering(slot: Slot, marks=()) -> Answering:
    before = FigureOnCanvas(FrameworkFigure(stage=slot.stage - 1, focus=slot))
    after = FigureOnCanvas(FrameworkFigure(stage=slot.stage))
    work = Still(np.full((90, 160, 3), 200, dtype=np.uint8), held_for=2.0)
    return Answering(
        before, after, slot, work, hue=(0x6D, 0x28, 0xD9), title="RippleDownRulesBackend", marks=marks,
        query_for=1.0, grow=0.5, close_up_grow=0.5, fill_for=0.5, filled_for=0.5, shrink=0.5,
    )


def test_the_answering_runs_query_then_close_up_then_work_then_fill_then_shrink() -> None:
    scene = answering(Slot.RULES)
    assert scene.close_up_from == pytest.approx(1.5)
    assert scene.work_from == pytest.approx(2.0)
    assert scene.fill_from == pytest.approx(4.0)
    assert scene.shrink_from == pytest.approx(5.0)
    assert scene.duration == pytest.approx(5.5)
    assert scene.query_grown_at(0.0) == 0.0 and scene.query_grown_at(0.5) == 1.0 and scene.query_grown_at(4.9) == 1.0
    assert scene.query_grown_at(5.5) == pytest.approx(0.0)
    assert scene.close_up_grown_at(1.5) == 0.0 and scene.close_up_grown_at(2.0) == 1.0
    assert scene.close_up_grown_at(4.9) == 1.0 and scene.close_up_grown_at(5.5) == pytest.approx(0.0)
    assert scene.filled_at(3.9) == 0.0 and scene.filled_at(4.5) == 1.0


def test_the_sub_query_is_held_in_its_column_and_the_close_up_right_of_it() -> None:
    scene = answering(Slot.RULES)
    query, close_up = scene.query_window, scene.close_up
    assert COLUMN_GAP <= query.x and query.right <= COLUMN_GAP + QUERY_COLUMN_WIDTH
    assert close_up.x >= COLUMN_GAP + QUERY_COLUMN_WIDTH + ARROW_ROOM
    assert close_up.bottom <= scene.before.resolution.stage_height
    assert close_up.right <= scene.before.resolution.width - COLUMN_GAP
    assert query.width == pytest.approx(scene.query_box.width * scene.scale)
    assert scene.filled_window.x == query.x and scene.filled_window.y == query.y
    assert scene.filled_window.width == pytest.approx(scene.filled_box.width * scene.scale)


def test_what_was_filled_in_is_marked_once_the_answer_is_written() -> None:
    readings = RunReadings(filled_values={Slot.RULES: "CUBE"})
    before = FigureOnCanvas(FrameworkFigure(stage=Slot.RULES.stage - 1, focus=Slot.RULES, readings=readings))
    after = FigureOnCanvas(FrameworkFigure(stage=Slot.RULES.stage, readings=readings))
    work = Still(np.full((90, 160, 3), 200, dtype=np.uint8), held_for=2.0)
    scene = Answering(before, after, Slot.RULES, work, hue=(0, 0, 0), query_for=1.0, grow=0.5, close_up_grow=0.5, fill_for=0.5, filled_for=0.5, shrink=0.5)
    assert len(scene.filled_marks) == 1 and scene.filled_marks[0].from_second == scene.fill_from
    field = after.figure.geometry.filled_fields[Slot.RULES]
    box = scene.filled_box
    on_value = (int((field.y + field.height / 2 - box.y) * scene.scale), int((field.x + field.width / 2 - box.x) * scene.scale))
    plain = scene.filled_picture[on_value]
    marked_at = scene.filled_picture_at(scene.fill_from + MARK_FADE)[on_value]
    assert not np.array_equal(plain, marked_at)
    assert np.array_equal(scene.filled_picture_at(scene.fill_from - 0.1)[on_value], plain)


def test_the_arrow_aims_at_the_open_field_when_there_is_one_else_at_the_sub_query() -> None:
    geometry = FrameworkFigure(stage=0).geometry
    with_field = answering(Slot.RULES, marks=(Mark(geometry.open_fields[Slot.RULES], (255, 0, 0)),))
    without = answering(Slot.RULES)
    query = with_field.query_window
    # outside the writing, level with the field
    assert with_field.aimed_at[0] >= max(query.right, with_field.filled_window.right) + ARROW_AIR
    assert query.y < with_field.aimed_at[1] < query.centre[1]
    assert without.aimed_at[0] == with_field.aimed_at[0] and without.aimed_at[1] == query.centre[1]


def test_the_answer_is_written_in_while_the_work_is_still_shown_and_the_column_lands_on_the_resolved_plan() -> None:
    scene = answering(Slot.RULES)
    on_query = (int(scene.query_window.y + 2), int(scene.query_window.x + 2))
    on_close_up = (int(scene.close_up.y + 10), int(scene.close_up.x + 10))
    held = scene.frame_at(1.0)
    assert np.array_equal(held[on_query], scene.query_picture[2, 2])
    assert tuple(held[on_close_up]) != (200, 200, 200)
    filled_in = scene.frame_at(4.9)
    # blended in fully, give or take the resampling onto the window
    assert np.abs(filled_in[on_query].astype(int) - scene.filled_picture[2, 2].astype(int)).max() <= 8
    assert tuple(filled_in[on_close_up]) == (200, 200, 200)
    # landed: the filled sub-query over its own place in the plan
    landed = scene.frame_at(scene.duration - 1e-3)
    x, y, width, height = scene.after.area_of(scene.filled_box).rounded()
    over_the_box = (slice(y, y + height), slice(x, x + width))
    # the same writing, resampled: alike on average, whatever single glyph edges do
    assert np.abs(landed[over_the_box].astype(int) - scene.after.frame[over_the_box].astype(int)).mean() < 12


# %% a stretch of the figure magnified


def plan_stretch(shown: FigureOnCanvas) -> tuple:
    """
    The whole plan, from the pick-up's first line to the insertion's last, and its actions.
    """
    actions = shown.figure.geometry.actions
    pick_up, insertion = actions[PlanAction.PICK_UP], actions[PlanAction.INSERTION]
    plan = shown.figure.geometry.plan
    return plan.__class__(plan.x, pick_up.y, plan.width, insertion.y + insertion.height - pick_up.y), pick_up, insertion


def test_a_magnified_stretch_grows_from_its_place_to_the_screens_share_and_back() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box = shown.figure.geometry.slots[Slot.RULES]
    magnified = Magnified(shown, box, hue=(0x6D, 0x28, 0xD9), held_for=1.0, grow=0.5, shrink=0.5)
    assert magnified.duration == pytest.approx(2.0)
    assert magnified.grown_at(0.0) == 0.0 and magnified.grown_at(0.5) == 1.0
    assert magnified.grown_at(1.5) == 1.0 and magnified.grown_at(2.0) == pytest.approx(0.0)
    window = magnified.window
    assert window.aspect == pytest.approx(box.width / box.height, rel=1e-3)
    assert magnified.scale == pytest.approx(shown.pixels_per_centimetre * magnified.magnification_up_to)
    uncapped = Magnified(shown, box, hue=(0, 0, 0), magnification_up_to=100.0).window
    assert uncapped.width == pytest.approx(640 * MAGNIFIED_SHARE) or uncapped.height == pytest.approx(shown.resolution.stage_height * MAGNIFIED_SHARE)
    assert uncapped.centre == pytest.approx(window.centre)


def test_a_stated_scale_sets_the_magnified_window_and_the_picture_is_cut_at_it() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box = shown.figure.geometry.actions[PlanAction.INSERTION]
    magnified = Magnified(shown, box, hue=(0, 0, 0), pixels_per_centimetre=50.0)
    assert magnified.window.width == pytest.approx(box.width * 50.0)
    assert magnified.window.centre[0] == pytest.approx(320.0)
    height, width = magnified.picture.shape[:2]
    assert width == pytest.approx(box.width * 50.0, abs=1.5)
    assert height == pytest.approx(box.height * 50.0, abs=1.5)


def test_a_magnified_stretch_may_take_more_of_the_stage_than_the_usual_share() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box, _, _ = plan_stretch(shown)
    usual = Magnified(shown, box, hue=(0, 0, 0), magnification_up_to=100.0).window
    wider = Magnified(shown, box, hue=(0, 0, 0), magnification_up_to=100.0, share=0.96).window
    assert usual.height == pytest.approx(shown.resolution.stage_height * MAGNIFIED_SHARE)
    assert wider.height == pytest.approx(shown.resolution.stage_height * 0.96)
    assert wider.centre == pytest.approx(usual.centre)


def hue_pixels(frame: np.ndarray, hue: tuple, area: Area) -> int:
    """
    How many pixels of an area of the frame are the hue, near enough.
    """
    left, top, width, height = area.rounded()
    patch = frame[max(top, 0) : top + height, max(left, 0) : left + width].astype(int)
    return int((np.abs(patch - np.array(hue)).sum(axis=2) < 40).sum())


def arrow_row(window: Area, part: Area) -> Area:
    """
    The strip beside the window an arrow pointing at a part lies in.
    """
    return Area(window.right + POINTER_AIR, part.centre[1] - 4, POINTER_LENGTH + POINTER_AIR + 8, 8)


def test_a_pointer_frames_its_part_and_an_arrow_beside_the_window_points_at_it_until_the_next_takes_over() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box, pick_up, insertion = plan_stretch(shown)
    hue = (0xD9, 0x29, 0x38)
    magnified = Magnified(shown, box, hue=(0, 0, 0), held_for=4.0, grow=0.0, shrink=0.0, share=0.96)
    magnified.pointers = (Pointer(pick_up, hue, from_second=0.5), Pointer(insertion, hue, from_second=2.0))
    window = magnified.window
    beside = Area(window.right, window.y, POINTER_LENGTH + 2 * POINTER_AIR + 8, window.height)
    assert hue_pixels(magnified.frame_at(0.2), hue, beside) == 0
    pointing = magnified.frame_at(1.5)
    pick_up_at, insertion_at = magnified.placed(window, pick_up), magnified.placed(window, insertion)
    assert hue_pixels(pointing, hue, arrow_row(window, pick_up_at)) > POINTER_LENGTH // 2
    assert hue_pixels(pointing, hue, arrow_row(window, insertion_at)) == 0
    # the frame runs along the part's top, just outside the window's own frame
    above = Area(pick_up_at.x, pick_up_at.y - POINTER_AIR - 3, pick_up_at.width, 5)
    assert hue_pixels(pointing, hue, above) > pick_up_at.width // 2
    assert hue_pixels(pointing, hue, Area(insertion_at.x, insertion_at.bottom + POINTER_AIR - 2, insertion_at.width, 5)) == 0
    # halfway through the move the arrow lies between the two parts; afterwards at the second alone
    moving = magnified.frame_at(2.0 + POINTER_MOVE / 2)
    between = Area(window.right + POINTER_AIR, pick_up_at.centre[1] + 4, POINTER_LENGTH + POINTER_AIR + 8, insertion_at.centre[1] - pick_up_at.centre[1] - 8)
    assert hue_pixels(moving, hue, between) > POINTER_LENGTH // 2
    moved = magnified.frame_at(3.5)
    assert hue_pixels(moved, hue, arrow_row(window, insertion_at)) > POINTER_LENGTH // 2
    assert hue_pixels(moved, hue, arrow_row(window, pick_up_at)) == 0
    assert hue_pixels(moved, hue, above) == 0


def test_a_pointer_left_unframed_only_points_leaving_the_part_to_its_mark() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box, _, _ = plan_stretch(shown)
    field = shown.figure.geometry.open_fields[Slot.RULES]
    hue = (0xD9, 0x29, 0x38)
    magnified = Magnified(shown, box, hue=(0, 0, 0), held_for=2.0, grow=0.0, shrink=0.0, share=0.96)
    magnified.pointers = (Pointer(field, hue, from_second=0.0, framed=False),)
    window = magnified.window
    field_at = magnified.placed(window, field)
    frame = magnified.frame_at(1.0)
    assert hue_pixels(frame, hue, arrow_row(window, field_at)) > POINTER_LENGTH // 2
    # nothing of the hue is drawn inside the window around the field: the arrow stops beside the window
    assert hue_pixels(frame, hue, field_at.inset(-POINTER_AIR - 4)) == 0


def test_a_magnified_stretch_without_growing_starts_fully_grown_and_framed_in_its_hue() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    hue = (0x0F, 0x76, 0x6E)
    magnified = Magnified(shown, shown.figure.geometry.slots[Slot.PERCEPTION], hue=hue, held_for=1.0, grow=0.0, shrink=0.0)
    assert magnified.duration == pytest.approx(1.0)
    window = magnified.window
    on_frame = (int(window.y - 2), int(window.centre[0]))
    assert tuple(magnified.frame_at(0.0)[on_frame]) == hue


# %% a part of a stretch pointed to


def test_a_highlighter_turns_the_paper_yellow_and_leaves_the_ink() -> None:
    picture = np.full((20, 30, 3), 255, dtype=np.uint8)
    picture[10, 10] = (0, 0, 0)
    drawn = highlighted(picture, Area(5, 5, 10, 10))
    assert tuple(drawn[7, 7]) == Ink.MARKER.rgb
    assert tuple(drawn[10, 10]) == (0, 0, 0)
    assert tuple(drawn[2, 2]) == (255, 255, 255)
    assert tuple(picture[7, 7]) == (255, 255, 255)


def test_a_mark_appears_at_its_moment_ringed_in_its_hue_where_the_picture_places_the_part() -> None:
    picture = np.full((100, 100, 3), 255, dtype=np.uint8)
    hue = (0xD9, 0x29, 0x38)
    mark = Mark(FigureBox(2.0, 3.0, 0.5, 0.25), hue, from_second=1.0)
    # the picture starts at figure (1, 2) cm, at 40 pixels per centimetre: the part lies at (40, 40)-(60, 50)
    before = marked(picture, (1.0, 2.0), 40.0, (mark,), 0.5)
    assert tuple(before[45, 50]) == (255, 255, 255)
    after = marked(picture, (1.0, 2.0), 40.0, (mark,), 1.0 + MARK_FADE)
    assert tuple(after[45, 50]) == Ink.MARKER.rgb
    assert tuple(after[45, 60 + 1]) == hue
    assert tuple(after[45, 90]) == (255, 255, 255)
    half = marked(picture, (1.0, 2.0), 40.0, (mark,), 1.0 + MARK_FADE / 2)
    assert Ink.MARKER.rgb[2] < half[45, 50][2] < 255


def test_a_mark_outside_the_picture_leaves_it_as_it_is() -> None:
    picture = np.full((20, 20, 3), 255, dtype=np.uint8)
    mark = Mark(FigureBox(9.0, 9.0, 0.5, 0.25), (0, 0, 0))
    assert np.array_equal(marked(picture, (0.0, 0.0), 10.0, (mark,), 5.0), picture)


def highlighter_over(before: np.ndarray, after: np.ndarray) -> bool:
    """
    Whether a patch has had the highlighter drawn over it: its blue has dropped out
    and its red stayed, the ink in it aside.
    """
    return float(after[..., 2].mean()) < float(before[..., 2].mean()) - 40 and float(after[..., 0].mean()) >= float(before[..., 0].mean()) - 15


def patch_of(frame: np.ndarray, window: Area, stretch: FigureBox, scale: float, part: FigureBox) -> np.ndarray:
    """
    The pixels of a part of a stretch read through a window at a scale.
    """
    top, left = window.y + (part.y - stretch.y) * scale, window.x + (part.x - stretch.x) * scale
    return frame[int(top) : int(top + part.height * scale), int(left) : int(left + part.width * scale)]


def test_a_magnified_sub_query_rings_its_open_field_once_the_mark_has_appeared() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    geometry = shown.figure.geometry
    field = geometry.open_fields[Slot.RULES]
    magnified = Magnified(shown, geometry.slots[Slot.RULES], hue=(0, 0, 0), held_for=2.0, grow=0.0, shrink=0.0)
    magnified.marks = (Mark(field, (0xD9, 0x29, 0x38), from_second=1.0),)
    window, scale, box = magnified.window, magnified.scale, magnified.box
    before = patch_of(magnified.frame_at(0.5), window, box, scale, field)
    after = patch_of(magnified.frame_at(1.9), window, box, scale, field)
    assert highlighter_over(before, after)
