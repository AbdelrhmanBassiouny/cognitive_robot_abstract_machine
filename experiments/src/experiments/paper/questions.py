"""
Whether the frozen question set's answers matched ground truth, reported per bucket and
per level of Bloom's taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import ClassVar, List, Sequence

from experiments.episodes.episode import RecordedTrial
from experiments.experiment_definitions import ExperimentResult
from experiments.paper.figure import FigureName, PaperFigure
from experiments.paper.measurement import MeasuredQuantity
from experiments.questions.question import BloomLevel, Bucket

# %% accuracy per bucket


@dataclass
class BucketAccuracy(ExperimentResult):
    """
    How often the frozen set's questions of one bucket were answered correctly.
    """

    bucket: Bucket
    """
    The kind of thing this row's questions ask about.
    """

    accuracy: MeasuredQuantity
    """
    The share of this bucket's askings that matched ground truth.
    """


@dataclass
class AccuracyByBucket(PaperFigure):
    """
    Whether the frozen question set was answered correctly, reported per bucket.
    """

    name: ClassVar[FigureName] = FigureName.ACCURACY_BY_BUCKET
    caption: ClassVar[str] = (
        "Share of the frozen question set's askings answered correctly, per bucket, "
        "with the interval that share lies in. An ordinary query that answers no "
        "question of the set carries no bucket and is not counted."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per bucket the given trials scored a question of, in bucket order.

        :param trials: Every trial the tables are computed over.
        """
        scored = self.scored_queries_of(trials)
        by_bucket = self.group_by(scored, key=lambda query: query.bucket)
        return [
            BucketAccuracy(
                bucket=bucket,
                accuracy=self.measured(
                    self.indicators(askings, lambda asking: asking.answered_correctly)
                ),
            )
            for bucket in Bucket
            if (askings := by_bucket.get(bucket))
        ]


# %% accuracy per level of Bloom's taxonomy


@dataclass
class BloomLevelAccuracy(ExperimentResult):
    """
    How often the frozen set's questions exercising one level of Bloom's taxonomy were
    answered correctly.
    """

    bloom_level: BloomLevel
    """
    The level of Bloom's taxonomy this row's questions exercise.
    """

    accuracy: MeasuredQuantity
    """
    The share of this level's askings that matched ground truth.
    """


@dataclass
class AccuracyByBloomLevel(PaperFigure):
    """
    Whether the frozen question set was answered correctly, reported per level of
    Bloom's taxonomy.
    """

    name: ClassVar[FigureName] = FigureName.ACCURACY_BY_BLOOM_LEVEL
    caption: ClassVar[str] = (
        "Share of the frozen question set's askings answered correctly, per level of "
        "Bloom's taxonomy, with the interval that share lies in. An ordinary query that "
        "answers no question of the set carries no level and is not counted."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per level the given trials scored a question of, in the taxonomy's own
        order.

        :param trials: Every trial the tables are computed over.
        """
        scored = self.scored_queries_of(trials)
        by_level = self.group_by(scored, key=lambda query: query.bloom_level)
        return [
            BloomLevelAccuracy(
                bloom_level=bloom_level,
                accuracy=self.measured(
                    self.indicators(askings, lambda asking: asking.answered_correctly)
                ),
            )
            for bloom_level in BloomLevel
            if (askings := by_level.get(bloom_level))
        ]
