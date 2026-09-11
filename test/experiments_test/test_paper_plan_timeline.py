"""
The chart of what the robot was running, drawn under the chart of what it saw.

The second of a card's two charts. An event says something happened; this says what the
robot was doing at the time, which is what makes the difference between an event it
brought about and one that happened to it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from giskardpy.motion_statechart.data_types import LifeCycleValues
from segmind.datastructures.events import PickUpEvent, TranslationEvent

from experiments.episodes.episode import RecordedTrial
from experiments.paper.chart import TimelineSpan
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.plan_timeline import PlanTimeline, RenderedPlanTimeline
from experiments.paper.timeline import EventTimeline
from experiments.paper.run_plan import RunPlan, TrialRanNoPlanError
from semantic_digital_twin.world_description.world_entity import Body

from .test_paper_run_plan import (
    ActsOnOneBody,
    CARRYING_STARTED_AT,
    MovesOnlyTheRobot,
    PICKING_ENDED_AT,
    PICKING_STARTED_AT,
    TRIAL_DURATION,
    cube,
    cylinder,
    event_at,
    trial,
)

# %% when the query these charts are shown beside was asked

ASKED_AT = 6.0
"""
Seconds into the trial the query was asked.
"""

# %% one row per item of the plan


def test_the_chart_holds_one_row_per_item_the_plan_ran(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    A reader looks down the chart for the item that was running, so every item the run
    recorded has a line of its own.
    """
    drawn = PlanTimeline().of(trial)
    assert [row.label for row in drawn.rows] == [
        "%s (%s)" % (ActsOnOneBody.__name__, cube.name.name),
        MovesOnlyTheRobot.__name__,
    ]


def test_a_row_runs_over_the_stretch_of_the_trial_its_item_ran_in(
    trial: RecordedTrial,
) -> None:
    """
    The bar of a row is the stretch its item ran over, which is what puts it under the
    events that were reported while it ran.
    """
    [picking, _] = PlanTimeline().of(trial).rows
    assert picking.spans == (
        TimelineSpan(
            start=PICKING_STARTED_AT, duration=PICKING_ENDED_AT - PICKING_STARTED_AT
        ),
    )


def test_a_row_of_an_item_that_never_finished_runs_to_the_end_of_the_trial(
    trial: RecordedTrial,
) -> None:
    """
    An item still running when the trial ended is drawn as running that far and no
    further.
    """
    [_, carrying] = PlanTimeline().of(trial).rows
    assert carrying.spans == (
        TimelineSpan(
            start=CARRYING_STARTED_AT, duration=TRIAL_DURATION - CARRYING_STARTED_AT
        ),
    )


# %% what a row is drawn in


def test_a_row_is_drawn_in_the_colour_of_the_state_its_item_was_left_in(
    trial: RecordedTrial,
) -> None:
    """
    Whether an item succeeded, failed or was still running is already a colour the
    statechart states, so the chart tells its rows apart by that rather than by one of
    its own.
    """
    [picking, carrying] = PlanTimeline().of(trial).rows
    assert (picking.color, carrying.color) == (
        LifeCycleValues.SUCCEEDED.color,
        LifeCycleValues.RUNNING.color,
    )


def test_the_item_accounting_for_the_event_is_drawn_in_the_answer_colour(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    The card picks the answer out in one colour across every panel, so the item that
    accounts for the answered event is the one the reader's eye is carried to.
    """
    picked_up = event_at(PickUpEvent, cube, PICKING_STARTED_AT + 1.0)
    drawn = PlanTimeline().of(trial, mark=ASKED_AT, emphasise=[picked_up])
    [picking, carrying] = drawn.rows
    assert picking.color == ANSWER_COLOR
    assert carrying.color == LifeCycleValues.RUNNING.color


def test_no_row_is_picked_out_when_the_plan_accounts_for_nothing(
    trial: RecordedTrial, cylinder: Body
) -> None:
    """
    An object a person pushed is accounted for by no item, so the chart shows a plan in
    which nothing is picked out -- which is the picture that says the answer is no.
    """
    shoved = event_at(TranslationEvent, cylinder, PICKING_STARTED_AT + 1.0)
    drawn = PlanTimeline().of(trial, mark=ASKED_AT, emphasise=[shoved])
    assert not any(row.accounts_for_the_event for row in drawn.rows)


def test_the_rows_that_account_for_the_event_are_the_ones_the_plan_names(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    What the chart picks out is what the plan itself says accounts for the event, rather
    than a second reading of the run that could disagree with it.
    """
    picked_up = event_at(PickUpEvent, cube, PICKING_STARTED_AT + 1.0)
    drawn = PlanTimeline().of(trial, emphasise=[picked_up])
    [picked_out] = [row for row in drawn.rows if row.accounts_for_the_event]
    assert picked_out.item == RunPlan.of(trial).accounts_for(picked_up)


# %% where the query falls on it


def test_the_chart_keeps_the_moment_the_query_was_asked(trial: RecordedTrial) -> None:
    """
    Both charts of a card are marked at the same moment, so the reader reads straight
    down from one to the other.
    """
    assert PlanTimeline().of(trial, mark=ASKED_AT).mark == ASKED_AT


def test_a_trial_that_recorded_no_plan_cannot_be_charted(trial: RecordedTrial) -> None:
    """
    There is no plan chart to draw for a run that recorded no plan, which is a state to
    report rather than an empty chart to show.
    """
    trial.insertion_attempts = []
    with pytest.raises(TrialRanNoPlanError):
        PlanTimeline().of(trial)


# %% the drawn chart itself


def test_the_chart_is_written_where_it_is_asked_for(
    trial: RecordedTrial, tmp_path: Path
) -> None:
    """
    A card names the file it wrote, so the chart leaves one where the card says.
    """
    written = PlanTimeline().of(trial, mark=ASKED_AT).write(tmp_path / "plan.png")
    assert written.is_file()
    assert written.stat().st_size > 0


def test_a_drawn_chart_is_a_panel_of_a_card(trial: RecordedTrial) -> None:
    """
    The plan chart is one of the pictures a card is made of, so a card can write it
    without knowing which of its panels it is.
    """
    assert isinstance(PlanTimeline().of(trial), RenderedPlanTimeline)


# %% the axis both charts of a card share


def test_the_chart_spans_the_whole_trial(trial: RecordedTrial) -> None:
    """
    A chart drawn only as wide as what it happens to hold would put the same second in a
    different place on each chart of a card.
    """
    assert PlanTimeline().of(trial).figure.axes[0].get_xlim() == (0.0, TRIAL_DURATION)


def test_both_charts_of_one_trial_span_the_same_seconds(trial: RecordedTrial) -> None:
    """
    The two charts are read straight down, one under the other, which only means
    anything if a second is in the same place on both.
    """
    events = EventTimeline().of(trial)
    plan = PlanTimeline().of(trial)
    assert events.figure.axes[0].get_xlim() == plan.figure.axes[0].get_xlim()
