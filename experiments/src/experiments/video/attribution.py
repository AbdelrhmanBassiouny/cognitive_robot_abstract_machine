"""
What the robot saw happen, set against what it was running, and a question about who
moved what answered from both.

The robot's own camera plays beside two timelines that grow with it: the events the
event segmentation reported, over the actions the plan was running. When the recorded
question arrives the film stands still, the question takes the screen with the statement
behind it, the moment it was asked is ruled onto the timelines, the events the answer
rests on light up, and the answer follows -- the robot reading its own record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property

import cv2
import numpy as np
from typing_extensions import Dict, List, Optional, Sequence, Set, Tuple, Type

from experiments.episodes.episode import RecordedQuery, RecordedTrial
from experiments.montessori.same_piece import SamePiece
from experiments.paper.chart import TimelineSpan
from experiments.paper.lettering import Face
from experiments.paper.plan_timeline import PlanRow, PlanTimeline
from experiments.paper.run_plan import RunPlan, plans_of
from experiments.paper.timeline import EventTimeline, TimelineRow
from experiments.questions.question import Question
from experiments.questions.working_memory import (
    ObjectsThatMoved,
    ObjectsTheRobotMoved,
)
from experiments.video.canvas import (
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Rgb,
    Typesetting,
    dimmed,
    filled,
    fitted,
    framed,
)
from experiments.video.footage import TABLE_FRAMING, CameraFilm, Framing
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, eased
from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    AgentInteractionEvent,
    DetectionEvent,
    MotionEvent,
)

CLOSE_UP = Resolution(width=1600, height=900)
"""
The size the scene draws itself at.
"""

REPORTED_TITLE = "what the monitor reported"
"""
What is written over the chart of events.
"""

RUNNING_TITLE = "what the robot was running"
"""
What is written over the chart of the plan.
"""

NO_PLAN_RAN = "no action ran"
"""
What is written in the chart of the plan when the trial ran none.
"""

BODY_PREFIX = "perceived/"
"""
What the twin puts before the name of a body the look found; dropped on screen.
"""

NAMED_BODY = re.compile(r"PrefixedName\('([^']+)'\)")
"""
How a body is named in the answer a query recorded.
"""

TITLE_HEIGHT = 34
"""
Pixels a chart keeps for its title.
"""

AXIS_HEIGHT = 56
"""
Pixels the lower chart keeps under its rows for the seconds.
"""

CHART_GAP = 20
"""
Pixels between the two charts.
"""


# %% what the trial recorded, laid on its time axis


@dataclass(frozen=True)
class ReportedEvent:
    """
    One event a tick reported, and the stretch of the trial the tick stands for.
    """

    kind: Type[DetectionEvent]
    """
    What kind of event it is.
    """

    about: str
    """
    The name of the body it is about.
    """

    span: TimelineSpan
    """
    The stretch of the trial it was reported over.
    """


@dataclass
class TrialTimelines:
    """
    One trial's events and plan as the rows of its two timelines, and its queries.
    """

    run: RecordedRun
    """
    The run the trial belongs to.
    """

    @property
    def trial(self) -> RecordedTrial:
        return self.run.trial

    @cached_property
    def event_rows(self) -> Tuple[TimelineRow, ...]:
        """
        One row per kind of event the trial reported, in the order they were first seen.
        """
        return EventTimeline().rows_of(self.trial, ())

    @cached_property
    def plan_rows(self) -> Tuple[PlanRow, ...]:
        """
        One row per item of the plan the trial ran, or none where it ran no plan.
        """
        if not plans_of(self.trial):
            return ()
        return PlanTimeline.rows_of(RunPlan.of(self.trial, identity=SamePiece()), ())

    @cached_property
    def reported(self) -> List[ReportedEvent]:
        """
        Every event of every tick, with the stretch its tick stands for.
        """
        return [
            ReportedEvent(type(event), event.tracked_object.name.name, span)
            for tick, span in EventTimeline.spans_of(self.trial)
            for event in tick.events
        ]

    def reported_about(
        self, names: Set[str], kind: Type[DetectionEvent]
    ) -> List[ReportedEvent]:
        """
        The events of a kind reported about the named bodies.

        :param names: The bodies' names, as the twin holds them.
        :param kind: The kind of event, taken with its subclasses.
        """
        return [
            event
            for event in self.reported
            if issubclass(event.kind, kind) and event.about in names
        ]

    def asked(self, question: Type[Question]) -> RecordedQuery:
        """
        The query of a kind the trial recorded.

        :param question: The kind of question.
        """
        return next(
            query
            for query in self.trial.queries
            if isinstance(query.question, question)
        )


# %% the questions, as the scene puts them


@dataclass
class AnswerDisagreesWithTheRecord(DataclassException):
    """
    Raised when the bodies read off the events are not the ones the recorded answer
    names.
    """

    english: str
    read_off_the_events: Set[str]
    recorded: str

    def error_message(self) -> str:
        return (
            f"{self.english!r}: the events name {sorted(self.read_off_the_events)}, "
            f"the recorded answer says {self.recorded!r}"
        )

    def suggest_correction(self) -> str:
        return "Read the answer the way the question's query does, off the same events."


@dataclass(frozen=True)
class AskedQuestion:
    """
    One recorded question as the scene shows it: its words, the statement behind it,
    the events its answer rests on, and the answer.
    """

    english: str
    """
    The question as it was asked.
    """

    statement: Tuple[str, ...]
    """
    The query behind it, line by line.
    """

    answer: str
    """
    The answer, as written on screen.
    """

    asked_at: float
    """
    Seconds into the trial it was asked.
    """

    emphasised: Tuple[ReportedEvent, ...] = ()
    """
    The events the answer rests on.
    """


def shown_name(body: str) -> str:
    """
    A body's name as it is written on screen.

    :param body: The name as the twin holds it.
    """
    return body.removeprefix(BODY_PREFIX)


@dataclass
class MovedQuestions:
    """
    The two recorded questions that tell what moved from what the robot moved, each
    answered from the events the trial reported and checked against the answer it
    recorded.
    """

    timelines: TrialTimelines
    """
    The trial's record.
    """

    @cached_property
    def moved(self) -> Set[str]:
        """
        The bodies the monitor saw move.
        """
        return {event.about for event in self.timelines.reported_about(self.every_body, MotionEvent)}

    @cached_property
    def acted_on(self) -> Set[str]:
        """
        The bodies the robot acted on.
        """
        return {
            event.about
            for event in self.timelines.reported_about(self.every_body, AgentInteractionEvent)
        }

    @property
    def every_body(self) -> Set[str]:
        return {event.about for event in self.timelines.reported}

    def which_moved(self) -> AskedQuestion:
        """
        Which objects recently moved: every body a motion event was reported about.
        """
        query = self.timelines.asked(ObjectsThatMoved)
        self._check(query, self.moved)
        return AskedQuestion(
            english=query.text,
            statement=("motion = a(MotionEvent)", "motion.tracked_object"),
            answer=self._listed(self.moved),
            asked_at=query.moment,
            emphasised=tuple(self.timelines.reported_about(self.moved, MotionEvent)),
        )

    def did_you_move_them(self) -> AskedQuestion:
        """
        Did you move them: the bodies that moved and that the robot acted on.
        """
        query = self.timelines.asked(ObjectsTheRobotMoved)
        answer = self.moved & self.acted_on
        self._check(query, answer)
        return AskedQuestion(
            english=query.text,
            statement=(
                "motion = a(MotionEvent)",
                "interaction = an(AgentInteractionEvent)(",
                "    tracked_object=motion.tracked_object)",
                "interaction.tracked_object",
            ),
            answer=self._listed(answer),
            asked_at=query.moment,
            emphasised=tuple(self.timelines.reported_about(answer, AgentInteractionEvent)),
        )

    def both(self) -> Tuple[AskedQuestion, AskedQuestion]:
        return self.which_moved(), self.did_you_move_them()

    @staticmethod
    def _listed(bodies: Set[str]) -> str:
        return ", ".join(sorted(shown_name(body) for body in bodies)) if bodies else "none"

    @staticmethod
    def _check(query: RecordedQuery, bodies: Set[str]) -> None:
        """
        Refuse an answer read off the events that names other bodies than the recorded
        answer does; the record writes each body with the twin's prefix, the events
        without it.
        """
        recorded = {shown_name(body) for body in NAMED_BODY.findall(query.answer)}
        if recorded != {shown_name(body) for body in bodies}:
            raise AnswerDisagreesWithTheRecord(query.text, bodies, query.answer)


# %% the charts


@dataclass(frozen=True)
class ChartRowDrawn:
    """
    One row of a chart as it is drawn: its label, its stretches and their colour.
    """

    label: str
    spans: Tuple[TimelineSpan, ...]
    color: Rgb


@dataclass
class TimelineChart:
    """
    Rows of stretches over one time axis, drawn up to a moment.
    """

    area: Area
    """
    Where the rows go, labels included.
    """

    length: float
    """
    Seconds the axis runs for.
    """

    rows: Tuple[ChartRowDrawn, ...]
    """
    What is drawn.
    """

    title: str = ""
    """
    What is written over the rows.
    """

    label_width: float = 210
    """
    Pixels kept for the labels down the side.
    """

    title_height: float = 34
    """
    Pixels kept for the title.
    """

    axis_height: float = 0
    """
    Pixels kept under the rows for the seconds, or none.
    """

    @property
    def bars(self) -> Area:
        """
        Where the stretches go.
        """
        return Area(
            self.area.x + self.label_width,
            self.area.y + self.title_height,
            self.area.width - self.label_width,
            self.area.height - self.title_height - self.axis_height,
        )

    @property
    def row_height(self) -> float:
        return self.bars.height / max(len(self.rows), 1)

    def x_of(self, second: float) -> float:
        """
        Where a moment falls along the axis.
        """
        return self.bars.x + self.bars.width * min(max(second, 0.0), self.length) / self.length

    def row_area(self, index: int, span: TimelineSpan, up_to: float) -> Optional[Area]:
        """
        Where one stretch of one row is drawn, cut off at a moment, or None when it has
        not begun.
        """
        if span.start > up_to:
            return None
        left = self.x_of(span.start)
        right = max(self.x_of(min(span.end, up_to)), left + 2)
        top = self.bars.y + index * self.row_height + self.row_height * 0.2
        return Area(left, top, right - left, self.row_height * 0.6)

    def drawn(self, frame: Frame, up_to: float) -> Frame:
        """
        The chart on a frame, its stretches cut off at a moment.
        """
        if self.title:
            frame = Typesetting(size=22, face=Face.BOLD).written(
                frame, self.title, (self.area.x, self.area.y + self.title_height / 2), Anchor.LEFT_MIDDLE
            )
        label = Typesetting(size=18, color=Ink.TEXT.rgb)
        frame = filled(frame, Area(self.bars.x, self.bars.y, 2, self.bars.height), Ink.HAIRLINE.rgb)
        for index, row in enumerate(self.rows):
            middle = self.bars.y + index * self.row_height + self.row_height / 2
            frame = label.written(frame, row.label, (self.bars.x - 10, middle), Anchor.RIGHT_MIDDLE)
            for span in row.spans:
                area = self.row_area(index, span, up_to)
                if area is not None:
                    frame = filled(frame, area, row.color)
        if not self.rows:
            frame = Typesetting(size=20, color=Ink.MUTED.rgb).written(
                frame, NO_PLAN_RAN, self.bars.centre, Anchor.CENTRE_MIDDLE
            )
        return self._axis(frame) if self.axis_height else frame

    def _axis(self, frame: Frame) -> Frame:
        baseline = self.bars.bottom
        frame = filled(frame, Area(self.bars.x, baseline, self.bars.width, 2), Ink.HAIRLINE.rgb)
        step = 50.0 if self.length > 100 else 10.0 if self.length > 30 else 5.0
        small = Typesetting(size=17, color=Ink.MUTED.rgb)
        tick = 0.0
        while tick <= self.length:
            frame = filled(frame, Area(self.x_of(tick) - 1, baseline, 2, 8), Ink.HAIRLINE.rgb)
            frame = small.written(frame, f"{tick:g}", (self.x_of(tick), baseline + 22), Anchor.CENTRE_MIDDLE)
            tick += step
        return small.written(
            frame, "seconds into the trial", (self.bars.right, baseline + 46), Anchor.RIGHT_MIDDLE
        )

    def emphasised(self, frame: Frame, events: Sequence[ReportedEvent], weight: float) -> Frame:
        """
        The given events drawn over the chart in the answer's colour.
        """
        if weight <= 0.0:
            return frame
        overlay = frame.copy()
        by_label = {row.label: index for index, row in enumerate(self.rows)}
        for event in events:
            index = by_label.get(event.kind.__name__)
            if index is None:
                continue
            area = self.row_area(index, event.span, self.length)
            if area is not None:
                overlay = filled(overlay, area.inset(-2), Ink.ANSWER.rgb)
        cv2.addWeighted(overlay, weight, frame, 1 - weight, 0, frame)
        return frame

    def ruled(self, frame: Frame, second: float, color: Rgb, thickness: int = 2) -> Frame:
        """
        A vertical rule across the rows at a moment.
        """
        x = self.x_of(second)
        return filled(frame, Area(x - thickness / 2, self.bars.y, thickness, self.bars.height), color)


# %% the scene


@dataclass
class AttributionScene(Scene):
    """
    The robot's camera and its two timelines playing together up to the moment a
    question was asked, then each question taking the screen and being answered off
    the timelines.
    """

    timelines: TrialTimelines
    """
    The trial's record.
    """

    film: CameraFilm
    """
    The trial's camera recording.
    """

    questions: Tuple[AskedQuestion, ...]
    """
    The questions, in the order they are asked.
    """

    scenario: str
    """
    What is written under the film: what was going on in this trial.
    """

    speed: float = 20.0
    """
    How many recorded seconds pass per second played while the film runs.
    """

    question_for: float = 4.5
    """
    Seconds each question takes, from arriving to its answer having been read.
    """

    resolution: Resolution = CLOSE_UP
    """
    The size the scene draws itself at.
    """

    framing: Framing = TABLE_FRAMING
    """
    What of each picture of the film is shown.
    """

    film_area: Area = field(default_factory=lambda: Area(40, 96, 780, 439))
    """
    Where the film plays.
    """

    charts_area: Area = field(default_factory=lambda: Area(880, 90, 680, 730))
    """
    Where the two charts stand, one over the other.
    """

    row_pitch: float = 40.0
    """
    The most pixels one row of a chart takes.
    """

    @property
    def asked_at(self) -> float:
        """
        Seconds into the trial the questions were asked.
        """
        return self.questions[0].asked_at

    @property
    def horizon(self) -> float:
        """
        Seconds into the trial the record is shown up to: the asking, or the last event
        an answer rests on where it was reported in the same breath as the asking.
        """
        latest = max(
            (event.span.start for question in self.questions for event in question.emphasised),
            default=0.0,
        )
        return max(self.asked_at, latest)

    @property
    def watching_for(self) -> float:
        """
        Seconds the film plays before the first question.
        """
        return self.horizon / self.speed

    @property
    def duration(self) -> float:
        return self.watching_for + self.question_for * len(self.questions)

    @property
    def pitch(self) -> float:
        """
        Pixels one row takes, the same on both charts: as much as the charts' room
        allows, up to :attr:`row_pitch`; a chart with no rows keeps room for two.
        """
        rows = len(self.timelines.event_rows) + max(len(self.timelines.plan_rows), 2)
        return min(self.row_pitch, (self.charts_area.height - 2 * TITLE_HEIGHT - AXIS_HEIGHT - CHART_GAP) / rows)

    @cached_property
    def reported_chart(self) -> TimelineChart:
        rows = tuple(
            ChartRowDrawn(row.label, row.spans, Ink.REPORTED.rgb) for row in self.timelines.event_rows
        )
        height = TITLE_HEIGHT + self.pitch * len(rows)
        return TimelineChart(
            Area(self.charts_area.x, self.charts_area.y, self.charts_area.width, height),
            self.timelines.trial.duration,
            rows,
            title=REPORTED_TITLE,
            title_height=TITLE_HEIGHT,
        )

    @cached_property
    def running_chart(self) -> TimelineChart:
        rows = tuple(
            ChartRowDrawn(row.label, row.spans, Ink.FIRED.rgb) for row in self.timelines.plan_rows
        )
        top = self.reported_chart.area.bottom + CHART_GAP
        height = TITLE_HEIGHT + self.pitch * max(len(rows), 2) + AXIS_HEIGHT
        return TimelineChart(
            Area(self.charts_area.x, top, self.charts_area.width, height),
            self.timelines.trial.duration,
            rows,
            title=RUNNING_TITLE,
            title_height=TITLE_HEIGHT,
            axis_height=AXIS_HEIGHT,
        )

    def question_at(self, seconds: float) -> Tuple[Optional[AskedQuestion], float]:
        """
        The question on screen at a moment and how far it has got, from zero to one,
        or None and zero while the film still runs.
        """
        if seconds < self.watching_for:
            return None, 0.0
        index = min(int((seconds - self.watching_for) / self.question_for), len(self.questions) - 1)
        progress = (seconds - self.watching_for - index * self.question_for) / self.question_for
        return self.questions[index], min(progress, 1.0)

    def picture_at(self, seconds: float) -> Frame:
        now = min(seconds * self.speed, self.horizon)
        question, progress = self.question_at(seconds)
        frame = self.resolution.blank(255)
        frame = self._film(frame, now, question is not None)
        for chart in (self.reported_chart, self.running_chart):
            frame = chart.drawn(frame, now)
            frame = chart.ruled(frame, now, Ink.TEXT.rgb)
        if question is not None:
            frame = self._asked(frame, question, progress)
        return Typesetting(size=26, color=Ink.TEXT.rgb).written(
            frame, self.scenario, (self.film_area.centre[0], self.resolution.stage_height - 40), Anchor.CENTRE_MIDDLE
        )

    def _film(self, frame: Frame, now: float, held: bool) -> Frame:
        image = self.framing.of(self.film.at(self.timelines.run.recording_second_of(self.timelines.trial, now)).image)
        if held:
            image = dimmed(image, 0.6)
        frame = fitted(frame, image, self.film_area)
        badge = Area(self.film_area.right - 130, self.film_area.y + 16, 114, 44)
        frame = filled(frame, badge, Ink.TEXT.rgb)
        frame = Typesetting(size=26, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            frame, f"×{self.speed:g}", badge.centre, Anchor.CENTRE_MIDDLE
        )
        clock = Area(self.film_area.x + 16, self.film_area.y + 16, 150, 44)
        frame = filled(frame, clock, Ink.TEXT.rgb)
        return Typesetting(size=24, face=Face.BOLD, color=Ink.PAPER.rgb).written(
            frame, f"{now:5.1f} s", clock.centre, Anchor.CENTRE_MIDDLE
        )

    def _asked(self, frame: Frame, question: AskedQuestion, progress: float) -> Frame:
        """
        The question over the film, the asking ruled onto the charts, the events its
        answer rests on lit, and the answer -- each in its turn.
        """
        card = self.film_area.inset(40)
        frame = filled(frame, card, Ink.PAPER.rgb)
        frame = framed(frame, card, Ink.ASKED.rgb, thickness=3)
        frame = Typesetting(size=30, face=Face.BOLD).written(
            frame, question.english, (card.x + 30, card.y + 48), Anchor.LEFT_MIDDLE
        )
        code = CodeTypesetting(size=21)
        for number, line in enumerate(question.statement):
            frame = code.written(frame, line, (card.x + 30, card.y + 100 + number * 30))
        ruled = eased((progress - 0.12) / 0.15)
        lit = eased((progress - 0.35) / 0.2)
        answered = eased((progress - 0.6) / 0.15)
        if ruled > 0:
            for chart in (self.reported_chart, self.running_chart):
                frame = chart.ruled(frame, question.asked_at, Ink.ASKED.rgb, thickness=4)
            frame = Typesetting(size=20, face=Face.BOLD, color=Ink.ASKED.rgb).written(
                frame,
                f"asked at {question.asked_at:.1f} s",
                (self.reported_chart.x_of(question.asked_at) - 8, self.reported_chart.area.y + 16),
                Anchor.RIGHT_MIDDLE,
            )
        frame = self.reported_chart.emphasised(frame, question.emphasised, lit)
        if answered > 0:
            answer = Typesetting(size=28, face=Face.BOLD, color=Ink.ANSWER.rgb)
            frame = answer.written(
                frame,
                answer.wrapped(f"→ {question.answer}", card.width - 60),
                (card.x + 30, card.bottom - 76),
                Anchor.LEFT_MIDDLE,
            )
        return frame
