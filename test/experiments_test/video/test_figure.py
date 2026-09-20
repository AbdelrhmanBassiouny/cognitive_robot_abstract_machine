"""
Tests for :mod:`experiments.video.figure`: the paper's figure compiled stage by stage
for the video, from its own source.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.video.stages import MAGNIFIED_SHARE, TAB_HEIGHT, FigureOnCanvas, Magnified, ReadingStop, Scrolled, Spotlight
from experiments.video.timeline import Resolution, Still

from experiments.video.figure import (
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


# %% a stretch of the figure magnified


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


def test_a_magnified_stretch_without_growing_starts_fully_grown_and_framed_in_its_hue() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    hue = (0x0F, 0x76, 0x6E)
    magnified = Magnified(shown, shown.figure.geometry.slots[Slot.PERCEPTION], hue=hue, held_for=1.0, grow=0.0, shrink=0.0)
    assert magnified.duration == pytest.approx(1.0)
    window = magnified.window
    on_frame = (int(window.y - 2), int(window.centre[0]))
    assert tuple(magnified.frame_at(0.0)[on_frame]) == hue


# %% a stretch of the figure read through


def plan_stretch(shown: FigureOnCanvas) -> tuple:
    """
    The whole plan, from the pick-up's first line to the insertion's last, and its actions.
    """
    actions = shown.figure.geometry.actions
    pick_up, insertion = actions[PlanAction.PICK_UP], actions[PlanAction.INSERTION]
    plan = shown.figure.geometry.plan
    return plan.__class__(plan.x, pick_up.y, plan.width, insertion.y + insertion.height - pick_up.y), pick_up, insertion


def test_a_scrolled_stretch_reads_at_the_rooms_width_and_shows_what_the_room_is_tall() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box, _, _ = plan_stretch(shown)
    scrolled = Scrolled(shown, box, hue=(0, 0, 0), magnification_up_to=100.0)
    assert scrolled.window.width == pytest.approx(640 * MAGNIFIED_SHARE)
    assert scrolled.window.height == pytest.approx(shown.resolution.stage_height * MAGNIFIED_SHARE)
    assert scrolled.picture.shape[0] > scrolled.window.height
    assert scrolled.lowest_top == pytest.approx(box.y + box.height - scrolled.window.height / scrolled.scale)
    capped = Scrolled(shown, box, hue=(0, 0, 0), magnification_up_to=2.0)
    assert capped.scale == pytest.approx(shown.pixels_per_centimetre * 2.0)


def test_a_scrolled_stretch_rests_moves_evenly_between_its_stops_and_rests_again() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box, _, insertion = plan_stretch(shown)
    scrolled = Scrolled(shown, box, hue=(0, 0, 0), held_for=8.0, magnification_up_to=100.0)
    scrolled.stops = (ReadingStop(2.0, box.y), ReadingStop(6.0, scrolled.lowest_top))
    assert scrolled.top_at(0.0) == scrolled.top_at(2.0) == box.y
    assert scrolled.top_at(4.0) == pytest.approx((box.y + scrolled.lowest_top) / 2)
    assert scrolled.top_at(6.0) == scrolled.top_at(9.0) == scrolled.lowest_top
    # a stop past the stretch's bottom is read at the bottom
    scrolled.stops = (ReadingStop(0.0, insertion.y + insertion.height),)
    assert scrolled.top_at(1.0) == scrolled.lowest_top


def test_a_scrolled_stretch_grows_from_its_place_to_its_window_and_back() -> None:
    shown = FigureOnCanvas(FrameworkFigure(stage=0), resolution=Resolution(width=640, height=360))
    box, _, _ = plan_stretch(shown)
    hue = (0x1F, 0x23, 0x28)
    scrolled = Scrolled(shown, box, hue=hue, held_for=1.0, grow=0.5, shrink=0.5)
    assert scrolled.duration == pytest.approx(2.0)
    assert scrolled.grown_at(0.0) == 0.0 and scrolled.grown_at(0.5) == 1.0 and scrolled.grown_at(2.0) == pytest.approx(0.0)
    window = scrolled.window
    on_frame = (int(window.y - 2), int(window.centre[0]))
    assert tuple(scrolled.frame_at(1.0)[on_frame]) == hue
    assert scrolled.frame_at(0.0).shape == scrolled.frame_at(1.0).shape
