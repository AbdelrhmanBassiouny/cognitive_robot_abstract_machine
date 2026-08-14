"""
Whether and where a Montessori run keeps the iterations it finishes.

Recording is best effort: a run whose database will not take a write sorts anyway and
says so, rather than losing a finished sort to a database problem. ``run_montessori_dem
o.sh``'s pre-flight is what still refuses to start a run whose database was named on the
command line and is broken, before a world has been built.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from krrood.ormatic.data_access_objects.helper import to_dao
from sqlalchemy.orm import Session
from typing_extensions import Protocol

from experiments.montessori.results_database import (
    ReadOnlyResultsDatabase,
    ResultsDatabase,
    UnreachableResultsDatabase,
    database_label,
    verify_reachable,
    verify_writable,
)
from experiments.montessori.sorting_results import SortingIterationResult

logger = logging.getLogger(__name__)


class RecordsIterations(Protocol):
    """
    Somewhere a run's finished iterations go.
    """

    def record(self, iteration_result: SortingIterationResult) -> None:
        """
        Keep one finished iteration.
        """

    def close(self) -> None:
        """
        Stop recording, releasing whatever was held open.
        """


@dataclass
class RecordsIterationsToADatabase:
    """
    Keeps every finished iteration in a database, one commit each.

    Committed as each iteration finishes rather than once at the end, so a run
    interrupted halfway keeps everything it had finished by then.
    """

    session: Session
    """
    The open session iterations are committed through.
    """

    def record(self, iteration_result: SortingIterationResult) -> None:
        """
        Commit one finished iteration.

        :param iteration_result: The iteration to keep.
        """
        self.session.add(to_dao(iteration_result))
        self.session.commit()

    def close(self) -> None:
        """
        Close the session iterations were committed through.
        """
        self.session.close()


@dataclass
class RecordsNothing:
    """
    Keeps no iteration at all, for a run that would rather sort than record.
    """

    def record(self, iteration_result: SortingIterationResult) -> None:
        """
        Keep nothing.

        :param iteration_result: The iteration that is not kept.
        """

    def close(self) -> None:
        """
        Close nothing.
        """


def open_recording(database_uri: str) -> RecordsIterations:
    """
    Start keeping finished iterations, or keep none if the database refuses them.

    :param database_uri: The database to record to.
    :return: A recorder writing to that database, or one keeping nothing when it cannot
        be reached or will not take a write.
    """
    try:
        verify_reachable(database_uri)
        verify_writable(database_uri)
    except (UnreachableResultsDatabase, ReadOnlyResultsDatabase) as error:
        logger.warning("%s", error)
        logger.warning("Sorting anyway; this run's results are not being recorded.")
        return RecordsNothing()
    logger.info("Recording results to %s.", database_label(database_uri))
    return RecordsIterationsToADatabase(
        session=ResultsDatabase(uri=database_uri).open_session()
    )
