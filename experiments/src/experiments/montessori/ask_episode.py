"""
Ask a recorded episode the long-term-memory question set after the fact, and keep the
scored rows with the trial they were asked about.

What a run recorded is asked back the way the paper scores remembering: every question
of the set over long-term memory, answered from the database and checked against what
the trials actually recorded.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import StrEnum

from krrood.ormatic.data_access_objects.helper import to_dao
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
from experiments.questions.question import RememberedThings, RequiredFact
from experiments.questions.question_set import QuestionSet

# %% what the command line offers


class AskingOption(StrEnum):
    """
    The command line options, as they are spelled.
    """

    EPISODE = "--episode"
    OBJECT_NAME = "--object-name"
    DATABASE_URI = "--database-uri"


@dataclass(frozen=True)
class AskingArguments:
    """
    Everything the command line settles for one round of questions.
    """

    episode_identifier: str
    """
    The episode the questions are about.
    """

    object_name: str
    """
    What the object the questions about one object are about was called.
    """

    database_uri: Optional[str]
    """
    The database asked for on the command line, or None to use the configured one.
    """


def parse_arguments(argument_list: Optional[Sequence[str]] = None) -> AskingArguments:
    """
    Read which episode is asked about off the command line.

    :param argument_list: Arguments to read; the process's own when omitted.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(AskingOption.EPISODE, required=True)
    parser.add_argument(AskingOption.OBJECT_NAME, required=True)
    parser.add_argument(AskingOption.DATABASE_URI, default=None)
    parsed = parser.parse_args(argument_list)
    return AskingArguments(
        episode_identifier=parsed.episode,
        object_name=parsed.object_name,
        database_uri=parsed.database_uri,
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


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    """
    Ask one recorded episode the question set and keep the answers with it.

    :param argument_list: Arguments to read; the process's own when omitted.
    :return: 0 once the rows are kept.
    """
    arguments = parse_arguments(argument_list)
    database = ResultsDatabase(
        uri=ConfiguredDatabase.resolve(arguments.database_uri).uri
    )
    rows = ask_episode(
        LongTermMemory(database), arguments.episode_identifier, arguments.object_name
    )
    keep_with_the_trial(database, arguments.episode_identifier, rows)
    for row in rows:
        print("%s -> %s (%s)" % (row.text, row.answer, row.answered_correctly))
    print(
        "%d questions asked of episode %s and kept with its trial."
        % (len(rows), arguments.episode_identifier)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
