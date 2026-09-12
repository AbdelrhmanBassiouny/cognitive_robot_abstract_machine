"""
The question set asked the moment the object it is about stops moving, so the query
stands right after the stretch of the trial a card draws.
"""

from __future__ import annotations

import pytest
from segmind.datastructures.events import (
    PickUpEvent,
    StopTranslationEvent,
    TranslationEvent,
)

from experiments.episodes.observer import EpisodeObserver, ObserverListener
from semantic_digital_twin.testing import two_arm_robot_world
from experiments.questions.after_the_move import QuestionAfterTheMove

from .test_questions import QuestionedScene, scene


@pytest.fixture
def asks(scene: QuestionedScene) -> QuestionAfterTheMove:
    """
    What waits for the cube of the questioned scene to come to rest.
    """
    observer = EpisodeObserver()
    return QuestionAfterTheMove(
        observer=observer,
        asked_about=scene.cube,
        question_set=lambda: scene.question_set,
        robot=scene.robot,
        listener=ObserverListener(observer),
    )


def test_the_set_is_asked_the_moment_the_object_stops(
    asks: QuestionAfterTheMove, scene: QuestionedScene
) -> None:
    asks.receive([TranslationEvent(tracked_object=scene.cube)])
    assert not asks.asked and not asks.observer.queries

    asks.receive([StopTranslationEvent(tracked_object=scene.cube)])

    assert asks.asked
    assert [query.question for query in asks.observer.queries] == (
        scene.question_set.questions
    )
    assert len(asks.observer.ticks) == 2


def test_another_object_stopping_does_not_ask(
    asks: QuestionAfterTheMove, scene: QuestionedScene
) -> None:
    asks.receive([StopTranslationEvent(tracked_object=scene.cylinder)])
    assert not asks.asked

    asks.receive([PickUpEvent(tracked_object=scene.cube)])
    assert not asks.asked


def test_the_set_is_asked_once_however_often_the_object_stops(
    asks: QuestionAfterTheMove, scene: QuestionedScene
) -> None:
    asks.receive([StopTranslationEvent(tracked_object=scene.cube)])
    asks.receive([StopTranslationEvent(tracked_object=scene.cube)])

    assert len(asks.observer.queries) == len(scene.question_set.questions)


def test_a_run_that_never_saw_the_object_stop_asks_as_it_ends(
    asks: QuestionAfterTheMove, scene: QuestionedScene
) -> None:
    asked = asks.ask_if_not_yet()

    assert asks.asked
    assert asked == asks.observer.queries
    assert asks.ask_if_not_yet() == []
