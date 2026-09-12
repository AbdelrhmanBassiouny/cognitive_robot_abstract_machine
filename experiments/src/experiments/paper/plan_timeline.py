"""
What the robot was running while the events of a trial were being reported.

The chart that turns an event into an answer about agency. Read under the event chart,
an item of the plan standing beneath a reported event says the robot brought it about;
an event with no item beneath it says something else did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from segmind.datastructures.events import DetectionEvent
from typing_extensions import Optional, Sequence, Tuple

from experiments.episodes.episode import RecordedTrial
from experiments.paper.chart import ChartRow, RenderedChart, TimelineSpan, TrialChart
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.run_plan import ObjectIdentity, PlanItem, RunPlan, SameName
from semantic_digital_twin.world_description.geometry import Color

# %% one row of the chart


@dataclass(frozen=True)
class PlanRow(ChartRow):
    """
    One item of the plan the trial ran, and the stretch of the trial it ran over.
    """

    item: PlanItem
    """
    The item this row is.
    """

    accounts_for_the_event: bool = False
    """
    Whether this is the item that brought the event the card is about about.
    """

    @property
    def label(self) -> str:
        """
        The item this row is, as it is written down the side of the chart.
        """
        return self.item.label

    @property
    def spans(self) -> Tuple[TimelineSpan, ...]:
        """
        The one stretch of the trial this item ran over.
        """
        return (TimelineSpan(start=self.item.start, duration=self.item.duration),)

    @property
    def color(self) -> Color:
        """
        What this row's stretch is drawn in: the answer's own colour where the item
        accounts for the event, and otherwise the colour the statechart already gives
        the state the item was left in.
        """
        if self.accounts_for_the_event:
            return ANSWER_COLOR
        return self.item.status.color


# %% the chart that comes out


@dataclass
class RenderedPlanTimeline(RenderedChart):
    """
    One drawn chart of the plan a trial ran, and the rows it was drawn from.
    """

    rows: Tuple[PlanRow, ...]
    """
    One row per item of the plan, in the order they started.
    """


# %% the chart itself


@dataclass
class PlanTimeline:
    """
    Draws what the robot was running while one trial ran.
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
        identity: ObjectIdentity = SameName(),
    ) -> RenderedPlanTimeline:
        """
        Draw the plan one trial ran, with the moment a query was asked marked on it.

        :param trial: The trial whose plan is drawn.
        :param mark: Seconds into the trial the query was asked, or None to mark
            nothing.
        :param emphasise: The events the query answered, whose accounting items are
            picked out. An event no item of the plan accounts for picks out nothing.
        :param identity: How a body an item acts on is told to be the body an event is
            about.
        :raises TrialRanNoPlanError: If the trial recorded no plan.
        """
        rows = self.rows_of(RunPlan.of(trial, identity=identity), emphasise)
        return RenderedPlanTimeline(
            rows=rows,
            mark=mark,
            figure=self.chart.drawn(rows, mark, trial.duration),
        )

    # %% reading the rows off the plan

    @staticmethod
    def rows_of(
        plan: RunPlan, emphasise: Sequence[DetectionEvent]
    ) -> Tuple[PlanRow, ...]:
        """
        One row per item of the plan, in the order they started.

        :param plan: The plan the trial ran.
        :param emphasise: The events whose accounting items are picked out.
        """
        accounting = [plan.accounts_for(event) for event in emphasise]
        return tuple(
            PlanRow(item=item, accounts_for_the_event=item in accounting)
            for item in plan.items
        )
