"""
Everything past runs recorded, asked in the language a live world is asked in.

An EQL query over the recorded episodes is answered with domain objects rather than with
rows, so the history is reached the same way a world is, and a report is computed from
what was recorded rather than from what is still in the process that recorded it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.query.query import Query
from krrood.exceptions import DataclassException
from krrood.ormatic.data_access_objects.from_dao import FromDataAccessObjectState
from krrood.ormatic.eql_interface import eql_to_sql
from typing_extensions import TYPE_CHECKING, Any, Iterable, List, Optional, Sequence

from experiments.episodes.episode import RecordedTrial
from experiments.experiment_definitions import DEFAULT_CONFIDENCE_LEVEL
from experiments.montessori.results_database import ResultsDatabase
from experiments.scenarios.report import Metric, Report

if TYPE_CHECKING:
    from semantic_digital_twin.orm.ormatic_interface import WorldMappingDAO

logger = logging.getLogger(__name__)

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


# %% an episode whose kept world cannot be read back


@dataclass
class KeptWorldCannotBeReadError(DataclassException):
    """
    Raised for an episode whose kept world refers to mesh files that are no longer there.

    A kept world refers to its meshes by path, and reading it back loads every one of
    them, so one missing file makes the whole episode unreadable.
    """

    episode_identifier: str
    """
    The episode whose world it is.
    """

    missing_mesh_files: List[str]
    """
    The files the world refers to that are not there.
    """

    def error_message(self) -> str:
        return (
            "The kept world of episode %s refers to %d mesh file(s) that are gone, "
            "%s among them."
            % (
                self.episode_identifier,
                len(self.missing_mesh_files),
                self.missing_mesh_files[0],
            )
        )

    def suggest_correction(self) -> str:
        return (
            "A mesh a recorded world refers to must be exported where it outlives the "
            "process that wrote it (experiments.episodes.artifacts.keep_mesh); an "
            "episode recorded otherwise cannot be read back and needs its rows removed."
        )


def missing_mesh_files_of(world: Optional[WorldMappingDAO]) -> List[str]:
    """
    The mesh files a stored world refers to that are not there.

    :param world: The world as stored, or none if the episode kept no world.
    :return: Each missing file's path, in the order the world's bodies refer to them.
    """
    from semantic_digital_twin.orm.ormatic_interface import BodyDAO, MeshDAO

    if world is None:
        return []
    missing: List[str] = []
    for held in world.kinematic_structure_entities:
        if not isinstance(held.target, BodyDAO):
            continue
        for collection in (held.target.visual, held.target.collision):
            for shape in collection.shapes:
                if not isinstance(shape.target, MeshDAO):
                    continue
                if not Path(shape.target.filename).is_file():
                    missing.append(shape.target.filename)
    return missing


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
            return self._as_domain_objects(eql_to_sql(question, session).evaluate())

    @staticmethod
    def _as_domain_objects(rows: Iterable[Any]) -> List[Any]:
        """
        Convert the given rows to the domain objects they store, through one conversion
        state.

        :param rows: The rows a query evaluated to, within the session that read them.
        :return: Their domain objects, in the rows' order.
        """
        conversion_state = FromDataAccessObjectState()
        return [row.from_dao(conversion_state) for row in rows]

    def answer_with_identifiers(self, question: Query) -> List[str]:
        """
        Answer an EQL query selecting episodes with their identifiers alone.

        Read off the rows rather than built from the episodes: an answer that names
        episodes has no use for their worlds, and rebuilding a corpus of worlds to list
        identifiers takes minutes.

        :param question: The query to answer, which selects episodes.
        :return: The identifier of every episode the query selected.
        """
        with self.results_database.open_session() as session:
            return [row.identifier for row in eql_to_sql(question, session).evaluate()]

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

    def recall_every_trial(self) -> List[RecordedTrial]:
        """
        Every trial the database holds, across every episode it recorded.

        What the paper's tables are computed over: a table reports the whole corpus
        rather than one run, and the trials carry the episode they belong to, so what
        each of them ran under is reached from the trial itself.

        :return: Every recorded trial, in whatever order the database returns them.
        """
        trial = variable(type_=RecordedTrial, domain=[])
        return self.answer(an(entity(trial)))

    def recall_every_readable_trial(self) -> List[RecordedTrial]:
        """
        Every trial the database holds whose episode's kept world can be read back.

        An episode whose kept world refers to a mesh file that is gone cannot be read
        back at all and would stop the recall of every other; it is passed over with a
        warning instead, so the paper's figures are still made of the rest of the corpus.

        :return: Every readable trial, in whatever order the database returns them.
        """
        trial = variable(type_=RecordedTrial, domain=[])
        with self.results_database.open_session() as session:
            readable = []
            passed_over: set[str] = set()
            for row in eql_to_sql(an(entity(trial)), session).evaluate():
                if row.episode.identifier in passed_over:
                    continue
                missing = missing_mesh_files_of(row.episode.world)
                if missing:
                    passed_over.add(row.episode.identifier)
                    logger.warning(
                        "%s",
                        KeptWorldCannotBeReadError(
                            episode_identifier=row.episode.identifier,
                            missing_mesh_files=missing,
                        ),
                    )
                    continue
                readable.append(row)
            return self._as_domain_objects(readable)

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


# %% the memory of a corpus that is finished recording


@dataclass
class FinishedCorpusMemory(LongTermMemory):
    """
    The episodes of a corpus that is finished recording, every trial of it recalled
    once.

    A corpus is asked once it stands, and every question spanning it is answered from
    the same trials, so reading the whole corpus again for each asking would read the
    same rows every time.
    """

    _every_trial: Optional[List[RecordedTrial]] = field(init=False, default=None)
    """
    Every trial of the corpus, once it has been recalled.
    """

    def recall_every_trial(self) -> List[RecordedTrial]:
        if self._every_trial is None:
            self._every_trial = super().recall_every_trial()
        return self._every_trial
