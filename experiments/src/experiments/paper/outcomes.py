"""
What the trials themselves said: how often each ablation reached the goal, which
failures it produced, whether those failures were foreseen, and how the robot compared
with the simulator.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import StrEnum

from coraplex.datastructures.enums import ExecutionType
from typing_extensions import ClassVar, List, Sequence

from experiments.episodes.episode import FailureType, InsertionAttempt, RecordedTrial
from experiments.experiment_definitions import ExperimentResult
from experiments.paper.figure import FigureName, PaperFigure
from experiments.paper.measurement import MeasuredQuantity, RunConditions
from experiments.scenarios.report import GoalReached

# %% how often the goal was reached


@dataclass
class ConditionOutcome(ExperimentResult):
    """
    How often the trials of one ablation reached the scenario's goal.
    """

    conditions: RunConditions
    """
    The knowledge sources this row's run switched off.
    """

    goal_reached: MeasuredQuantity
    """
    The share of its trials that reached the goal.
    """


@dataclass
class ExecutionTypeOutcome(ExperimentResult):
    """
    How often the trials run in one place reached the scenario's goal.
    """

    execution_type: ExecutionType
    """
    Whether this row's trials ran in a simulator or on the robot.
    """

    goal_reached: MeasuredQuantity
    """
    The share of them that reached the goal.
    """


@dataclass
class TrialOutcomeFigure(PaperFigure, ABC):
    """
    A table of how often the trials of each group reached the goal.

    The share is measured with :class:`~experiments.scenarios.report.GoalReached`, the
    same metric a run's own report measures it with, so a table regenerated from the
    database says what the run said.
    """

    def goal_reached(self, trials: Sequence[RecordedTrial]) -> MeasuredQuantity:
        """
        The share of the given trials that reached the goal.

        :param trials: The trials of one row.
        """
        return self.measured([GoalReached().measure(trial) for trial in trials])


@dataclass
class TrialOutcomeByCondition(TrialOutcomeFigure):
    """
    What taking one knowledge source away did to the run.
    """

    name: ClassVar[FigureName] = FigureName.TRIAL_OUTCOME_BY_CONDITION
    caption: ClassVar[str] = (
        "Share of trials reaching the goal under each ablation, with the interval the "
        "share lies in. The unablated run is the row every other is read against."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per set of conditions, the unablated run first.

        :param trials: Every trial the tables are computed over.
        """
        by_conditions = self.group_by(
            trials, key=lambda trial: RunConditions.of(trial.episode)
        )
        return sorted(
            (
                ConditionOutcome(
                    conditions=conditions, goal_reached=self.goal_reached(of_condition)
                )
                for conditions, of_condition in by_conditions.items()
            ),
            key=lambda row: row.conditions,
        )


@dataclass
class TrialOutcomeByExecutionType(TrialOutcomeFigure):
    """
    What the same scenario reached on the robot and in the simulator.
    """

    name: ClassVar[FigureName] = FigureName.TRIAL_OUTCOME_BY_EXECUTION_TYPE
    caption: ClassVar[str] = (
        "Share of trials reaching the goal on the robot and in the simulator, with the "
        "interval the share lies in."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per place the trials ran, named alphabetically.

        :param trials: Every trial the tables are computed over.
        """
        by_execution_type = self.group_by(
            trials, key=lambda trial: trial.episode.execution_type
        )
        return sorted(
            (
                ExecutionTypeOutcome(
                    execution_type=execution_type,
                    goal_reached=self.goal_reached(of_execution_type),
                )
                for execution_type, of_execution_type in by_execution_type.items()
            ),
            key=lambda row: row.execution_type.name,
        )


# %% which failures each ablation produced


@dataclass
class FailureTypeShare(ExperimentResult):
    """
    How much of one ablation's attempts ended in one type of failure.
    """

    conditions: RunConditions
    """
    The knowledge sources this row's run switched off.
    """

    failure_type: FailureType
    """
    The failure the attempts were observed to end in.
    """

    share: MeasuredQuantity
    """
    The share of that run's attempts that ended in it.
    """


@dataclass
class FailureTypeByCondition(PaperFigure):
    """
    Which failures each ablation produced, as the stacked bars are drawn from.
    """

    name: ClassVar[FigureName] = FigureName.FAILURE_TYPE_BY_CONDITION
    caption: ClassVar[str] = (
        "Share of each ablation's insertion attempts ending in each observed failure "
        "type, over every attempt that ablation made rather than over its failures "
        "alone."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per failure type each set of conditions was observed to produce.

        :param trials: Every trial the tables are computed over.
        """
        rows: List[ExperimentResult] = []
        by_conditions = self.group_by(
            trials, key=lambda trial: RunConditions.of(trial.episode)
        )
        for conditions, of_condition in by_conditions.items():
            attempts = self.attempts_of(of_condition)
            for failure_type in self.observed_failures(attempts):
                rows.append(
                    FailureTypeShare(
                        conditions=conditions,
                        failure_type=failure_type,
                        share=self.measured(
                            self.indicators(
                                attempts,
                                lambda attempt: attempt.observed_failure
                                is failure_type,
                            )
                        ),
                    )
                )
        return sorted(rows, key=lambda row: (row.conditions, row.failure_type))

    @staticmethod
    def observed_failures(attempts: Sequence[InsertionAttempt]) -> List[FailureType]:
        """
        Every failure type the given attempts were observed to end in, without repeats.

        :param attempts: The attempts to read.
        """
        observed: List[FailureType] = []
        for attempt in attempts:
            if attempt.observed_failure is not None and (
                attempt.observed_failure not in observed
            ):
                observed.append(attempt.observed_failure)
        return observed


# %% whether a failure was foreseen


class PredictionScore(StrEnum):
    """
    Which side of a prediction's agreement with what happened one row reports.
    """

    PRECISION = "precision"
    RECALL = "recall"

    def attempts_scored(
        self, attempts: Sequence[InsertionAttempt]
    ) -> List[InsertionAttempt]:
        """
        The attempts this score is measured over.

        :param attempts: Every attempt recorded.
        """
        if self is PredictionScore.PRECISION:
            return [
                attempt for attempt in attempts if attempt.predicted_failure is not None
            ]
        return [attempt for attempt in attempts if attempt.observed_failure is not None]


@dataclass
class FailurePredictionScore(ExperimentResult):
    """
    How often a prediction and what happened agreed, on one of the two sides.
    """

    score: PredictionScore
    """
    Which attempts the agreement was measured over.
    """

    agreement: MeasuredQuantity
    """
    The share of them where the prediction named the failure that happened.
    """


@dataclass
class FailurePrediction(PaperFigure):
    """
    How well a failure was foreseen before the attempt that produced it ran.
    """

    name: ClassVar[FigureName] = FigureName.FAILURE_PREDICTION
    caption: ClassVar[str] = (
        "How often a predicted failure was the one that happened (precision) and how "
        "often a failure that happened had been predicted (recall), with the interval "
        "each share lies in."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per side of the agreement that had an attempt to measure it.

        A side measured over no attempt is left out rather than reported as zero, since
        a share of nothing is undefined and would read as a system that never foresaw
        anything.

        :param trials: Every trial the tables are computed over.
        """
        attempts = self.attempts_of(trials)
        rows: List[ExperimentResult] = []
        for score in PredictionScore:
            scored = score.attempts_scored(attempts)
            if not scored:
                continue
            rows.append(
                FailurePredictionScore(
                    score=score,
                    agreement=self.measured(
                        self.indicators(scored, self.foresaw_the_failure)
                    ),
                )
            )
        return rows

    @staticmethod
    def foresaw_the_failure(attempt: InsertionAttempt) -> bool:
        """
        Whether the attempt's prediction named the failure it was observed to end in.

        :param attempt: The attempt to score.
        """
        return (
            attempt.predicted_failure is not None
            and attempt.predicted_failure is attempt.observed_failure
        )
