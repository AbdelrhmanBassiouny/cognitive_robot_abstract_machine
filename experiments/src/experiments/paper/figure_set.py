"""
Every table the paper prints, and writing them all at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from krrood.exceptions import DataclassException
from typing_extensions import List, Sequence

from experiments.episodes.episode import RecordedTrial
from experiments.paper.figure import FigureName, PaperFigure, WrittenFigure
from experiments.paper.outcomes import (
    FailurePrediction,
    FailureTypeByCondition,
    TrialOutcomeByCondition,
    TrialOutcomeByExecutionType,
)
from experiments.paper.queries import QueryDeterminism, QueryLatencyByBackend

# %% asking for a table the paper does not print


@dataclass
class UnknownFigureError(DataclassException):
    """
    Raised when a figure is asked for that the set does not hold.
    """

    figure: FigureName
    """
    The table nothing was found for.
    """

    def error_message(self) -> str:
        return "The set holds no figure reporting %s." % self.figure.value

    def suggest_correction(self) -> str:
        return (
            "Add a PaperFigure for it to FigureSet.for_the_paper, which is where the "
            "tables the paper prints are listed."
        )


# %% the set itself


@dataclass
class FigureSet:
    """
    Every table the paper prints, regenerated together from one corpus of trials.
    """

    figures: List[PaperFigure] = field(default_factory=list)
    """
    The tables, in the order the script writes them.
    """

    @classmethod
    def for_the_paper(cls) -> FigureSet:
        """
        The set the paper's experiments section is written from.
        """
        return cls(
            figures=[
                TrialOutcomeByCondition(),
                FailureTypeByCondition(),
                FailurePrediction(),
                QueryLatencyByBackend(),
                QueryDeterminism(),
                TrialOutcomeByExecutionType(),
            ]
        )

    def figure_named(self, figure: FigureName) -> PaperFigure:
        """
        The one figure of this set reporting the given table.

        :param figure: The table wanted.
        :raises UnknownFigureError: If the set holds no figure reporting it.
        """
        for held in self.figures:
            if held.name is figure:
                return held
        raise UnknownFigureError(figure=figure)

    def write(
        self, trials: Sequence[RecordedTrial], output_directory: Path
    ) -> List[WrittenFigure]:
        """
        Leave every table of the paper, and the rows behind each, in one directory.

        :param trials: Every trial the tables are computed over.
        :param output_directory: Where the files go, created if it is not there.
        :return: Where each figure was left, in the order they were written.
        """
        return [figure.write(trials, output_directory) for figure in self.figures]
