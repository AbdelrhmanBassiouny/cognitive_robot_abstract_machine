"""
Asking the recorded corpus questions that span it: which episodes an insertion failed
in, how often one piece was moved across all of them, which episodes it was picked up
in, and whether that has happened in an episode other than the one being asked about.

Three episodes are recorded through the recorder a run uses, then asked back. Ground
truth is traversed from :meth:`~experiments.episodes.long_term_memory.LongTermMemory.
recall_every_trial` rather than asked for through the query under test, so a query
checked against itself proves nothing here either.
"""

from __future__ import annotations

import pytest
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.world_description.world_entity import Body
from typing_extensions import List, Tuple

from experiments.episodes.episode import (
    Episode,
    FailureResolution,
    InsertionAttempt,
    InsertionOutcome,
    RecordedTrial,
    Tick,
)
from experiments.episodes.long_term_memory import LongTermMemory
from experiments.montessori.results_database import ResultsDatabase
from experiments.questions.long_term_memory import (
    EpisodesWhereInsertionFailed,
    EpisodesWhereThePieceWasPickedUp,
    FailedInsertion,
    HasThisHappenedBefore,
    HowOftenWasThePieceMoved,
)
from experiments.questions.question import Bucket, RememberedThings
from experiments.questions.question_set import QuestionSet
from experiments.scenarios.trial import TrialOutcome

from .test_episodes import SortingFailureType, minimal_plan, sorting_episode
from .test_long_term_memory import record

SORTED_PIECE = "cube"
"""
The piece the corpus acts on, which two of its three episodes pick up.
"""

PIECE_PICKED_UP_ONCE = "cylinder"
"""
The piece only the first episode picks up, so asking whether that has happened in
another episode has a false to give.
"""

CUBE_MOTIONS_PER_EPISODE: Tuple[int, ...] = (2, 1, 1)
"""
How often the cube moved in each of the three recorded episodes, which is what each of
their ticks is built from.
"""

EPISODES_THAT_PICK_THE_CUBE_UP = (0, 2)
"""
Which of the three episodes, by position, record a pick-up of the cube.
"""

FAILED_INSERTION_EPISODE = 0
"""
Which of the three episodes, by position, records an insertion that did not fall
through.
"""

SUCCEEDED_INSERTION_EPISODE = 1
"""
Which of them records an insertion that did, so a question about failures has something
to leave out.
"""

TRIAL_DURATION = 4.0
"""
How long each recorded trial took, which none of these questions reads.
"""

FIRST_TICK = 1.0
"""
When each trial's only tick was taken, in seconds from the start of the trial.
"""

# %% the corpus every question is asked over


@pytest.fixture()
def results_database(tmp_path) -> ResultsDatabase:
    """
    A results database of this test's own, on disk so a run and a question reach it
    through sessions of their own.
    """
    return ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))


def piece(name: str) -> Body:
    """
    The body of one loose piece, as an episode's events name it.

    :param name: What the piece was called.
    """
    return Body(name=PrefixedName(name))


def events_of(position: int) -> List[object]:
    """
    What the episode at the given position of the corpus detected: the cube moving as
    often as :data:`CUBE_MOTIONS_PER_EPISODE` says, the pick-ups that episode records,
    and nothing else.

    :param position: Which episode of the corpus, counting from the first.
    """
    events: List[object] = [
        TranslationEvent(tracked_object=piece(SORTED_PIECE))
        for _ in range(CUBE_MOTIONS_PER_EPISODE[position])
    ]
    if position in EPISODES_THAT_PICK_THE_CUBE_UP:
        events.append(PickUpEvent(tracked_object=piece(SORTED_PIECE)))
    if position == FAILED_INSERTION_EPISODE:
        events.append(PickUpEvent(tracked_object=piece(PIECE_PICKED_UP_ONCE)))
    return events


def insertion_attempts_of(position: int) -> List[InsertionAttempt]:
    """
    The insertions the episode at the given position attempted: one that did not fall
    through, one that did, or none at all.

    :param position: Which episode of the corpus, counting from the first.
    """
    if position == FAILED_INSERTION_EPISODE:
        return [
            InsertionAttempt(
                shape_name=SORTED_PIECE,
                plan=minimal_plan(),
                outcome=InsertionOutcome.DID_NOT_FALL_THROUGH,
                observed_failure=SortingFailureType.WRONG_HOLE,
                resolution=FailureResolution.RETRIED,
            )
        ]
    if position == SUCCEEDED_INSERTION_EPISODE:
        return [
            InsertionAttempt(
                shape_name=SORTED_PIECE,
                plan=minimal_plan(),
                outcome=InsertionOutcome.FELL_THROUGH,
            )
        ]
    return []


@pytest.fixture()
def corpus(results_database: ResultsDatabase) -> List[Episode]:
    """
    Three recorded episodes: one whose insertion did not fall through, one whose did,
    and one that attempted none.
    """
    episodes = [sorting_episode() for _ in CUBE_MOTIONS_PER_EPISODE]
    for position, episode in enumerate(episodes):
        record(
            results_database,
            RecordedTrial(
                episode=episode,
                outcome=TrialOutcome.SUCCEEDED,
                duration=TRIAL_DURATION,
                ticks=[Tick(moment=FIRST_TICK, events=events_of(position))],
                insertion_attempts=insertion_attempts_of(position),
            ),
        )
    return episodes


@pytest.fixture()
def memory(results_database: ResultsDatabase) -> LongTermMemory:
    """
    The episodes that database holds.
    """
    return LongTermMemory(results_database)


# %% which episodes an insertion failed in


def test_only_the_episode_whose_insertion_did_not_fall_through_is_reported(
    corpus: List[Episode], memory: LongTermMemory
):
    question = EpisodesWhereInsertionFailed(
        episode_identifier=corpus[FAILED_INSERTION_EPISODE].identifier
    )

    assert question.ask(memory) == [
        FailedInsertion(
            episode_identifier=corpus[FAILED_INSERTION_EPISODE].identifier,
            failure_type=SortingFailureType.WRONG_HOLE,
            resolution=FailureResolution.RETRIED,
        )
    ]
    assert question.matches_ground_truth(memory)


# %% how often the piece was moved


def test_the_motions_counted_are_every_episodes_together(
    corpus: List[Episode], memory: LongTermMemory
):
    question = HowOftenWasThePieceMoved(
        episode_identifier=corpus[0].identifier, object_name=SORTED_PIECE
    )

    assert question.ask(memory) == sum(CUBE_MOTIONS_PER_EPISODE)
    assert question.matches_ground_truth(memory)


# %% which episodes the piece was picked up in


def test_the_episodes_reported_are_the_ones_that_recorded_a_pick_up(
    corpus: List[Episode], memory: LongTermMemory
):
    question = EpisodesWhereThePieceWasPickedUp(
        episode_identifier=corpus[0].identifier, object_name=SORTED_PIECE
    )

    assert question.ask(memory) == sorted(
        corpus[position].identifier for position in EPISODES_THAT_PICK_THE_CUBE_UP
    )
    assert question.matches_ground_truth(memory)


# %% whether it has happened in another episode


def test_a_piece_picked_up_in_another_episode_has_happened_before(
    corpus: List[Episode], memory: LongTermMemory
):
    question = HasThisHappenedBefore(
        episode_identifier=corpus[EPISODES_THAT_PICK_THE_CUBE_UP[0]].identifier,
        object_name=SORTED_PIECE,
    )

    assert question.ask(memory) is True
    assert question.matches_ground_truth(memory)


def test_a_piece_picked_up_in_this_episode_alone_has_not_happened_before(
    corpus: List[Episode], memory: LongTermMemory
):
    question = HasThisHappenedBefore(
        episode_identifier=corpus[FAILED_INSERTION_EPISODE].identifier,
        object_name=PIECE_PICKED_UP_ONCE,
    )

    assert question.ask(memory) is False
    assert question.matches_ground_truth(memory)


# %% what these questions declare about themselves


def test_every_cross_episode_question_asks_about_what_happened(
    corpus: List[Episode], memory: LongTermMemory
):
    for question in (
        EpisodesWhereInsertionFailed,
        HowOftenWasThePieceMoved,
        EpisodesWhereThePieceWasPickedUp,
        HasThisHappenedBefore,
    ):
        assert question.bucket is Bucket.TEMPORAL_AND_AGENCY


def test_the_long_term_set_asks_the_cross_episode_questions(corpus: List[Episode]):
    question_set = QuestionSet.over_long_term_memory(
        RememberedThings(
            episode_identifier=corpus[0].identifier, object_name=SORTED_PIECE
        )
    )

    asked = {type(question) for question in question_set.questions}
    assert {
        EpisodesWhereInsertionFailed,
        HowOftenWasThePieceMoved,
        EpisodesWhereThePieceWasPickedUp,
        HasThisHappenedBefore,
    } <= asked
