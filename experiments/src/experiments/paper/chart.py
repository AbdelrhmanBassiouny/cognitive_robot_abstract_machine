"""
A chart of stretches laid down the seconds of one trial.

What the two charts of a card have in common. Whether a row is a kind of event the
monitor reported or one item of the plan the robot ran, it is drawn the same way: a
label down the side, its stretches as bars, and a rule where the query was asked. Kept
here so the two read against each other on the page rather than only happening to look
alike.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from typing_extensions import Optional, Sequence, Tuple

from experiments.paper.panel import CardPanel
from semantic_digital_twin.world_description.geometry import Color

# %% the colour every chart marks the query's own moment in

ASKED_COLOR = Color(0.85, 0.16, 0.22, 1.0)
"""
What the rule standing at the moment the query was asked is drawn in.
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
    How tall the chart is drawn at its shortest, so a trial with one row still has room
    for its axis.
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

    def drawn(self, rows: Sequence[ChartRow], mark: Optional[float]) -> Figure:
        """
        The chart these rows are drawn as.

        :param rows: The rows to draw, top to bottom in the order they are given.
        :param mark: Seconds into the trial the rule stands at, or None for no rule.
        """
        figure = Figure(
            figsize=(self.width_in_inches, self._height_of(rows)),
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

    def _height_of(self, rows: Sequence[ChartRow]) -> float:
        """
        How tall a chart of these rows is drawn, in inches.

        :param rows: The rows it draws.
        """
        return max(self.minimum_height_in_inches, len(rows) * self.row_height_in_inches)
