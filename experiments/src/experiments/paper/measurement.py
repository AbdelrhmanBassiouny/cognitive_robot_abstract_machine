"""
What a paper figure's rows are built out of: a quantity read from repeated measurements,
and the knowledge sources the run it was measured over kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from typing_extensions import Sequence, Tuple

from experiments.episodes.episode import Episode
from experiments.experiment_definitions import (
    DEFAULT_CONFIDENCE_LEVEL,
    ConfidenceInterval,
    ExperimentResult,
    MeanAndStandardDeviation,
    Unit,
)

# %% a quantity and how far its measurements pin it down


@dataclass
class MeasuredQuantity(ExperimentResult):
    """
    What a set of measurements says about the quantity they measure.

    Reported within a row rather than as a row of its own, so every figure of the paper
    presents a measured number the same way: how many measurements it rests on, its
    average and spread, and the interval that average lies in.
    """

    measurement_count: int
    """
    How many measurements the quantity was read from.
    """

    average: MeanAndStandardDeviation
    """
    The quantity's average, and how far the measurements spread around it.
    """

    confidence_interval: ConfidenceInterval
    """
    The interval the average lies in.
    """

    @classmethod
    def from_measurements(
        cls,
        measurements: Sequence[float],
        unit: Unit = Unit.NONE,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    ) -> MeasuredQuantity:
        """
        Summarize the given measurements as the quantity they measure.

        :param measurements: The measurements taken.
        :param unit: The unit they are expressed in.
        :param confidence_level: Two-sided confidence level the interval holds at.
        :raises NoMeasurementsError: If no measurement was taken, since a quantity read
            from nothing is undefined rather than zero.
        """
        measurements = list(measurements)
        return cls(
            measurement_count=len(measurements),
            average=MeanAndStandardDeviation.from_measurements(measurements, unit=unit),
            confidence_interval=ConfidenceInterval.for_mean(
                measurements, confidence_level=confidence_level
            ),
        )


# %% the knowledge sources one run kept


class ConditionLabel(StrEnum):
    """
    The fixed text a cell naming a run's knowledge sources is written from.
    """

    SEPARATOR = " + "
    UNABLATED = "none"


@dataclass(frozen=True, order=True)
class RunConditions:
    """
    The knowledge sources one run switched off, which its trials are grouped by.

    Ordered so that the run keeping everything comes first and the ablations follow it
    alphabetically, which is the order the ablation tables are read in.
    """

    condition_names: Tuple[str, ...]
    """
    Each condition applied to every trial of the run, named as its class is.
    """

    def __str__(self) -> str:
        if not self.condition_names:
            return ConditionLabel.UNABLATED.value
        return ConditionLabel.SEPARATOR.value.join(self.condition_names)

    @classmethod
    def of(cls, episode: Episode) -> RunConditions:
        """
        The conditions the given run was made under.

        :param episode: The run whose conditions are wanted.
        """
        return cls(condition_names=tuple(episode.condition_names))
