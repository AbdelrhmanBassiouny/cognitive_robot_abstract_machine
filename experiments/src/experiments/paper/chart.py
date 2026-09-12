"""
A chart of stretches laid down the seconds of one trial.

What the charts of a card have in common. Whether a row is a kind of event the monitor
reported or one item of the plan the robot ran, it is drawn the same way: a label down
the side, its stretches as bars, and a rule where the query was asked. Kept here so the
charts read against each other on the page rather than only happening to look alike.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from typing_extensions import Optional, Sequence, Tuple

from experiments.paper.panel import CardPanel
from semantic_digital_twin.world_description.geometry import Color

# %% the colours every chart marks its moments in

ASKED_COLOR = Color(0.85, 0.16, 0.22, 1.0)
"""
What the rule standing at the moment the query was asked is drawn in.
"""

BAND_COLOR = Color(0.55, 0.60, 0.68, 0.18)
"""
What a stretch of the trial another level of the card shows is shaded in, so a reader
can find on the chart the seconds the camera frames were taken at.
"""

# %% one stretch of a trial


@dataclass(frozen=True)
class TimelineSpan:
    """
    One stretch of a trial, as the seconds it runs between.
    """

    start: float
    """
    Seconds between the start of the trial and the beginning of this stretch.
    """

    duration: float
    """
    How long the stretch lasts, in seconds.
    """

    @property
    def end(self) -> float:
        """
        Seconds between the start of the trial and the end of this stretch.
        """
        return self.start + self.duration


# %% one moment of a trial, marked on the chart


@dataclass(frozen=True)
class MarkedMoment:
    """
    One moment of the trial a chart draws a rule at and names.
    """

    moment: float
    """
    Seconds between the start of the trial and the moment.
    """

    label: str
    """
    What the moment is, written beside the rule.
    """

    color: Color
    """
    What the rule and its label are drawn in.
    """


# %% one row of a chart


@dataclass(frozen=True)
class ChartRow(ABC):
    """
    One labelled line of a chart, and the stretches of the trial drawn on it.
    """

    @property
    @abstractmethod
    def label(self) -> str:
        """
        What is written down the side of the chart for this row.
        """

    @property
    @abstractmethod
    def spans(self) -> Tuple[TimelineSpan, ...]:
        """
        The stretches of the trial drawn on this row.
        """

    @property
    @abstractmethod
    def color(self) -> Color:
        """
        What this row's stretches are drawn in.
        """


# %% the chart that comes out


@dataclass
class RenderedChart(CardPanel, ABC):
    """
    One drawn chart of a trial, and where the query it is shown beside falls in it.
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


# %% drawing one


@dataclass
class TrialChart:
    """
    Draws labelled rows of stretches down the seconds of one trial.
    """

    bar_thickness: float = 0.5
    """
    How much of a row's own height its bar takes up, leaving the rest as the gap between
    rows.
    """

    row_height_in_inches: float = 0.32
    """
    How tall one row is drawn.
    """

    width_in_inches: float = 8.0
    """
    How wide the chart is drawn.
    """

    minimum_height_in_inches: float = 1.2
    """
    How tall the chart is drawn at its shortest, so a trial with one row still has room
    for its axis.
    """

    rule_width: float = 1.4
    """
    Thickness of the rule standing at a marked moment, in points.
    """

    label_size: float = 8.0
    """
    Size of the writing down the side of the chart and beside its rules, in points.
    """

    resolution: int = 200
    """
    How many pixels to the inch the chart is written at.
    """

    time_axis_label: str = "seconds into the trial"
    """
    What is written under the chart's horizontal axis.
    """

    def drawn(
        self,
        rows: Sequence[ChartRow],
        mark: Optional[float],
        span: Optional[float] = None,
    ) -> Figure:
        """
        The chart these rows are drawn as, on their own.

        :param rows: The rows to draw, top to bottom in the order they are given.
        :param mark: Seconds into the trial the rule stands at, or None for no rule.
        :param span: How long the trial ran, in seconds. Given, the chart spans the
            whole of it rather than only what these rows happen to cover, so that a
            second falls in the same place on every chart of one trial.
        """
        figure = self.figure_of(self.height_of(rows))
        axes = figure.add_subplot()
        self.draw_rows(axes, rows, span)
        if mark is not None:
            self.draw_rule(axes, MarkedMoment(mark, "", ASKED_COLOR))
        axes.set_xlabel(self.time_axis_label, fontsize=self.label_size)
        return figure

    def figure_of(self, height_in_inches: float) -> Figure:
        """
        An empty figure of the chart's own width, drawn on a canvas that needs no
        window.

        :param height_in_inches: How tall it is.
        """
        figure = Figure(
            figsize=(self.width_in_inches, height_in_inches), dpi=self.resolution
        )
        FigureCanvasAgg(figure)
        return figure

    def height_of(self, rows: Sequence[ChartRow]) -> float:
        """
        How tall a chart of these rows is drawn, in inches.

        :param rows: The rows it draws.
        """
        return max(self.minimum_height_in_inches, len(rows) * self.row_height_in_inches)

    def draw_rows(
        self, axes: Axes, rows: Sequence[ChartRow], span: Optional[float]
    ) -> None:
        """
        Draw the rows into the given axes: their bars, their labels down the side, and
        the seconds along the bottom.

        :param axes: Where to draw.
        :param rows: The rows, top to bottom in the order they are given.
        :param span: How long the trial ran, in seconds, or None to span only what the
            rows cover.
        """
        for place, row in enumerate(rows):
            axes.broken_barh(
                [(stretch.start, stretch.duration) for stretch in row.spans],
                (place - self.bar_thickness / 2.0, self.bar_thickness),
                facecolors=row.color.to_hex(),
            )
        if span is not None:
            axes.set_xlim(0.0, span)
        axes.set_yticks(range(len(rows)))
        axes.set_yticklabels([row.label for row in rows], fontsize=self.label_size)
        axes.set_ylim(-0.75, max(len(rows), 1) - 0.25)
        axes.invert_yaxis()
        axes.tick_params(axis="x", labelsize=self.label_size)
        axes.grid(axis="x", color="0.85", linewidth=0.6)
        axes.set_axisbelow(True)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)

    def draw_rule(self, axes: Axes, marked: MarkedMoment) -> None:
        """
        Stand a rule at one moment of the trial, with its name written over the top of
        the chart where it is given one.

        :param axes: Where to draw.
        :param marked: The moment, and what to write above it, or nothing.
        """
        axes.axvline(
            marked.moment, color=marked.color.to_hex(), linewidth=self.rule_width
        )
        if not marked.label:
            return
        axes.annotate(
            marked.label,
            xy=(marked.moment, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(3, 1),
            textcoords="offset points",
            fontsize=self.label_size,
            color=marked.color.to_hex(),
            verticalalignment="bottom",
        )

    def shade(self, axes: Axes, stretch: TimelineSpan) -> None:
        """
        Shade one stretch of the trial.

        :param axes: Where to draw.
        :param stretch: The seconds to shade.
        """
        axes.axvspan(
            stretch.start,
            stretch.end,
            facecolor=BAND_COLOR.to_hex(),
            alpha=BAND_COLOR.A,
            linewidth=0,
        )
