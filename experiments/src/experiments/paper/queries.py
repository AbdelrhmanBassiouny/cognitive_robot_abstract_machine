"""
What the queries asked while the trials ran said: which backend answered each predicate
and how long that took, and whether a repeated question came back with the same answer.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from typing_extensions import ClassVar, List, Sequence

from experiments.episodes.episode import RecordedQuery, RecordedTrial
from experiments.experiment_definitions import ExperimentResult, Unit
from experiments.paper.figure import FigureName, PaperFigure
from experiments.paper.measurement import MeasuredQuantity

MINIMUM_ASKINGS_TO_MEASURE_DETERMINISM = 2
"""
How often a question has to have been asked before its answers can disagree.

A question asked once always agrees with itself, so reporting it would fill a table
whose whole subject is disagreement across repetitions with rows of ones.
"""

# %% what each backend answered


@dataclass(frozen=True)
class RoutedPredicate:
    """
    One predicate of one query, and what answering it cost.
    """

    backend_name: str
    """
    The backend the predicate was routed to, named as its class is.
    """

    query_latency: float
    """
    Seconds the query carrying it took to answer.
    """

    @classmethod
    def of(cls, query: RecordedQuery) -> List[RoutedPredicate]:
        """
        Every predicate one query routed, with what that query cost.

        :param query: The query as it was recorded.
        """
        return [
            cls(backend_name=answered.backend_name, query_latency=query.latency)
            for answered in query.answered_predicates
        ]


@dataclass
class BackendLatency(ExperimentResult):
    """
    What one backend answered, and how long the queries carrying it took.
    """

    backend_name: str
    """
    The backend, named as its class is.
    """

    query_latency: MeasuredQuantity
    """
    How long the queries that routed a predicate here took, one measurement per
    predicate, so the count is how much of the paper's queries this backend carried.
    """


@dataclass
class QueryLatencyByBackend(PaperFigure):
    """
    How the paper's queries were decomposed across the backends that answered them.
    """

    name: ClassVar[FigureName] = FigureName.QUERY_LATENCY_BY_BACKEND
    caption: ClassVar[str] = (
        "Predicates each backend answered and how long the queries carrying them took, "
        "with the interval the average latency lies in. One measurement per predicate, "
        "so a query decomposed across two backends is counted against both."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per backend that answered a predicate, named alphabetically.

        :param trials: Every trial the tables are computed over.
        """
        routed = [
            predicate
            for query in self.queries_of(trials)
            for predicate in RoutedPredicate.of(query)
        ]
        by_backend = self.group_by(routed, key=lambda each: each.backend_name)
        return sorted(
            (
                BackendLatency(
                    backend_name=backend_name,
                    query_latency=self.measured(
                        [each.query_latency for each in answered_here],
                        unit=Unit.SECONDS,
                    ),
                )
                for backend_name, answered_here in by_backend.items()
            ),
            key=lambda row: row.backend_name,
        )


# %% whether a repeated question agreed with itself


@dataclass
class QueryAgreement(ExperimentResult):
    """
    How often one question, asked repeatedly, came back with the same answer.
    """

    query: str
    """
    The question, as it was asked.
    """

    agreement: MeasuredQuantity
    """
    The share of its askings that returned its most frequent answer.
    """


@dataclass
class QueryDeterminism(PaperFigure):
    """
    Whether the same question, asked again, is answered the same way.
    """

    name: ClassVar[FigureName] = FigureName.QUERY_DETERMINISM
    caption: ClassVar[str] = (
        "Share of a question's askings that returned its most frequent answer, over "
        "the questions asked more than once, with the interval that share lies in."
    )

    def rows(self, trials: Sequence[RecordedTrial]) -> List[ExperimentResult]:
        """
        One row per question asked more than once, in the order the questions read.

        :param trials: Every trial the tables are computed over.
        """
        by_query = self.group_by(self.queries_of(trials), key=lambda query: query.text)
        rows: List[ExperimentResult] = []
        for text, askings in by_query.items():
            if len(askings) < MINIMUM_ASKINGS_TO_MEASURE_DETERMINISM:
                continue
            most_frequent = statistics.mode(asking.answer for asking in askings)
            rows.append(
                QueryAgreement(
                    query=text,
                    agreement=self.measured(
                        self.indicators(
                            askings, lambda asking: asking.answer == most_frequent
                        )
                    ),
                )
            )
        return sorted(rows, key=lambda row: row.query)
