"""
What the monitor reported, drawn over what the robot was running, on one time axis.

The chart that turns an event into an answer about agency. Drawn as two charts stacked
in one figure rather than two figures, so a second is in exactly the same place on both
and a reader reads straight down from a reported event to the item of the plan that was
running under it -- or to the empty stretch of plan that says nothing was.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from matplotlib.patches import Patch
from segmind.datastructures.events import DetectionEvent
from typing_extensions import List, Optional, Sequence, Tuple

from experiments.episodes.episode import RecordedTrial
from experiments.paper.chart import (
    ASKED_COLOR,
    MarkedMoment,
    RenderedChart,
    Side,
    TimelineSpan,
    TrialChart,
)
from experiments.paper.panel import ANSWER_COLOR
from experiments.paper.plan_timeline import PlanRow, PlanTimeline
from experiments.paper.run_plan import ObjectIdentity, RunPlan, SameName, plans_of
from experiments.paper.timeline import REPORTED_COLOR, EventTimeline, TimelineRow
from giskardpy.motion_statechart.data_types import LifeCycleValues

# %% what the two charts are called on the figure

REPORTED_TITLE = "what the monitor reported"
"""
What is written over the chart of events.
"""

RUNNING_TITLE = "what the robot was running"
"""
What is written over the chart of the plan.
"""

PICTURES_TAKEN_AT = "pictures below taken at %s"
"""
What is written under the charts to say which instants the levels below show, given
those instants written out.
"""

INSTANT = "%.1f s"
"""
How one instant is written.
"""

REPORTED_LEGEND = "reported"
"""
What a stretch an event was reported over is called in the key.
"""

ANSWER_LEGEND = "the event the answer is about, and the item accounting for it"
"""
What the answer's own colour is called in the key.
"""

# %% the chart that comes out


@dataclass
class RenderedRunTimeline(RenderedChart):
    """
    One drawn figure of a trial's events over its plan, and the rows of each.
    """

    reported: Tuple[TimelineRow, ...]
    """
    One row per kind of event the trial reported.
    """

    ran: Tuple[PlanRow, ...]
    """
    One row per item of the plan, or none where the trial recorded no plan.
    """


# %% the chart itself


@dataclass
class RunTimeline:
    """
    Draws what the monitor reported over what the robot was running, as one figure.
    """

    chart: TrialChart = field(default_factory=TrialChart)
    """
    How the rows of both charts are drawn.
    """

    title_size: float = 9.0
    """
    Size of the writing over each chart, in points.
    """

    def of(
        self,
        trial: RecordedTrial,
        asked_at: Optional[float] = None,
        emphasise: Sequence[DetectionEvent] = (),
        happened_at: Optional[float] = None,
        pictured_at: Sequence[float] = (),
        identity: ObjectIdentity = SameName(),
    ) -> RenderedRunTimeline:
        """
        Draw one trial's events over the plan it ran.

        :param trial: The trial to draw.
        :param asked_at: Seconds into the trial the query was asked, or None to mark no
            query.
        :param emphasise: The events the query answered, whose rows and accounting items
            are picked out.
        :param happened_at: Seconds into the trial the answered event was reported, or
            None to mark no event.
        :param pictured_at: The instants the other levels of the same card show, in
            seconds into the trial; the stretch between the first and the last is shaded
            and the instants written under the charts, so a reader can find each picture
            on the axis.
        :param identity: How a body an item of the plan acts on is told to be the body
            an event is about.
        """
        reported = EventTimeline(chart=self.chart).rows_of(trial, emphasise)
        ran = self._plan_rows_of(trial, emphasise, identity)
        figure = self.chart.figure_of(
            self.chart.height_of(reported) + self.chart.height_of(ran) + 1.0
        )
        upper, lower = figure.subplots(
            2,
            1,
            sharex=True,
            gridspec_kw={
                "height_ratios": [max(len(reported), 1), max(len(ran), 1)],
                "hspace": 0.35,
            },
        )
        self.chart.draw_rows(upper, reported, trial.duration)
        self.chart.draw_rows(lower, ran, trial.duration)
        upper.set_title(REPORTED_TITLE, loc="left", fontsize=self.title_size)
        lower.set_title(RUNNING_TITLE, loc="left", fontsize=self.title_size)
        lower.set_xlabel(self._axis_label(pictured_at), fontsize=self.chart.label_size)
        marks = self._marks(asked_at, happened_at)
        for axes in (upper, lower):
            for marked in marks:
                self.chart.draw_rule(
                    axes,
                    (
                        marked
                        if axes is upper
                        else MarkedMoment(marked.moment, "", marked.color)
                    ),
                )
            if pictured_at:
                self.chart.shade(
                    axes,
                    TimelineSpan(min(pictured_at), max(pictured_at) - min(pictured_at)),
                )
        self._key(figure, ran)
        figure.subplots_adjust(left=0.30, right=0.98, top=0.90, bottom=0.22)
        return RenderedRunTimeline(
            mark=asked_at, figure=figure, reported=reported, ran=ran
        )

    def _axis_label(self, pictured_at: Sequence[float]) -> str:
        """
        What is written under the lower chart: the seconds, and the instants the
        pictures below were taken at where there are any.

        :param pictured_at: The instants, in seconds into the trial.
        """
        if not pictured_at:
            return self.chart.time_axis_label
        instants = ", ".join(INSTANT % moment for moment in sorted(set(pictured_at)))
        return "%s; %s" % (self.chart.time_axis_label, PICTURES_TAKEN_AT % instants)

    @staticmethod
    def _plan_rows_of(
        trial: RecordedTrial,
        emphasise: Sequence[DetectionEvent],
        identity: ObjectIdentity,
    ) -> Tuple[PlanRow, ...]:
        """
        One row per item of the plan the trial ran, or none where it recorded no plan.

        :param trial: The trial to read.
        :param emphasise: The events whose accounting items are picked out.
        :param identity: How a body an item acts on is told to be the body an event is
            about.
        """
        if not plans_of(trial):
            return ()
        return PlanTimeline.rows_of(RunPlan.of(trial, identity=identity), emphasise)

    @staticmethod
    def _marks(
        asked_at: Optional[float], happened_at: Optional[float]
    ) -> List[MarkedMoment]:
        """
        The moments both charts draw a rule at: when the answered event was reported,
        and when the query was asked. Where there are two, the earlier is named on the
        left of its rule and the later on the right, so the two names never run into one
        another however close the rules stand.

        :param asked_at: Seconds into the trial the query was asked, or None.
        :param happened_at: Seconds into the trial the event was reported, or None.
        """
        marks = []
        if happened_at is not None:
            marks.append(
                MarkedMoment(
                    happened_at, "reported at %.1f s" % happened_at, ANSWER_COLOR
                )
            )
        if asked_at is not None:
            marks.append(
                MarkedMoment(asked_at, "asked at %.1f s" % asked_at, ASKED_COLOR)
            )
        if len(marks) < 2:
            return marks
        earlier, later = sorted(marks, key=lambda mark: mark.moment)
        return [
            MarkedMoment(earlier.moment, earlier.label, earlier.color, Side.LEFT),
            MarkedMoment(later.moment, later.label, later.color, Side.RIGHT),
        ]

    def _key(self, figure, ran: Sequence[PlanRow]) -> None:
        """
        Write under the charts what each colour means: the reported stretches, the
        answer's own colour, and every state the plan's items were left in.

        :param figure: The figure to write on.
        :param ran: The plan's rows, whose states the key names.
        """
        handles = [
            Patch(facecolor=REPORTED_COLOR.to_hex(), label=REPORTED_LEGEND),
            Patch(facecolor=ANSWER_COLOR.to_hex(), label=ANSWER_LEGEND),
        ]
        states: List[LifeCycleValues] = []
        for row in ran:
            if row.accounts_for_the_event or row.item.status in states:
                continue
            states.append(row.item.status)
        handles.extend(
            Patch(facecolor=state.color.to_hex(), label=state.name.lower())
            for state in states
        )
        figure.legend(
            handles=handles,
            loc="lower center",
            ncol=len(handles),
            fontsize=self.chart.label_size,
            frameon=False,
        )
