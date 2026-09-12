"""
What the trials of one run measured, as the rows a scientific article prints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from typing_extensions import List, Protocol

from experiments.experiment_definitions import (
    DEFAULT_CONFIDENCE_LEVEL,
    ConfidenceInterval,
    ExperimentResult,
    ExperimentsTable,
    MeanAndStandardDeviation,
    TypstRenderer,
    Unit,
)
from experiments.scenarios.trial import TrialOutcome

# %% what a metric reads a trial for


class MeasuredTrial(Protocol):
    """
    What a metric reads off a finished trial.

    Declared rather than left to convention: a trial a run is still holding and a trial
    read back out of the database are different classes, and a metric measures either.
    """

    outcome: TrialOutcome
    """
    Whether the trial reached the scenario's goal.
    """

    duration: float
    """
    How long the trial took, in seconds.
    """


# %% one number read off a trial


@dataclass
class Metric(ABC):
    """
    One number read off a finished trial.
    """

    unit: Unit = Unit.NONE
    """
    The unit the number is expressed in.
    """

    @abstractmethod
    def measure(self, trial: MeasuredTrial) -> float:
        """
        Read this metric's number off the given trial.

        :param trial: A trial that has finished.
        """


@dataclass
class GoalReached(Metric):
    """
    Whether a trial reached its scenario's goal, so that its mean over the trials is the
    success rate of the run.
    """

    def measure(self, trial: MeasuredTrial) -> float:
        return float(trial.outcome is TrialOutcome.SUCCEEDED)


@dataclass
class TrialDuration(Metric):
    """
    How long a trial took.
    """

    unit: Unit = Unit.SECONDS

    def measure(self, trial: MeasuredTrial) -> float:
        return trial.duration


# %% what a metric measured over the trials


@dataclass
class MetricSummary(ExperimentResult):
    """
    One metric over the trials it was measured on, as one row of a report's table.
    """

    metric_name: str
    """
    The metric the row reports.
    """

    measurements: MeanAndStandardDeviation
    """
    What the metric measured, and how far the trials spread around it.
    """

    confidence_interval: ConfidenceInterval
    """
    The interval the mean lies in.
    """


@dataclass
class Report:
    """
    What the trials of one run measured, ready to be printed as a table.
    """

    scenario_name: str
    """
    The scenario the trials ran.
    """

    trials: List[MeasuredTrial]
    """
    The trials the metrics are measured over.
    """

    metrics: List[Metric] = field(default_factory=list)
    """
    One metric per row of the table.
    """

    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    """
    Two-sided confidence level every interval in the report holds at.
    """

    def summarize(self, metric: Metric) -> MetricSummary:
        """
        Measure one metric over every trial of this report.

        :param metric: The metric to measure.
        :raises NoMeasurementsError: If the report holds no trial.
        """
        measurements = [metric.measure(trial) for trial in self.trials]
        return MetricSummary(
            metric_name=type(metric).__name__,
            measurements=MeanAndStandardDeviation.from_measurements(
                measurements, unit=metric.unit
            ),
            confidence_interval=ConfidenceInterval.for_mean(
                measurements, confidence_level=self.confidence_level
            ),
        )

    def table(self) -> ExperimentsTable:
        """
        The report as a table of one row per metric.
        """
        return ExperimentsTable([self.summarize(metric) for metric in self.metrics])

    def render_figure(self, caption: str) -> str:
        """
        The report as a captioned table in Typst markup.

        :param caption: Caption text describing what the table shows.
        """
        return TypstRenderer(self.table()).render_figure(caption)
