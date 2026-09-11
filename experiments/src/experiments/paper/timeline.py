"""
When each kind of event was reported while a trial ran, and where in that a query was
asked.

The second panel of a query card. A picture of the scene says what an answer names; this
says when, so a question about something that happened is read against the run it
happened in rather than against a moment the reader has to take on trust.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from segmind.datastructures.events import DetectionEvent
from typing_extensions import Dict, List, Optional, Sequence, Tuple, Type

from experiments.episodes.episode import RecordedTrial, Tick
from semantic_digital_twin.world_description.geometry import Color

# %% the colours a chart tells its rows apart in

REPORTED_COLOR = Color(0.62, 0.66, 0.72, 1.0)
"""
What a stretch of the trial an event was reported over is drawn in.
"""

ANSWERED_COLOR = Color(1.0, 0.78, 0.06, 1.0)
"""
What the row of the event a query answered is drawn in, which is the colour the scene
picks that answer out in.
"""

ASKED_COLOR = Color(0.85, 0.16, 0.22, 1.0)
"""
What the rule standing at the moment the query was asked is drawn in.
"""

# %% one row of the chart


@dataclass(frozen=True)
class TimelineSpan:
    """
    One stretch of a trial over which some kind of event was being reported.
    """

    start: float
    """
    Seconds between the start of the trial and the beginning of this stretch.
    """

    duration: float
    """
    How long the stretch lasts, in seconds.
    """


@dataclass(frozen=True)
class TimelineRow:
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
        return ANSWERED_COLOR if self.emphasised else REPORTED_COLOR


# %% the chart that comes out


@dataclass
class RenderedTimeline:
    """
    One drawn chart of a trial's events, and the rows it was drawn from.
    """

    rows: Tuple[TimelineRow, ...]
    """
    One row per kind of event the trial reported, in the order they were first seen.
    """

    mark: Optional[float]
    """
    Seconds between the start of the trial and the moment the rule stands at, or None
    where the chart is shown beside no query.
    """

    figure: Figure
    """
    The drawn chart itself.
    """

    def write(self, path: Path) -> Path:
        """
        Leave this chart at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self.figure.savefig(path, bbox_inches="tight")
        return path


# %% the chart itself


@dataclass
class EventTimeline:
    """
    Draws when each kind of event was reported while one trial ran.

    A row is a kind of event rather than one event: a monitor reports the same thing on
    every tick it still holds, so drawing one bar per report is drawing the stretch the
    event lasted.
    """

    bar_thickness: float = 0.4
    """
    How much of a row's own height its bar takes up, leaving the rest as the gap between
    rows.
    """

    row_height_in_inches: float = 0.4
    """
    How tall one row is drawn.
    """

    width_in_inches: float = 7.0
    """
    How wide the chart is drawn.
    """

    minimum_height_in_inches: float = 1.2
    """
    How tall the chart is drawn at its shortest, so a trial reporting one kind of event
    still has room for its axis.
    """

    rule_width: float = 1.5
    """
    Thickness of the rule standing at the moment the query was asked, in points.
    """

    resolution: int = 200
    """
    How many pixels to the inch the chart is written at.
    """

    time_axis_label: str = "seconds into the trial"
    """
    What is written under the chart's horizontal axis.
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
        rows = self._rows_of(trial, emphasise)
        return RenderedTimeline(rows=rows, mark=mark, figure=self._drawn(rows, mark))

    # %% reading the rows off the trial

    def _rows_of(
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

    # %% drawing them

    def _drawn(self, rows: Sequence[TimelineRow], mark: Optional[float]) -> Figure:
        """
        The chart these rows are drawn as.

        :param rows: The rows to draw, top to bottom in the order they are given.
        :param mark: Seconds into the trial the rule stands at, or None for no rule.
        """
        figure = Figure(
            figsize=(
                self.width_in_inches,
                max(
                    self.minimum_height_in_inches,
                    len(rows) * self.row_height_in_inches,
                ),
            ),
            dpi=self.resolution,
        )
        FigureCanvasAgg(figure)
        axes = figure.add_subplot()
        for place, row in enumerate(rows):
            axes.broken_barh(
                [(span.start, span.duration) for span in row.spans],
                (place - self.bar_thickness / 2.0, self.bar_thickness),
                facecolors=row.color.to_hex(),
            )
        if mark is not None:
            axes.axvline(mark, color=ASKED_COLOR.to_hex(), linewidth=self.rule_width)
        axes.set_yticks(range(len(rows)))
        axes.set_yticklabels([row.label for row in rows])
        axes.set_ylim(-1.0, max(len(rows), 1))
        axes.invert_yaxis()
        axes.set_xlabel(self.time_axis_label)
        return figure
