"""
Everything past runs recorded, asked in the language a live world is asked in.

An EQL query over the recorded episodes is answered with domain objects rather than with
rows, so the history is reached the same way a world is, and a report is computed from
what was recorded rather than from what is still in the process that recorded it.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.query.query import Query
from krrood.exceptions import DataclassException
from krrood.ormatic.data_access_objects.from_dao import FromDataAccessObjectState
from krrood.ormatic.eql_interface import eql_to_sql
from typing_extensions import Any, List, Sequence

from experiments.episodes.episode import RecordedTrial
from experiments.experiment_definitions import DEFAULT_CONFIDENCE_LEVEL
from experiments.montessori.results_database import ResultsDatabase
from experiments.scenarios.report import Metric, Report

# %% asking after an episode that is not there


@dataclass
class UnrecordedEpisodeError(DataclassException):
    """
    Raised when a report is asked for over an episode the database holds no trial of.
    """

    episode_identifier: str
    """
    The episode nothing was found under.
    """

    def error_message(self) -> str:
        return "No trial was recorded under episode %s." % self.episode_identifier

    def suggest_correction(self) -> str:
        return (
            "Check the identifier against the one the run reported, and that the run "
            "recorded to this database rather than falling back to one in memory "
            "because this one could not be reached."
        )


# %% the memory itself


@dataclass
class LongTermMemory:
    """
    The episodes past runs recorded, answering the query language a live world answers.
    """

    results_database: ResultsDatabase
    """
    The database the episodes were recorded to.
    """

    def answer(self, question: Query) -> List[Any]:
        """
        Answer an EQL query from the recorded episodes, as the objects it asked for.

        One conversion state serves the whole answer, so an object several results reach
        is one object rather than a copy for each of them.

        Asked through the database object it was given rather than one of its own, so a
        question put while a run is still going is answered from the very rows that run
        is writing -- which for an in-memory database is only true of a shared
        connection.

        :param question: The query to answer.
        :return: The domain objects the query selected.
        """
        with self.results_database.open_session() as session:
            rows = eql_to_sql(question, session).evaluate()
            conversion_state = FromDataAccessObjectState()
            return [row.from_dao(conversion_state) for row in rows]

    def recall_trials(self, episode_identifier: str) -> List[RecordedTrial]:
        """
        Every trial recorded under one episode.

        :param episode_identifier: What addresses the episode outside the database.
        :return: Its trials, or none if nothing was recorded under it.
        """
        trial = variable(type_=RecordedTrial, domain=[])
        return self.answer(
            an(entity(trial).where(trial.episode.identifier == episode_identifier))
        )

    def report_on(
        self,
        episode_identifier: str,
        metrics: Sequence[Metric],
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    ) -> Report:
        """
        Measure the given metrics over one episode's recorded trials.

        The scenario the report names is read off the recalled episode, so a report can
        never name a scenario its trials did not run.

        :param episode_identifier: What addresses the episode outside the database.
        :param metrics: One metric per row of the report.
        :param confidence_level: Two-sided confidence level the report's intervals hold
            at.
        :raises UnrecordedEpisodeError: If the database holds no trial of that episode.
        :return: What its trials measured.
        """
        trials = self.recall_trials(episode_identifier)
        if not trials:
            raise UnrecordedEpisodeError(episode_identifier=episode_identifier)
        return Report(
            scenario_name=trials[0].episode.scenario_name,
            trials=list(trials),
            metrics=list(metrics),
            confidence_level=confidence_level,
        )
