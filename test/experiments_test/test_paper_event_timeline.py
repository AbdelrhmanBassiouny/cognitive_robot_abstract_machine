"""
When each kind of event was reported while a trial ran, and where in that the query
being shown was asked.

The chart is asserted off the rows it is drawn from rather than off its pixels: what a
reader has to be able to read off it is which kinds of event there were, when each was
reported and which one the query answered, and all three are rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from coraplex.datastructures.enums import ExecutionType
from segmind.datastructures.events import DetectionEvent, InsertionEvent, PickUpEvent
from typing_extensions import Type

from experiments.episodes.episode import Episode, RecordedTrial, Tick
from experiments.paper.timeline import EventTimeline, RenderedTimeline, TimelineRow
from experiments.scenarios.trial import TrialOutcome
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body

# %% a trial with two kinds of event in it

TRIAL_DURATION = 10.0
"""
How long the recorded trial ran, in seconds, which is where its last bar ends.
"""

PICKED_UP_AT = 1.0
"""
The moment the trial's pick-up was reported at, in seconds from its start.
"""

INSERTED_AT = 4.0
"""
The moment the trial's insertion was reported at, in seconds from its start.
"""

ASKED_AT = 5.0
"""
The moment the query being shown was asked at, in seconds from the trial's start.
"""


@pytest.fixture
def tracked_shape() -> Body:
    """
    The shape both of the trial's events are about.
    """
    return Body(name=PrefixedName("square_piece"))


@pytest.fixture
def trial_with_two_kinds_of_event(tracked_shape: Body) -> RecordedTrial:
    """
    One recorded trial whose monitor reported a pick-up and, later, an insertion.
    """
    return RecordedTrial(
        episode=Episode(
            scenario_name="shape_sorting", execution_type=ExecutionType.SIMULATED
        ),
        outcome=TrialOutcome.SUCCEEDED,
        duration=TRIAL_DURATION,
        ticks=[
            Tick(
                moment=PICKED_UP_AT, events=[PickUpEvent(tracked_object=tracked_shape)]
            ),
            Tick(
                moment=INSERTED_AT,
                events=[InsertionEvent(tracked_object=tracked_shape)],
            ),
        ],
    )


def row_for(
    timeline: RenderedTimeline, event_type: Type[DetectionEvent]
) -> TimelineRow:
    """
    The one row of a drawn timeline reporting the given kind of event.

    :param timeline: The timeline that was drawn.
    :param event_type: The kind of event the row is wanted for.
    :raises AssertionError: If the timeline holds any other number of rows for it.
    """
    rows = [row for row in timeline.rows if row.event_type is event_type]
    assert len(rows) == 1, f"expected one row of {event_type}, found {len(rows)}"
    return rows[0]


# %% what the chart is made of


def test_each_kind_of_event_the_trial_reported_gets_one_row(
    trial_with_two_kinds_of_event: RecordedTrial,
) -> None:
    """
    A row is a kind of event, so a trial reporting two kinds is drawn on two rows
    whatever number of times each of them was reported.
    """
    timeline = EventTimeline().of(trial_with_two_kinds_of_event)
    assert [row.event_type for row in timeline.rows] == [PickUpEvent, InsertionEvent]


def test_a_row_runs_from_the_tick_that_reported_it_to_the_next_one(
    trial_with_two_kinds_of_event: RecordedTrial,
) -> None:
    """
    A tick says what was seen at a moment, so its bar reaches to the next tick; the
    trial's last tick reaches the end of the trial.
    """
    timeline = EventTimeline().of(trial_with_two_kinds_of_event)
    picked_up = row_for(timeline, PickUpEvent)
    inserted = row_for(timeline, InsertionEvent)
    assert [(span.start, span.duration) for span in picked_up.spans] == [
        (PICKED_UP_AT, INSERTED_AT - PICKED_UP_AT)
    ]
    assert [(span.start, span.duration) for span in inserted.spans] == [
        (INSERTED_AT, TRIAL_DURATION - INSERTED_AT)
    ]


def test_a_trial_that_reported_nothing_is_drawn_with_no_rows() -> None:
    """
    A trial whose monitor saw nothing has an empty chart rather than a made-up one.
    """
    timeline = EventTimeline().of(
        RecordedTrial(
            episode=Episode(
                scenario_name="shape_sorting", execution_type=ExecutionType.SIMULATED
            ),
            outcome=TrialOutcome.SUCCEEDED,
            duration=TRIAL_DURATION,
        )
    )
    assert timeline.rows == ()


# %% the moment the query was asked


def test_the_marked_moment_is_the_one_the_query_was_asked_at(
    trial_with_two_kinds_of_event: RecordedTrial,
) -> None:
    """
    The rule down the chart stands where the query being shown was asked.
    """
    timeline = EventTimeline().of(trial_with_two_kinds_of_event, mark=ASKED_AT)
    assert timeline.mark == ASKED_AT


def test_a_timeline_shown_beside_no_query_is_marked_nowhere(
    trial_with_two_kinds_of_event: RecordedTrial,
) -> None:
    """
    A chart drawn on its own has no moment to point at, so it points at none.
    """
    assert EventTimeline().of(trial_with_two_kinds_of_event).mark is None


# %% the event the query answered


def test_the_row_of_an_emphasised_event_is_the_one_marked(
    trial_with_two_kinds_of_event: RecordedTrial, tracked_shape: Body
) -> None:
    """
    The event a query answered is what the chart picks out, and it picks out that
    event's own row and no other.
    """
    timeline = EventTimeline().of(
        trial_with_two_kinds_of_event,
        mark=ASKED_AT,
        emphasise=[PickUpEvent(tracked_object=tracked_shape)],
    )
    assert row_for(timeline, PickUpEvent).emphasised
    assert not row_for(timeline, InsertionEvent).emphasised


def test_no_row_is_marked_when_the_query_answered_no_event(
    trial_with_two_kinds_of_event: RecordedTrial,
) -> None:
    """
    A query about the scene rather than about something that happened leaves every row
    drawn the same way.
    """
    timeline = EventTimeline().of(trial_with_two_kinds_of_event, mark=ASKED_AT)
    assert not any(row.emphasised for row in timeline.rows)


# %% the chart itself


def test_the_written_chart_is_a_file_on_disk(
    trial_with_two_kinds_of_event: RecordedTrial, tmp_path: Path
) -> None:
    """
    The chart is written as a picture the paper can include.
    """
    written = (
        EventTimeline()
        .of(trial_with_two_kinds_of_event, mark=ASKED_AT)
        .write(tmp_path / "timeline.png")
    )
    assert written.is_file()
    assert written.stat().st_size > 0
