"""
When each kind of event was reported while a trial ran, and where in that a query was
asked.

One of the charts of a query card. A picture of the scene says what an answer names;
this says when, so a question about something that happened is read against the run it
happened in rather than against a moment the reader has to take on trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from segmind.datastructures.events import DetectionEvent
from typing_extensions import Dict, List, Optional, Sequence, Tuple, Type

from experiments.episodes.episode import RecordedTrial, Tick
from experiments.paper.chart import ChartRow, RenderedChart, TimelineSpan, TrialChart
from experiments.paper.panel import ANSWER_COLOR
from semantic_digital_twin.world_description.geometry import Color

# %% the colours a chart tells its rows apart in

REPORTED_COLOR = Color(0.62, 0.66, 0.72, 1.0)
"""
What a stretch of the trial an event was reported over is drawn in.
"""

# %% one row of the chart


@dataclass(frozen=True)
class TimelineRow(ChartRow):
    """
    One kind of event, and every stretch of the trial it was reported over.
    """

    event_type: Type[DetectionEvent]
    """
    The kind of event this row is.
    """

    spans: Tuple[TimelineSpan, ...] = ()
    """
    The stretches it was reported over, in the order the ticks reported them.
    """

    emphasised: bool = False
    """
    Whether this is the row of the event the query being shown answered.
    """

    @property
    def label(self) -> str:
        """
        The kind of event this row is, as it is written down the side of the chart.
        """
        return self.event_type.__name__

    @property
    def color(self) -> Color:
        """
        What this row's stretches are drawn in.
        """
        return ANSWER_COLOR if self.emphasised else REPORTED_COLOR


# %% the chart that comes out


@dataclass
class RenderedTimeline(RenderedChart):
    """
    One drawn chart of a trial's events, and the rows it was drawn from.
    """

    rows: Tuple[TimelineRow, ...]
    """
    One row per kind of event the trial reported, in the order they were first seen.
    """


# %% the chart itself


@dataclass
class EventTimeline:
    """
    Draws when each kind of event was reported while one trial ran.

    A row is a kind of event rather than one event: a monitor reports the same thing on
    every tick it still holds, so drawing one bar per report is drawing the stretch the
    event lasted.
    """

    chart: TrialChart = field(default_factory=TrialChart)
    """
    How the rows are drawn.
    """

    def of(
        self,
        trial: RecordedTrial,
        mark: Optional[float] = None,
        emphasise: Sequence[DetectionEvent] = (),
    ) -> RenderedTimeline:
        """
        Draw one trial's events, with the moment a query was asked marked on them.

        :param trial: The trial whose monitor's ticks are drawn.
        :param mark: Seconds into the trial the query was asked, or None to mark
            nothing.
        :param emphasise: The events the query answered, whose rows are picked out. An
            event of a kind the trial never reported has no row and picks out nothing.
        """
        rows = self.rows_of(trial, emphasise)
        return RenderedTimeline(
            rows=rows,
            mark=mark,
            figure=self.chart.drawn(rows, mark, trial.duration),
        )

    # %% reading the rows off the trial

    def rows_of(
        self, trial: RecordedTrial, emphasise: Sequence[DetectionEvent]
    ) -> Tuple[TimelineRow, ...]:
        """
        One row per kind of event the trial reported, in the order they were first seen.

        :param trial: The trial to read.
        :param emphasise: The events whose rows are picked out.
        """
        answered = {type(event) for event in emphasise}
        spans: Dict[Type[DetectionEvent], List[TimelineSpan]] = {}
        for tick, span in self._spans_of(trial):
            for event in tick.events:
                spans.setdefault(type(event), []).append(span)
        return tuple(
            TimelineRow(
                event_type=event_type,
                spans=tuple(reported),
                emphasised=event_type in answered,
            )
            for event_type, reported in spans.items()
        )

    @staticmethod
    def _spans_of(trial: RecordedTrial) -> List[Tuple[Tick, TimelineSpan]]:
        """
        The stretch of the trial each of its ticks stands for.

        A tick says what was seen at one moment, so it stands for the stretch up to the
        next tick; the last tick stands for the rest of the trial.

        :param trial: The trial to read.
        """
        ends = [tick.moment for tick in trial.ticks[1:]] + [trial.duration]
        return [
            (tick, TimelineSpan(start=tick.moment, duration=end - tick.moment))
            for tick, end in zip(trial.ticks, ends)
        ]
