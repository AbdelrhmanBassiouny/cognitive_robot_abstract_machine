"""
What one table of the paper is: rows read off the trials the runs recorded, rendered as
a captioned table and written beside the rows it was computed from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from typing_extensions import (
    Callable,
    ClassVar,
    Dict,
    Hashable,
    List,
    Sequence,
    TypeVar,
)

from experiments.episodes.episode import InsertionAttempt, RecordedQuery, RecordedTrial
from experiments.experiment_definitions import (
    DEFAULT_CONFIDENCE_LEVEL,
    ExperimentResult,
    ExperimentsTable,
    TypstRenderer,
    Unit,
)
from experiments.paper.measurement import MeasuredQuantity

GroupedItem = TypeVar("GroupedItem")
"""
What a figure groups before measuring each group: a trial, an attempt or a query.
"""

GroupKey = TypeVar("GroupKey", bound=Hashable)
"""
What one group of a figure's rows is gathered under, and what that row reports.
"""

# %% which table of the paper a figure is


class FigureName(StrEnum):
    """
    Every table the paper prints, named by what it reports.

    A member's value is the stem of the files it is written to, so the paper and the
    script that regenerates it name a table once.
    """

    TRIAL_OUTCOME_BY_CONDITION = "trial_outcome_by_condition"
    FAILURE_TYPE_BY_CONDITION = "failure_type_by_condition"
    FAILURE_PREDICTION = "failure_prediction"
    QUERY_LATENCY_BY_BACKEND = "query_latency_by_backend"
    QUERY_DETERMINISM = "query_determinism"
    TRIAL_OUTCOME_BY_EXECUTION_TYPE = "trial_outcome_by_execution_type"


class FigureFile(StrEnum):
    """
    The suffix each of the two files a figure is written to carries.
    """

    TYPST_TABLE = ".typ"
    ROW_MANIFEST = ".json"


@dataclass(frozen=True)
class WrittenFigure:
    """
    Where one figure's table, and the rows behind it, were left.
    """

    figure: FigureName
    """
    The table that was written.
    """

    table_path: Path
    """
    The Typst markup the paper includes.
    """

    row_manifest_path: Path
    """
    The rows the table presents, so a number in the paper is traceable to them.
    """


# %% the figure itself


@dataclass
class PaperFigure(ABC):
    """
    One table the paper prints, computed from what the runs recorded.

    A figure reads its rows off recorded trials rather than off a database, so the same
    figure is computed from a corpus recalled from long-term memory and from the trials
    a run is still holding.
    """

    name: ClassVar[FigureName]
    """
    Which table of the paper this figure is.
    """

    caption: ClassVar[str]
    """
    What the table shows, as the paper's reader is told it.
    """

    confidence_level: float = field(default=DEFAULT_CONFIDENCE_LEVEL)
    """
    Two-sided confidence level every interval in this table holds at.
    """

    @abstractmethod
    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        Read this table's rows off the given trials, in the order they are read in.

        :param trials: Every trial the tables are computed over.
        """

    def table(self, trials: Sequence[RecordedTrial]) -> ExperimentsTable:
        """
        This table's rows, ready to be presented.

        :param trials: Every trial the tables are computed over.
        """
        return ExperimentsTable(self.rows(trials))

    def render(self, trials: Sequence[RecordedTrial]) -> str:
        """
        This table as captioned Typst markup.

        :param trials: Every trial the tables are computed over.
        """
        return TypstRenderer(self.table(trials)).render_figure(self.caption)

    def file_name(self, figure_file: FigureFile) -> str:
        """
        What one of this figure's two files is called.

        :param figure_file: Which of them is wanted.
        """
        return "%s%s" % (self.name.value, figure_file.value)

    def write(
        self, trials: Sequence[RecordedTrial], output_directory: Path
    ) -> WrittenFigure:
        """
        Leave this table and the rows it presents in the given directory.

        :param trials: Every trial the tables are computed over.
        :param output_directory: Where the two files go, created if it is not there.
        :return: Where each of them was left.
        """
        output_directory.mkdir(parents=True, exist_ok=True)
        table = self.table(trials)
        table_path = output_directory / self.file_name(FigureFile.TYPST_TABLE)
        table_path.write_text(TypstRenderer(table).render_figure(self.caption))
        return WrittenFigure(
            figure=self.name,
            table_path=table_path,
            row_manifest_path=table.write_manifest(
                output_directory, self.file_name(FigureFile.ROW_MANIFEST)
            ),
        )

    # %% what a figure reaches for in the trials it is given

    def measured(
        self, measurements: Sequence[float], unit: Unit = Unit.NONE
    ) -> MeasuredQuantity:
        """
        Summarize the given measurements at this figure's own confidence level.

        :param measurements: The measurements one row reports.
        :param unit: The unit they are expressed in.
        """
        return MeasuredQuantity.from_measurements(
            measurements, unit=unit, confidence_level=self.confidence_level
        )

    @staticmethod
    def group_by(
        items: Sequence[GroupedItem], key: Callable[[GroupedItem], GroupKey]
    ) -> Dict[GroupKey, List[GroupedItem]]:
        """
        Gather the given items under what each of them is reported by.

        :param items: The trials, attempts or queries to gather.
        :param key: What each of them is reported under.
        :return: The items of each group, in the order they were first seen.
        """
        groups: Dict[GroupKey, List[GroupedItem]] = {}
        for item in items:
            groups.setdefault(key(item), []).append(item)
        return groups

    @staticmethod
    def attempts_of(trials: Sequence[RecordedTrial]) -> List[InsertionAttempt]:
        """
        Every insertion attempted while the given trials ran.

        :param trials: The trials to read.
        """
        return [attempt for trial in trials for attempt in trial.insertion_attempts]

    @staticmethod
    def queries_of(trials: Sequence[RecordedTrial]) -> List[RecordedQuery]:
        """
        Every query asked while the given trials ran.

        :param trials: The trials to read.
        """
        return [query for trial in trials for query in trial.queries]

    @staticmethod
    def indicators(
        items: Sequence[GroupedItem], holds: Callable[[GroupedItem], bool]
    ) -> List[float]:
        """
        One measurement per item, being whether the given statement holds of it.

        A rate is the average of these, which is what lets a rate be summarized and
        given an interval by the same code an ordinary measured quantity is.

        :param items: The items the statement is asked of.
        :param holds: The statement.
        """
        return [float(holds(item)) for item in items]
