"""
Ask a recorded episode the long-term-memory question set after the fact, keep the scored
rows with the trial they were asked about, and score the working-memory rows a run wrote
while it happened again.

What a run recorded is asked back the way the paper scores remembering: every question
of the set over long-term memory, answered from the database and checked against what
the trials actually recorded. What the run scored while it happened is scored again
against the account of its scene each of those rows carries, so an episode whose rows
were scored by an older rule is re-scored rather than run again.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum

from krrood.exceptions import DataclassException
from krrood.ormatic.data_access_objects.helper import to_dao
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World
from sqlalchemy import select
from typing_extensions import List, Optional, Sequence, Set

from experiments.episodes.episode import RecordedQuery, RecordedTrial
from experiments.episodes.long_term_memory import (
    LongTermMemory,
    UnrecordedEpisodeError,
)
from experiments.montessori.results_database import (
    ConfiguredDatabase,
    ResultsDatabase,
)
from experiments.questions.question import (
    RememberedThings,
    RequiredFact,
    ScoredAgainstTheSceneAsSetUp,
)
from experiments.questions.question_set import QuestionSet

# %% what the command line offers


class AskingOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    EPISODE = "--episode"
    OBJECT_NAME = "--object-name"
    DATABASE_URI = "--database-uri"
    RESCORE_WORKING_MEMORY = "--rescore-working-memory"


@dataclass(frozen=True)
class AskingArguments:
    """
    Everything the command line settles for one round of questions.
    """

    episode_identifier: str
    """
    The episode the questions are about.
    """

    object_name: Optional[str]
    """
    What the object the questions about one object are about was called, or None where
    the round asks no question that singles an object out.
    """

    database_uri: Optional[str]
    """
    The database asked for on the command line, or None to use the configured one.
    """

    rescore_working_memory: bool
    """
    Whether this round scores the working-memory rows the episode already holds again
    rather than asking it the long-term-memory set.
    """


def parse_arguments(argument_list: Optional[Sequence[str]] = None) -> AskingArguments:
    """
    Read which episode is asked about off the command line.

    :param argument_list: Arguments to read; the process's own when omitted.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(AskingOption.EPISODE, required=True)
    parser.add_argument(AskingOption.OBJECT_NAME, default=None)
    parser.add_argument(AskingOption.DATABASE_URI, default=None)
    parser.add_argument(AskingOption.RESCORE_WORKING_MEMORY, action="store_true")
    parsed = parser.parse_args(argument_list)
    return AskingArguments(
        episode_identifier=parsed.episode,
        object_name=parsed.object_name,
        database_uri=parsed.database_uri,
        rescore_working_memory=parsed.rescore_working_memory,
    )


# %% asking, and keeping what was answered

FACTS_IN_THE_EVENT_LOG = {RequiredFact.MOTION_EVENTS, RequiredFact.PICK_UP_EVENTS}
"""
What an episode's ticks represent, however few events they hold.
"""

FACTS_IN_THE_RECORDED_WORLD = {
    RequiredFact.KINEMATIC_STRUCTURE,
    RequiredFact.DEGREES_OF_FREEDOM,
}
"""
What an episode that kept its world represents.
"""


def recorded_facts(trials: Sequence[RecordedTrial]) -> Set[RequiredFact]:
    """
    The facts an episode's trials represent, which is what decides which questions can
    be scored against it.

    :param trials: The episode's recalled trials.
    """
    facts: Set[RequiredFact] = set()
    if any(trial.ticks for trial in trials):
        facts |= FACTS_IN_THE_EVENT_LOG
    if any(trial.episode.world is not None for trial in trials):
        facts |= FACTS_IN_THE_RECORDED_WORLD
    return facts


def ask_episode(
    memory: LongTermMemory, episode_identifier: str, object_name: str
) -> List[RecordedQuery]:
    """
    Ask one episode every question of the long-term-memory set its record can answer,
    scored.

    :param memory: The episodes past runs recorded.
    :param episode_identifier: The episode the questions are about.
    :param object_name: What the object the questions about one object are about was
        called.
    :raises UnrecordedEpisodeError: If the database holds no trial of that episode.
    :return: The scored rows, in the set's own order.
    """
    trials = memory.recall_trials(episode_identifier)
    if not trials:
        raise UnrecordedEpisodeError(episode_identifier=episode_identifier)
    question_set = QuestionSet.over_long_term_memory(
        RememberedThings(episode_identifier=episode_identifier, object_name=object_name)
    ).answerable_with(recorded_facts(trials))
    return question_set.answer_and_record(memory)


def keep_with_the_trial(
    results_database: ResultsDatabase,
    episode_identifier: str,
    rows: Sequence[RecordedQuery],
) -> None:
    """
    Append scored rows to the last recorded trial of an episode.

    Appended to the rows the trial already carries rather than replacing them, so what
    the run asked while it happened and what it was asked afterwards are both kept.

    :param results_database: The database the episode was recorded to.
    :param episode_identifier: The episode the rows are about.
    :param rows: The rows to keep.
    :raises UnrecordedEpisodeError: If the database holds no trial of that episode.
    """
    from experiments.orm.ormatic_interface import (
        EpisodeDAO,
        RecordedTrialDAO,
        RecordedTrialDAO_queries_association,
    )

    with results_database.open_session() as session:
        trials = session.scalars(
            select(RecordedTrialDAO)
            .join(EpisodeDAO, RecordedTrialDAO.episode)
            .where(EpisodeDAO.identifier == episode_identifier)
            .order_by(RecordedTrialDAO.database_id)
        ).all()
        if not trials:
            raise UnrecordedEpisodeError(episode_identifier=episode_identifier)
        for row in rows:
            trials[-1].queries.append(
                RecordedTrialDAO_queries_association(target=to_dao(row))
            )
        session.commit()


# %% scoring again what a run scored while it happened


@dataclass
class TheObjectAskedAboutIsNotNamed(DataclassException):
    """
    Raised when an episode is asked the long-term-memory set without being told what the
    object those questions single out was called.
    """

    episode_identifier: str
    """
    The episode that was to be asked.
    """

    def error_message(self) -> str:
        return "Nothing says which object episode %s is asked about." % (
            self.episode_identifier
        )

    def suggest_correction(self) -> str:
        return "Name it with %s." % AskingOption.OBJECT_NAME


@dataclass
class EpisodeKeptNoWorldToAskAgain(DataclassException):
    """
    Raised when the working-memory rows of an episode that kept no world are to be
    scored again.
    """

    episode_identifier: str
    """
    The episode that was to be scored again.
    """

    def error_message(self) -> str:
        return "Episode %s kept no world, so its questions cannot be put again." % (
            self.episode_identifier
        )

    def suggest_correction(self) -> str:
        return (
            "A run keeps the world it ran in as it records, so an episode recorded "
            "before it did has rows but nothing left to ask. Run it again."
        )


def robot_of(world: World) -> AbstractRobot:
    """
    The robot a recorded world holds, which is what its working-memory questions were
    put to.

    :param world: The world a run recorded.
    """
    [robot] = world.get_semantic_annotations_by_type(AbstractRobot)
    return robot


def rescore_the_working_memory(
    results_database: ResultsDatabase, episode_identifier: str
) -> List[RecordedQuery]:
    """
    Score the working-memory rows of a recorded episode again and keep the fresh scores
    on them, so an episode scored by an older rule is re-scored rather than run again.

    Only the rows whose questions are scored against the scene as it was set up: those
    carry the account they are scored against, and putting them to the world the run
    kept asks exactly what the run asked. A question answered from what the segmentation
    saw is left alone, since the events it read are the running process's rather than
    the record's.

    :param results_database: The database the episode was recorded to.
    :param episode_identifier: The episode whose rows are scored again.
    :raises UnrecordedEpisodeError: If the database holds no trial of that episode.
    :raises EpisodeKeptNoWorldToAskAgain: If the episode kept no world to ask again.
    :return: The rows that were scored again, in the order they were recorded.
    """
    from experiments.orm.ormatic_interface import EpisodeDAO, RecordedTrialDAO

    with results_database.open_session() as session:
        trials = session.scalars(
            select(RecordedTrialDAO)
            .join(EpisodeDAO, RecordedTrialDAO.episode)
            .where(EpisodeDAO.identifier == episode_identifier)
            .order_by(RecordedTrialDAO.database_id)
        ).all()
        if not trials:
            raise UnrecordedEpisodeError(episode_identifier=episode_identifier)
        rescored: List[RecordedQuery] = []
        for stored in trials:
            recalled = stored.from_dao()
            if recalled.episode.world is None:
                raise EpisodeKeptNoWorldToAskAgain(
                    episode_identifier=episode_identifier
                )
            robot = robot_of(recalled.episode.world)
            for row, association in zip(recalled.queries, stored.queries):
                if not isinstance(row.question, ScoredAgainstTheSceneAsSetUp):
                    continue
                row.answered_correctly = row.question.matches_ground_truth(robot)
                association.target.answered_correctly = row.answered_correctly
                rescored.append(row)
        session.commit()
        return rescored


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Ask one recorded episode the question set and keep the answers with it, or score the
    working-memory rows it already holds again.

    :param argument_list: Arguments to read; the process's own when omitted.
    :raises TheObjectAskedAboutIsNotNamed: If the set is to be asked and nothing says
        which object it singles out.
    :return: 0 once the rows are kept.
    """
    arguments = parse_arguments(argument_list)
    database = ResultsDatabase(
        uri=ConfiguredDatabase.resolve(arguments.database_uri).uri
    )
    if arguments.rescore_working_memory:
        return print_the_scores(
            rescore_the_working_memory(database, arguments.episode_identifier),
            "%d working-memory questions of episode %s scored again.",
            arguments.episode_identifier,
        )
    if arguments.object_name is None:
        raise TheObjectAskedAboutIsNotNamed(
            episode_identifier=arguments.episode_identifier
        )
    rows = ask_episode(
        LongTermMemory(database), arguments.episode_identifier, arguments.object_name
    )
    keep_with_the_trial(database, arguments.episode_identifier, rows)
    return print_the_scores(
        rows,
        "%d questions asked of episode %s and kept with its trial.",
        arguments.episode_identifier,
    )


def print_the_scores(
    rows: Sequence[RecordedQuery], summary: str, episode_identifier: str
) -> int:
    """
    Write what was scored to the console, a row at a time and then a count.

    :param rows: The rows that were scored.
    :param summary: How the count is worded, taking the count and the episode.
    :param episode_identifier: The episode the rows belong to.
    :return: 0.
    """
    for row in rows:
        print("%s -> %s (%s)" % (row.text, row.answer, row.answered_correctly))
    print(summary % (len(rows), episode_identifier))
    return 0


if __name__ == "__main__":
    sys.exit(main())
