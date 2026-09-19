"""
Tests for the attribution scene's parts that need no recording: where a moment falls on
a chart, how a stretch is cut off at the present, when each question takes the screen,
and how the two questions are answered off the events and checked against the record.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from experiments.paper.chart import TimelineSpan
from experiments.video.attribution import (
    AnswerDisagreesWithTheRecord,
    AskedQuestion,
    AttributionScene,
    ChartRowDrawn,
    MovedQuestions,
    ReportedEvent,
    TimelineChart,
    TrialTimelines,
    shown_name,
)
from experiments.video.canvas import Area, Ink
from segmind.datastructures.events import (
    PickUpEvent,
    SupportEvent,
    TranslationEvent,
)

# %% the chart


@pytest.fixture
def chart() -> TimelineChart:
    rows = (ChartRowDrawn("TranslationEvent", (TimelineSpan(10.0, 5.0),), Ink.REPORTED.rgb),)
    return TimelineChart(Area(100, 0, 500, 100), length=100.0, rows=rows, label_width=100, title_height=0)


def test_a_moment_falls_along_the_axis_and_is_clamped_to_it(chart: TimelineChart) -> None:
    assert chart.x_of(0.0) == chart.bars.x
    assert chart.x_of(100.0) == chart.bars.right
    assert chart.x_of(50.0) == pytest.approx(chart.bars.x + chart.bars.width / 2)
    assert chart.x_of(250.0) == chart.bars.right


def test_a_stretch_is_cut_off_at_the_present(chart: TimelineChart) -> None:
    span = TimelineSpan(10.0, 5.0)
    assert chart.row_area(0, span, up_to=5.0) is None
    whole = chart.row_area(0, span, up_to=100.0)
    assert whole.width == pytest.approx(chart.bars.width * 0.05)
    half = chart.row_area(0, span, up_to=12.5)
    assert half.width == pytest.approx(whole.width / 2)


def test_an_instant_is_still_drawn_two_pixels_wide(chart: TimelineChart) -> None:
    instant = chart.row_area(0, TimelineSpan(10.0, 0.0), up_to=100.0)
    assert instant.width == 2


# %% when each question takes the screen


@dataclass
class TrialStandIn:
    duration: float = 40.0


@dataclass
class TimelinesStandIn:
    trial: TrialStandIn


@pytest.fixture
def scene() -> AttributionScene:
    questions = (
        AskedQuestion("Which objects recently moved?", (), "cube_2", asked_at=20.0),
        AskedQuestion("Did you move them?", (), "none", asked_at=20.0),
    )
    return AttributionScene(TimelinesStandIn(TrialStandIn()), film=None, questions=questions, scenario="", speed=4.0, question_for=3.0)


def test_the_film_plays_up_to_the_asking_then_each_question_takes_its_turn(scene: AttributionScene) -> None:
    assert scene.watching_for == pytest.approx(5.0)
    assert scene.duration == pytest.approx(11.0)
    assert scene.question_at(2.0) == (None, 0.0)
    question, progress = scene.question_at(5.6)
    assert question is scene.questions[0]
    assert progress == pytest.approx(0.2)
    question, progress = scene.question_at(10.9)
    assert question is scene.questions[1]
    assert progress == pytest.approx(0.9666, abs=1e-3)


def test_the_last_question_stays_on_screen_past_its_time(scene: AttributionScene) -> None:
    question, progress = scene.question_at(30.0)
    assert question is scene.questions[1]
    assert progress == 1.0


# %% the questions answered off the events


@dataclass
class QueryStandIn:
    text: str
    answer: str
    moment: float


def timelines_with(reported, answers) -> TrialTimelines:
    timelines = TrialTimelines.__new__(TrialTimelines)
    timelines.__dict__["reported"] = reported
    timelines.asked = lambda question: answers[question.__name__]
    return timelines


CUBE, PRISM = "perceived/cube_2", "perceived/rectangular_prism_0"


def test_what_moved_and_what_the_robot_moved_are_read_off_the_events() -> None:
    reported = [
        ReportedEvent(SupportEvent, CUBE, TimelineSpan(0.0, 10.0)),
        ReportedEvent(TranslationEvent, CUBE, TimelineSpan(10.0, 1.0)),
        ReportedEvent(TranslationEvent, PRISM, TimelineSpan(12.0, 1.0)),
        ReportedEvent(PickUpEvent, CUBE, TimelineSpan(11.0, 2.0)),
    ]
    answers = {
        "ObjectsThatMoved": QueryStandIn("Which objects recently moved?", f"[PrefixedName('{CUBE}'), PrefixedName('{PRISM}')]", 20.0),
        "ObjectsTheRobotMoved": QueryStandIn("Did you move them?", f"[PrefixedName('{CUBE}')]", 20.0),
    }
    moved, robot_moved = MovedQuestions(timelines_with(reported, answers)).both()
    assert moved.answer == "cube_2, rectangular_prism_0"
    assert {event.kind for event in moved.emphasised} == {TranslationEvent}
    assert robot_moved.answer == "cube_2"
    assert [event.kind for event in robot_moved.emphasised] == [PickUpEvent]
    assert robot_moved.asked_at == 20.0


def test_nothing_the_robot_moved_reads_as_none() -> None:
    reported = [ReportedEvent(TranslationEvent, CUBE, TimelineSpan(21.0, 1.0))]
    answers = {
        "ObjectsThatMoved": QueryStandIn("Which objects recently moved?", f"[PrefixedName('{CUBE}')]", 21.7),
        "ObjectsTheRobotMoved": QueryStandIn("Did you move them?", "[]", 21.7),
    }
    _, robot_moved = MovedQuestions(timelines_with(reported, answers)).both()
    assert robot_moved.answer == "none"
    assert robot_moved.emphasised == ()


def test_an_answer_that_disagrees_with_the_record_is_refused() -> None:
    reported = [ReportedEvent(TranslationEvent, CUBE, TimelineSpan(21.0, 1.0))]
    answers = {"ObjectsThatMoved": QueryStandIn("Which objects recently moved?", "[]", 21.7)}
    with pytest.raises(AnswerDisagreesWithTheRecord):
        MovedQuestions(timelines_with(reported, answers)).which_moved()


def test_a_bodys_name_is_shown_without_the_twins_prefix() -> None:
    assert shown_name("perceived/cube_2") == "cube_2"
    assert shown_name("board") == "board"
