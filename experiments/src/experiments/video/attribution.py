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
    BODY_SIZE,
    LABEL_SIZE,
    MARGIN,
    VIDEO_RESOLUTION,
    Anchor,
    Area,
    CodeTypesetting,
    Ink,
    Rgb,
    Typesetting,
    filled,
    framed,
    pasted,
)
from experiments.video.footage import TABLE_FRAMING, CameraFilm, Framing, badged, speed_badged
from experiments.video.sources import RecordedRun
from experiments.video.timeline import Frame, Resolution, Scene, blended, eased
from krrood.exceptions import DataclassException
from segmind.datastructures.events import (
    AgentInteractionEvent,
    DetectionEvent,
    MotionEvent,
)

ROBOT_ACTION = "robot action"
"""
What the one strip merging everything the robot was running is called.
"""

NO_PLAN_RAN = "none"
"""
What is written in the robot's strip when the trial ran no action.
"""

BODY_PREFIX = "perceived/"
"""
What the twin puts before the name of a body the look found; dropped on screen.
"""

NAMED_BODY = re.compile(r"PrefixedName\('([^']+)'\)")
"""
How a body is named in the answer a query recorded.
"""

ROW_PITCH = 34
"""
Pixels one row of the timeline takes.
"""

AXIS_HEIGHT = 44
"""
Pixels the timeline keeps under its rows for the seconds.
"""

PANEL_WIDTH = 560
"""
Pixels the timeline's panel over the footage is wide.
"""

PANEL_OPACITY = 0.9
"""
How far the timeline's panel covers the footage under it.
"""

HEADER_CLEAR = 96
"""
Pixels from the top kept clear for the chapter's pill and the badges.
"""

CARD_PADDING = 24
"""
Pixels between a question's card and its words.
"""

CARD_ROW = 36
"""
Pixels one row of a question or its answer takes.
"""

CODE_PITCH = 28
"""
Pixels one line of a question's statement takes.
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
        One row per kind of event the questions are about -- the motions, and what
        the robot did to a body -- in the order they were first seen.
        """
        kinds = {event.kind.__name__ for event in self.reported if issubclass(event.kind, (MotionEvent, AgentInteractionEvent))}
        return tuple(row for row in EventTimeline().rows_of(self.trial, ()) if row.label in kinds)

    @cached_property
    def plan_rows(self) -> Tuple[PlanRow, ...]:
        """
        One row per item of the plan the trial ran, or none where it ran no plan.
        """
        if not plans_of(self.trial):
            return ()
        return PlanTimeline.rows_of(RunPlan.of(self.trial, identity=SamePiece()), ())

    @cached_property
    def robot_spans(self) -> Tuple[TimelineSpan, ...]:
        """
        Every stretch the robot was running some action over, as one strip.
        """
        return tuple(span for row in self.plan_rows for span in row.spans)

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

    label_width: float = 190
    """
    Pixels kept for the labels down the side.
    """

    title_height: float = 0
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
            frame = Typesetting(size=LABEL_SIZE, face=Face.BOLD).written(
                frame, self.title, (self.area.x, self.area.y + self.title_height / 2), Anchor.LEFT_MIDDLE
            )
        label = Typesetting(size=LABEL_SIZE, color=Ink.TEXT.rgb)
        frame = filled(frame, Area(self.bars.x, self.bars.y, 2, self.bars.height), Ink.HAIRLINE.rgb)
        for index, row in enumerate(self.rows):
            middle = self.bars.y + index * self.row_height + self.row_height / 2
            frame = label.written(frame, row.label, (self.bars.x - 10, middle), Anchor.RIGHT_MIDDLE)
            for span in row.spans:
                area = self.row_area(index, span, up_to)
                if area is not None:
                    frame = filled(frame, area, row.color)
        return self._axis(frame) if self.axis_height else frame

    def _axis(self, frame: Frame) -> Frame:
        baseline = self.bars.bottom
        frame = filled(frame, Area(self.bars.x, baseline, self.bars.width, 2), Ink.HAIRLINE.rgb)
        step = 50.0 if self.length > 100 else 10.0 if self.length > 30 else 5.0
        small = Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb)
        tick = 0.0
        while tick <= self.length:
            frame = filled(frame, Area(self.x_of(tick) - 1, baseline, 2, 8), Ink.HAIRLINE.rgb)
            frame = small.written(frame, f"{tick:g} s" if tick == 0.0 else f"{tick:g}", (self.x_of(tick), baseline + 24), Anchor.CENTRE_MIDDLE)
            tick += step
        return frame

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
    The robot's camera filling the frame, its timeline over it playing up to the
    moment a question was asked, then each question over the footage, answered off
    the timeline.
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

    speed: float = 20.0
    """
    How many recorded seconds pass per second played while the film runs.
    """

    question_for: float = 4.5
    """
    Seconds each question takes, from arriving to its answer having been read.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size the scene draws itself at: the video's own, the footage filling it.
    """

    framing: Framing = TABLE_FRAMING
    """
    What of each picture of the film is shown.
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
    def panel(self) -> Area:
        """
        Where the timeline lies: over the footage, at the right, under the badges.
        """
        rows = len(self.timelines.event_rows) + 1
        height = ROW_PITCH * rows + AXIS_HEIGHT + 16
        return Area(self.resolution.width - MARGIN - PANEL_WIDTH, HEADER_CLEAR, PANEL_WIDTH, height)

    @property
    def card_width(self) -> float:
        return self.panel.x - MARGIN - 24

    def card_for(self, question: AskedQuestion) -> Area:
        """
        Where a question stands: over the footage, at the left, as tall as its words,
        its statement and its answer need.
        """
        asked = Typesetting(size=BODY_SIZE, face=Face.BOLD)
        width = self.card_width - 2 * CARD_PADDING
        question_rows = asked.wrapped(question.english, width).count("\n") + 1
        answer_rows = asked.wrapped(f"→ {question.answer}", width).count("\n") + 1
        height = (
            CARD_PADDING
            + question_rows * CARD_ROW
            + 12
            + len(question.statement) * CODE_PITCH
            + 12
            + answer_rows * CARD_ROW
            + CARD_PADDING
        )
        return Area(MARGIN, HEADER_CLEAR, self.card_width, height)

    @cached_property
    def chart(self) -> TimelineChart:
        rows = tuple(
            ChartRowDrawn(row.label, row.spans, Ink.REPORTED.rgb) for row in self.timelines.event_rows
        )
        rows += (ChartRowDrawn(ROBOT_ACTION, self.timelines.robot_spans, Ink.TEXT.rgb),)
        panel = self.panel
        return TimelineChart(
            Area(panel.x + 8, panel.y + 8, panel.width - 16, panel.height - 16),
            self.timelines.trial.duration,
            rows,
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
        frame = self._film(frame=self.resolution.blank(0), now=now)
        frame = self._panel_drawn(frame, now)
        if question is not None:
            frame = self._asked(frame, question, progress)
        return frame

    def _film(self, frame: Frame, now: float) -> Frame:
        image = self.framing.of(self.film.at(self.timelines.run.recording_second_of(self.timelines.trial, now)).image)
        frame = pasted(frame, image, Area.whole(self.resolution))
        frame = speed_badged(frame, self.speed)
        return badged(frame, f"{now:5.1f} s", (self.resolution.width - MARGIN - 90, MARGIN), Anchor.RIGHT_TOP)

    def _panel_drawn(self, frame: Frame, now: float) -> Frame:
        """
        The timeline on its panel over the footage, played up to a moment.
        """
        panel = self.panel
        drawn = filled(frame, panel, Ink.PAPER.rgb)
        drawn = self.chart.drawn(drawn, now)
        drawn = self.chart.ruled(drawn, now, Ink.TEXT.rgb)
        if not self.timelines.robot_spans:
            drawn = Typesetting(size=LABEL_SIZE, color=Ink.MUTED.rgb).written(
                drawn, NO_PLAN_RAN, (self.chart.bars.x + 12, self.chart.bars.bottom - self.chart.row_height / 2), Anchor.LEFT_MIDDLE
            )
        return blended(frame, drawn, PANEL_OPACITY)

    def _asked(self, frame: Frame, question: AskedQuestion, progress: float) -> Frame:
        """
        The question over the footage, the asking ruled onto the timeline, the events
        its answer rests on lit, and the answer -- each in its turn.
        """
        card = self.card_for(question)
        frame = filled(frame, card, Ink.PAPER.rgb)
        frame = framed(frame, card, Ink.HAIRLINE.rgb, thickness=2)
        asked = Typesetting(size=BODY_SIZE, face=Face.BOLD)
        width = card.width - 2 * CARD_PADDING
        words = asked.wrapped(question.english, width)
        frame = asked.written(frame, words, (card.x + CARD_PADDING, card.y + CARD_PADDING), Anchor.LEFT_TOP)
        code = CodeTypesetting(size=LABEL_SIZE)
        code_top = card.y + CARD_PADDING + (words.count("\n") + 1) * CARD_ROW + 12
        for number, line in enumerate(question.statement):
            frame = code.written(frame, line, (card.x + CARD_PADDING, code_top + (number + 0.5) * CODE_PITCH))
        ruled = eased((progress - 0.12) / 0.15)
        lit = eased((progress - 0.35) / 0.2)
        answered = eased((progress - 0.6) / 0.15)
        if ruled > 0:
            frame = self.chart.ruled(frame, question.asked_at, Ink.ANSWER.rgb, thickness=4)
            frame = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.ANSWER.rgb).written(
                frame,
                f"asked at {question.asked_at:.1f} s",
                (self.chart.x_of(question.asked_at) - 8, self.chart.bars.y - 2),
                Anchor.RIGHT_TOP,
            )
        frame = self.chart.emphasised(frame, question.emphasised, lit)
        if lit > 0 and len(question.emphasised) == 1:
            [event] = question.emphasised
            frame = Typesetting(size=LABEL_SIZE, face=Face.BOLD, color=Ink.ANSWER.rgb).written(
                frame, f"reported at {event.span.start:.1f} s", (self.chart.x_of(event.span.start) + 8, self.chart.bars.y - 2), Anchor.LEFT_TOP
            )
        if answered > 0:
            answer = Typesetting(size=BODY_SIZE, face=Face.BOLD, color=Ink.ANSWER.rgb)
            frame = answer.written(
                frame,
                answer.wrapped(f"→ {question.answer}", width),
                (card.x + CARD_PADDING, code_top + len(question.statement) * CODE_PITCH + 12),
                Anchor.LEFT_TOP,
            )
        return frame
