"""
Tests for :mod:`experiments.video.figure`: the paper's figure compiled stage by stage
for the video, from its own source.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.canvas import MARGIN, VIDEO_RESOLUTION, CodeTypesetting, Ink
from experiments.video.plan import STATED_LINES, resolved_plan, stated_plan
from experiments.video.stages import (
    CODE_SIZE,
    FADE,
    HEADER_CLEAR,
    MOVE,
    PANEL_VISUAL,
    PLAN_CODE_SIZE,
    QUERY_ZONE_SHARE,
    BackendAtWork,
    PlanOverview,
)
from experiments.video.statements import SlotStatement, statements_of
from experiments.video.timeline import Still

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


# %% the plan, as stated and resolved


READINGS = RunReadings(
    resolved_lines={
        Slot.PERCEPTION: ["cube_1  # CYAN, CUBE", "  at (1, 2, 3) m,"],
        Slot.PROBABILISTIC: ["grasp_1 = GraspDescription(", "  LEFT, TOP,", "  LEFT_HAND)"],
        Slot.RULES: ["ShapeSortingHole(", "  shape_category=CUBE)"],
    },
    filled_values={Slot.PROBABILISTIC: "LEFT", Slot.RULES: "CUBE"},
    filled_lines={Slot.PERCEPTION: ["cube_1  # CYAN, CUBE", "  at (1, 2, 3) m,"]},
    support_verdict="SupportedBy(cube_1, lid) → True",
)


def test_the_stated_plan_is_the_figures_and_emphasises_its_three_open_parts() -> None:
    plan = stated_plan()
    assert plan.lines == STATED_LINES and len(plan.lines) == 25
    assert plan.columns() == ((0, 15), (15, 25))
    description, grasp, hole = plan.emphasised
    assert (description.first_row, description.last_row, description.span) == (4, 8, None)
    assert plan.lines[grasp.first_row][slice(*grasp.span)] == "..." and plan.lines[hole.first_row][slice(*hole.span)] == "..."
    assert description.covers(5, 3) and not description.covers(9, 3)
    assert grasp.covers(11, grasp.span[0]) and not grasp.covers(11, 0)


def test_the_resolved_plan_carries_what_the_run_read() -> None:
    plan = resolved_plan(READINGS)
    text = "\n".join(plan.lines)
    assert "cube_1  # CYAN, CUBE" in text and "at (1, 2, 3) m," in text
    assert "SupportedBy(cube_1, lid) ✓" in text
    assert "LEFT, TOP," in text and "shape_category=CUBE)" in text
    assert "object_designator=cube_1," in text and "grasp_description=grasp_1," in text
    assert "..." not in text and not plan.emphasised


def test_the_plan_overview_writes_two_columns_under_the_pill_above_the_captions_and_dims_all_but_the_open_parts() -> None:
    overview = PlanOverview(stated_plan(), held_for=4.0, emphasis_from=1.0)
    assert overview.duration == 4.0
    first, last = overview.line_at(0), overview.line_at(24)
    assert first[1] - 15 >= HEADER_CLEAR and last[1] + 15 <= VIDEO_RESOLUTION.stage_height
    assert overview.line_at(15)[0] > first[0] + overview.column_width
    assert overview.line_at(15)[0] + overview.column_width <= VIDEO_RESOLUTION.width - MARGIN
    assert overview.line_at(14)[0] == first[0]
    before, after = overview.frame_at(0.5), overview.frame_at(1.0 + FADE)
    # the ink of a line left alone has faded; the open field's ink has not
    x, y = overview.line_at(0)
    column = slice(int(x), int(x + CodeTypesetting(size=PLAN_CODE_SIZE).width_of("sequential([")))
    rows = slice(int(y - 10), int(y + 10))
    assert after[rows, column].min() > before[rows, column].min()
    x, y = overview.line_at(11)
    grasp = stated_plan().emphasised[1]
    code = CodeTypesetting(size=PLAN_CODE_SIZE)
    dots = slice(int(x + code.width_of(STATED_LINES[11][: grasp.span[0]])), int(x + code.width_of(STATED_LINES[11][: grasp.span[1]])))
    rows = slice(int(y - 10), int(y + 10))
    assert after[rows, dots].min() == before[rows, dots].min()


def test_the_resolved_overview_carries_the_footnote_under_the_plan() -> None:
    with_note = PlanOverview(resolved_plan(READINGS), held_for=2.0, footnote="values from the recorded run")
    without = PlanOverview(resolved_plan(READINGS), held_for=2.0)
    stage = int(VIDEO_RESOLUTION.stage_height)
    assert with_note.frame_at(1.0)[stage - 40 : stage].min() < 200
    assert without.frame_at(1.0)[stage - 40 : stage].min() == 255
    assert with_note.line_at(0)[1] < without.line_at(0)[1]


# %% the sub-queries


def test_the_statements_are_the_plans_and_read_answered_with_what_the_run_read() -> None:
    readings = RunReadings(
        filled_values={Slot.PROBABILISTIC: "LEFT", Slot.RULES: "CUBE"},
        filled_lines={Slot.PERCEPTION: ["cube_1  # CYAN, CUBE", "  at (1, 2, 3) m,"]},
        support_verdict="SupportedBy(cube_1, lid) → True",
    )
    statements = statements_of(readings)
    assert set(statements) == set(Slot)
    perception = statements[Slot.PERCEPTION]
    assert perception.lines[0] == "a(DetectedMontessoriShape)(" and perception.open_span is None and perception.open_row == 0
    assert perception.answered == ("cube_1  # CYAN, CUBE", "  at (1, 2, 3) m,") and perception.answer == "cube_1"
    simulation = statements[Slot.SIMULATION]
    assert simulation.lines == ("SupportedBy(cube_1, lid)",) and simulation.answer == "True" and simulation.answered[0].endswith("✓")
    grasp = statements[Slot.PROBABILISTIC]
    assert grasp.open_row == 1 and grasp.lines[1][slice(*grasp.open_span)] == "..."
    assert grasp.answered[1] == "  approach_direction=LEFT," and grasp.answer == "LEFT"
    hole = statements[Slot.RULES]
    assert hole.answered[1] == "  shape_category=CUBE)" and hole.answer == "CUBE"
    assert max(len(statement.lines) for statement in statements.values()) == 5


# %% a backend at work


def at_work(answered_at: float = 1.0) -> BackendAtWork:
    statement = SlotStatement(
        Slot.RULES,
        ("a(ShapeSortingHole)(", "  shape_category=...)", ".from_(board.apertures)"),
        ("a(ShapeSortingHole)(", "  shape_category=CUBE)", ".from_(board.apertures)"),
        "CUBE",
        open_row=1,
    )
    work = Still(np.full((PANEL_VISUAL.height, PANEL_VISUAL.width, 3), 200, dtype=np.uint8), held_for=8.0)
    return BackendAtWork(statement, "RippleDownRulesBackend", Ink.RULES.rgb, work, answered_at=answered_at, held_for=6.0)


def test_the_two_zones_are_fixed_the_query_left_and_the_panel_right() -> None:
    scene = at_work()
    box, panel = scene.query_box, scene.panel
    assert box.x == MARGIN and box.y == HEADER_CLEAR and box.right < VIDEO_RESOLUTION.width * QUERY_ZONE_SHARE
    assert panel.x > VIDEO_RESOLUTION.width * QUERY_ZONE_SHARE and panel.right == VIDEO_RESOLUTION.width - MARGIN
    assert scene.visual.width == PANEL_VISUAL.width and scene.visual.height == PANEL_VISUAL.height
    assert panel.bottom <= VIDEO_RESOLUTION.stage_height
    assert not scene.dissolves_in
    other = BackendAtWork(scene.statement, "PerceptionBackend", Ink.PERCEPTION.rgb, scene.work, answered_at=1.0)
    assert other.query_box == box and other.panel == panel


def test_the_title_bar_carries_the_backends_colour_and_the_visual_plays_under_it() -> None:
    scene = at_work()
    frame = scene.frame_at(0.5)
    bar = scene.title_bar
    assert tuple(frame[int(bar.y) + 2, int(bar.right) - 2]) == Ink.RULES.rgb
    visual = scene.visual
    assert tuple(frame[int(visual.centre[1]), int(visual.centre[0])]) == (200, 200, 200)


def test_the_answer_chip_comes_up_moves_into_the_open_slot_and_the_query_then_reads_answered() -> None:
    scene = at_work(answered_at=1.0)
    assert scene.moves_at == pytest.approx(1.0 + scene.chip_for)
    assert scene.lands_at == pytest.approx(scene.moves_at + MOVE)
    on_panel = scene.chip_on_panel
    in_slot = scene.chip_in_slot
    assert on_panel.right == scene.panel.right and on_panel.bottom == scene.panel.bottom
    assert scene.query_box.x < in_slot.x < scene.query_box.right
    assert in_slot.centre[1] == pytest.approx(scene.line_at(1)[1])
    centre = (int(on_panel.centre[1]), int(on_panel.x + 4))
    assert tuple(scene.frame_at(0.5)[centre]) != Ink.ANSWER.rgb
    assert tuple(scene.frame_at(1.0 + FADE)[centre]) == Ink.ANSWER.rgb
    landed = scene.frame_at(scene.lands_at + 0.05)
    assert tuple(landed[int(in_slot.centre[1]), int(in_slot.x + 8)]) == Ink.ANSWER.rgb
    read = scene.frame_at(scene.answered_read_at + FADE + 0.05)
    assert tuple(read[int(in_slot.centre[1]), int(in_slot.x + 8)]) != Ink.ANSWER.rgb
    assert not np.array_equal(read, scene.frame_at(0.5))


def test_the_open_field_is_marked_until_the_chip_lands() -> None:
    scene = at_work(answered_at=1.0)
    x, y = scene.line_at(1)
    on_field = (int(y), int(x + CodeTypesetting(size=CODE_SIZE).width_of("  shape_category=") + 4))
    assert tuple(scene.frame_at(0.5)[on_field]) == Ink.MARKER.rgb
    assert tuple(scene.frame_at(scene.answered_read_at + FADE + 0.05)[on_field]) != Ink.MARKER.rgb
