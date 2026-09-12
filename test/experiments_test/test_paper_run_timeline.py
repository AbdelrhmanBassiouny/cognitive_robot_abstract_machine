"""
What the monitor reported, drawn over what the robot was running, on one time axis.

Two charts stacked in one figure rather than two figures: a second has to be in exactly
the same place on both, or reading straight down from a reported event to the item of
the plan under it means nothing.
"""

from __future__ import annotations

from pathlib import Path

from segmind.datastructures.events import PickUpEvent

from experiments.episodes.episode import RecordedTrial, Tick
from experiments.paper.run_timeline import (
    ANSWER_LEGEND,
    INSTANT,
    REPORTED_LEGEND,
    RenderedRunTimeline,
    RunTimeline,
)
from experiments.paper.chart import Side
from experiments.paper.panel import ANSWER_COLOR
from semantic_digital_twin.world_description.world_entity import Body

from .test_paper_run_plan import (
    PICKING_STARTED_AT,
    TRIAL_DURATION,
    cube,
    cylinder,
    event_at,
    trial,
)

# %% the moments the figure marks

ASKED_AT = 6.0
"""
Seconds into the trial the query was asked.
"""

HAPPENED_AT = PICKING_STARTED_AT + 1.0
"""
Seconds into the trial the answered event was reported.
"""

PICTURED_AT = (HAPPENED_AT - 1.0, HAPPENED_AT + 1.0)
"""
The instants the other levels of the same card show, either side of the event.
"""


def drawn(trial: RecordedTrial, cube: Body) -> RenderedRunTimeline:
    """
    The figure of the trial, marked at the query and at a pick-up of the cube.

    :param trial: The trial to draw.
    :param cube: The piece the pick-up is about.
    """
    picked_up = event_at(PickUpEvent, cube, HAPPENED_AT)
    trial.ticks.append(Tick(moment=HAPPENED_AT, events=[picked_up]))
    return RunTimeline().of(
        trial,
        asked_at=ASKED_AT,
        emphasise=[picked_up],
        happened_at=HAPPENED_AT,
        pictured_at=PICTURED_AT,
    )


# %% one axis for both


def test_both_charts_share_one_axis(trial: RecordedTrial, cube: Body) -> None:
    """
    The whole point of the figure: a second is in the same place on both charts.
    """
    figure = drawn(trial, cube).figure
    upper, lower = figure.axes[:2]

    assert upper.get_xlim() == lower.get_xlim() == (0.0, TRIAL_DURATION)
    assert upper.get_position().x0 == lower.get_position().x0
    assert upper.get_position().x1 == lower.get_position().x1


def test_the_events_are_drawn_over_the_plan(trial: RecordedTrial, cube: Body) -> None:
    figure = drawn(trial, cube).figure
    upper, lower = figure.axes[:2]

    assert upper.get_position().y0 > lower.get_position().y0


# %% what the figure is drawn from


def test_the_figure_holds_the_rows_of_both_charts(
    trial: RecordedTrial, cube: Body
) -> None:
    figure = drawn(trial, cube)

    assert [row.label for row in figure.reported] == [PickUpEvent.__name__]
    assert len(figure.ran) == 2


def test_the_event_and_the_item_accounting_for_it_share_the_answers_colour(
    trial: RecordedTrial, cube: Body
) -> None:
    figure = drawn(trial, cube)

    [reported] = figure.reported
    [accounting] = [row for row in figure.ran if row.accounts_for_the_event]
    assert reported.color == accounting.color == ANSWER_COLOR


def test_a_trial_that_recorded_no_plan_is_drawn_with_an_empty_lower_chart(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    A run that recorded no plan still reported events; the lower chart is drawn empty
    under them rather than the whole figure being left out.
    """
    trial.plans = []

    figure = drawn(trial, cube)

    assert figure.ran == ()
    assert len(figure.figure.axes) >= 2


# %% what the figure says


def test_the_key_names_what_the_colours_mean(trial: RecordedTrial, cube: Body) -> None:
    figure = drawn(trial, cube).figure

    labels = [text.get_text() for text in figure.legends[0].get_texts()]
    assert labels[:2] == [REPORTED_LEGEND, ANSWER_LEGEND]


def test_the_moments_are_named_once_over_the_upper_chart(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    Both charts carry the rules, but a name written twice is clutter; it is written over
    the upper chart only.
    """
    figure = drawn(trial, cube).figure
    upper, lower = figure.axes[:2]

    written = {text.get_text() for text in upper.texts}
    assert "reported at %.1f s" % HAPPENED_AT in written
    assert "asked at %.1f s" % ASKED_AT in written
    assert not lower.texts


def test_the_two_names_are_written_on_opposite_sides_of_their_rules(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    The query is asked right after the event it is about, so the two rules stand close
    together; the earlier name ends at its rule and the later starts at its, so they
    never run into one another.
    """
    upper = drawn(trial, cube).figure.axes[0]
    alignment_of = {
        text.get_text(): text.get_horizontalalignment() for text in upper.texts
    }

    assert alignment_of["reported at %.1f s" % HAPPENED_AT] == Side.LEFT.alignment
    assert alignment_of["asked at %.1f s" % ASKED_AT] == Side.RIGHT.alignment


def test_the_axis_says_when_the_pictures_below_were_taken(
    trial: RecordedTrial, cube: Body
) -> None:
    """
    The other levels of the card are pictures of instants; the axis names them so a
    reader can find each picture on it.
    """
    figure = drawn(trial, cube).figure
    lower = figure.axes[1]

    label = lower.get_xlabel()
    assert all(INSTANT % moment in label for moment in PICTURED_AT)


def test_the_figure_keeps_the_moment_the_query_was_asked(
    trial: RecordedTrial, cube: Body
) -> None:
    assert drawn(trial, cube).mark == ASKED_AT


def test_the_figure_is_written_where_it_is_asked_for(
    trial: RecordedTrial, cube: Body, tmp_path: Path
) -> None:
    written = drawn(trial, cube).write(tmp_path / "run.png")

    assert written.is_file() and written.stat().st_size > 0
