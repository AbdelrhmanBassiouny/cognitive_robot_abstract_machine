"""
Asking a recorded episode the long-term-memory question set after the fact, keeping the
scored rows with the trial they were asked about, and scoring the working-memory rows a
run wrote while it happened again.
"""

from __future__ import annotations

import pytest

from experiments.episodes.episode import Episode
from experiments.episodes.long_term_memory import (
    LongTermMemory,
    UnrecordedEpisodeError,
)
from experiments.episodes.episode import RecordedQuery, RecordedTrial, Tick
from experiments.montessori.ask_episode import (
    AskingOption,
    EpisodeKeptNoWorldToAskAgain,
    FACTS_IN_THE_EVENT_LOG,
    TheObjectAskedAboutIsNotNamed,
    ask_episode,
    keep_with_the_trial,
    main,
    parse_arguments,
    recorded_facts,
    rescore_the_working_memory,
)
from experiments.questions.long_term_memory import (
    AnythingMovedInTheEpisode,
    NumberOfDegreesOfFreedomInTheRecordedWorld,
)
from experiments.questions.working_memory import AnythingMoved, ObjectsSeen
from experiments.scenarios.trial import TrialOutcome
from experiments.montessori.results_database import ResultsDatabase
from experiments.questions.question import Memory

from .test_episodes import sorting_episode
from .test_long_term_memory import record
from .test_working_memory_ground_truth import ASceneTheRunStood, area, stood
from .test_long_term_questions import (
    MOVED_OBJECT_NAME,
    memory,
    recorded_episode,
    results_database,
)

# %% the command line


def test_the_episode_and_the_object_are_read(tmp_path):
    arguments = parse_arguments(
        [
            AskingOption.EPISODE,
            "episode-42",
            AskingOption.OBJECT_NAME,
            MOVED_OBJECT_NAME,
            AskingOption.DATABASE_URI,
            "sqlite:///%s" % (tmp_path / "results.db"),
        ]
    )

    assert arguments.episode_identifier == "episode-42"
    assert arguments.object_name == MOVED_OBJECT_NAME
    assert arguments.database_uri == "sqlite:///%s" % (tmp_path / "results.db")


# %% asking


def test_every_long_term_memory_question_is_asked_and_scored(
    memory: LongTermMemory, recorded_episode: Episode
):
    rows = ask_episode(memory, recorded_episode.identifier, MOVED_OBJECT_NAME)

    assert rows
    assert {row.question.memory for row in rows} == {Memory.LONG_TERM}
    assert all(row.answered_correctly is True for row in rows)
    assert {row.question.episode_identifier for row in rows} == {
        recorded_episode.identifier
    }


def test_the_rows_are_kept_with_the_trial_they_asked_about(
    results_database: ResultsDatabase,
    memory: LongTermMemory,
    recorded_episode: Episode,
):
    rows = ask_episode(memory, recorded_episode.identifier, MOVED_OBJECT_NAME)

    keep_with_the_trial(results_database, recorded_episode.identifier, rows)

    [trial] = memory.recall_trials(recorded_episode.identifier)
    assert [type(query.question) for query in trial.queries] == [
        type(row.question) for row in rows
    ]
    assert [query.answered_correctly for query in trial.queries] == [
        row.answered_correctly for row in rows
    ]


def test_asking_twice_keeps_both_rounds(
    results_database: ResultsDatabase,
    memory: LongTermMemory,
    recorded_episode: Episode,
):
    first = ask_episode(memory, recorded_episode.identifier, MOVED_OBJECT_NAME)
    keep_with_the_trial(results_database, recorded_episode.identifier, first)
    second = ask_episode(memory, recorded_episode.identifier, MOVED_OBJECT_NAME)
    keep_with_the_trial(results_database, recorded_episode.identifier, second)

    [trial] = memory.recall_trials(recorded_episode.identifier)
    assert len(trial.queries) == len(first) + len(second)


def test_an_episode_the_database_does_not_hold_is_refused(
    results_database: ResultsDatabase, memory: LongTermMemory
):
    with pytest.raises(UnrecordedEpisodeError):
        keep_with_the_trial(results_database, "nobody-recorded-this", [])


def test_an_episode_the_database_does_not_hold_cannot_be_asked(
    memory: LongTermMemory,
):
    with pytest.raises(UnrecordedEpisodeError):
        ask_episode(memory, "nobody-recorded-this", MOVED_OBJECT_NAME)


# %% what an episode can be asked


def test_an_episode_that_kept_its_world_is_asked_about_its_joints(
    memory: LongTermMemory, recorded_episode: Episode
):
    rows = ask_episode(memory, recorded_episode.identifier, MOVED_OBJECT_NAME)

    assert NumberOfDegreesOfFreedomInTheRecordedWorld in {
        type(row.question) for row in rows
    }


def test_an_episode_that_kept_no_world_is_not_asked_about_its_joints(
    results_database: ResultsDatabase, memory: LongTermMemory
):
    """
    A question about facts nothing recorded cannot be scored, so it is left out rather
    than counted wrong.
    """
    episode = sorting_episode()
    record(
        results_database,
        RecordedTrial(
            episode=episode,
            outcome=TrialOutcome.SUCCEEDED,
            duration=1.0,
            ticks=[Tick(moment=1.0, events=[])],
        ),
    )

    rows = ask_episode(memory, episode.identifier, MOVED_OBJECT_NAME)

    asked = {type(row.question) for row in rows}
    assert NumberOfDegreesOfFreedomInTheRecordedWorld not in asked
    assert AnythingMovedInTheEpisode in asked


def test_the_facts_an_episode_recorded_follow_what_it_kept():
    episode = sorting_episode()
    without_anything = RecordedTrial(
        episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=1.0
    )
    with_ticks = RecordedTrial(
        episode=episode,
        outcome=TrialOutcome.SUCCEEDED,
        duration=1.0,
        ticks=[Tick(moment=1.0, events=[])],
    )

    assert recorded_facts([without_anything]) == set()
    assert recorded_facts([with_ticks]) == FACTS_IN_THE_EVENT_LOG


# %% the whole command


def test_the_command_asks_and_keeps(
    results_database: ResultsDatabase,
    memory: LongTermMemory,
    recorded_episode: Episode,
):
    exit_code = main(
        [
            AskingOption.EPISODE,
            recorded_episode.identifier,
            AskingOption.OBJECT_NAME,
            MOVED_OBJECT_NAME,
            AskingOption.DATABASE_URI,
            results_database.uri,
        ]
    )

    assert exit_code == 0
    [trial] = memory.recall_trials(recorded_episode.identifier)
    assert trial.queries


# %% scoring again what a run scored while it happened

A_SCORE_NOBODY_BELIEVES = False
"""
What the stored rows are set to before they are scored again, so a fresh score is
visible whichever way it comes out.
"""


def a_recorded_working_memory_round(
    results_database: ResultsDatabase, stood: ASceneTheRunStood
) -> Episode:
    """
    One recorded trial carrying the two rows a re-scoring has to tell apart: a question
    scored against the scene as it was set up, and one answered from what the
    segmentation saw. Both are stored with the wrong score.

    :param results_database: The database to record to.
    :param stood: The scene the questions were asked of.
    """
    episode = sorting_episode()
    episode.world = stood.world
    record(
        results_database,
        RecordedTrial(
            episode=episode,
            outcome=TrialOutcome.SUCCEEDED,
            duration=1.0,
            queries=[
                RecordedQuery(
                    role_taker=ObjectsSeen(scene=stood.as_set_up),
                    answer="",
                    latency=0.0,
                    moment=0.0,
                    answered_correctly=A_SCORE_NOBODY_BELIEVES,
                ),
                RecordedQuery(
                    role_taker=AnythingMoved(),
                    answer=str(False),
                    latency=0.0,
                    moment=0.0,
                    answered_correctly=A_SCORE_NOBODY_BELIEVES,
                ),
            ],
        ),
    )
    return episode


def test_a_question_scored_against_the_scene_is_scored_again(
    results_database: ResultsDatabase, memory: LongTermMemory, stood: ASceneTheRunStood
):
    """
    The point of scoring again: the row keeps the account of the scene it was scored
    against, so the world the run kept can be asked once more without running it.
    """
    episode = a_recorded_working_memory_round(results_database, stood)

    [rescored] = rescore_the_working_memory(results_database, episode.identifier)

    assert type(rescored.question) is ObjectsSeen
    assert rescored.answered_correctly is True
    [trial] = memory.recall_trials(episode.identifier)
    [stored] = [query for query in trial.queries if type(query.question) is ObjectsSeen]
    assert stored.answered_correctly is True


def test_a_question_answered_from_what_the_segmentation_saw_is_left_alone(
    results_database: ResultsDatabase, memory: LongTermMemory, stood: ASceneTheRunStood
):
    """
    What the segmentation saw belongs to the process that ran, so a row answered from it
    keeps the score the run gave it rather than being asked of a symbol graph that never
    saw the run.
    """
    episode = a_recorded_working_memory_round(results_database, stood)

    rescore_the_working_memory(results_database, episode.identifier)

    [trial] = memory.recall_trials(episode.identifier)
    [stored] = [
        query for query in trial.queries if type(query.question) is AnythingMoved
    ]
    assert stored.answered_correctly is A_SCORE_NOBODY_BELIEVES


def test_an_episode_that_kept_no_world_cannot_be_scored_again(
    results_database: ResultsDatabase,
):
    episode = sorting_episode()
    record(
        results_database,
        RecordedTrial(episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=1.0),
    )

    with pytest.raises(EpisodeKeptNoWorldToAskAgain):
        rescore_the_working_memory(results_database, episode.identifier)


def test_an_episode_the_database_does_not_hold_cannot_be_scored_again(
    results_database: ResultsDatabase,
):
    with pytest.raises(UnrecordedEpisodeError):
        rescore_the_working_memory(results_database, "nobody-recorded-this")


def test_the_command_scores_the_working_memory_of_an_episode_again(
    results_database: ResultsDatabase, memory: LongTermMemory, stood: ASceneTheRunStood
):
    episode = a_recorded_working_memory_round(results_database, stood)

    exit_code = main(
        [
            AskingOption.EPISODE,
            episode.identifier,
            AskingOption.DATABASE_URI,
            results_database.uri,
            AskingOption.RESCORE_WORKING_MEMORY,
        ]
    )

    assert exit_code == 0
    [trial] = memory.recall_trials(episode.identifier)
    [stored] = [query for query in trial.queries if type(query.question) is ObjectsSeen]
    assert stored.answered_correctly is True


def test_the_set_cannot_be_asked_without_the_object_it_singles_out(
    results_database: ResultsDatabase, recorded_episode: Episode
):
    with pytest.raises(TheObjectAskedAboutIsNotNamed):
        main(
            [
                AskingOption.EPISODE,
                recorded_episode.identifier,
                AskingOption.DATABASE_URI,
                results_database.uri,
            ]
        )
