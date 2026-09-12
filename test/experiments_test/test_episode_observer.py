"""
Collecting what a trial's runner cannot see - when it began, the monitor's ticks, the
questions asked, the plans performed and the insertions attempted - and writing it onto
the trial that was recorded.

The trial is built on the recording scenario of :mod:`test_scenarios`, so nothing here
needs a simulator; the questions are asked of the two-arm scene of
:mod:`test_questions`, which is what the frozen set can be scored against.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from segmind.datastructures.events import PickUpEvent, TranslationEvent
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.testing import two_arm_robot_world
from semantic_digital_twin.world_description.world_entity import Body
from sqlalchemy import select

from experiments.episodes.episode import (
    Episode,
    InsertionAttempt,
    InsertionOutcome,
    RecordedTrial,
    Tick,
)
from experiments.episodes.observer import EpisodeObserver, ObserverListener
from experiments.orm.ormatic_interface import RecordedTrialDAO
from experiments.scenarios.runner import ScenarioRunner
from krrood.ormatic.data_access_objects.helper import to_dao

from .test_episodes import minimal_plan
from .test_questions import QuestionedScene, robot, scene
from .test_scenarios import SortOnePiece

# %% what the tests observe

MOMENT_OF_THE_FIRST_TICK = 0.5
"""
When the first tick of a trial is taken to have happened, in seconds after its start.
"""

MOMENT_OF_THE_SECOND_TICK = 1.5
"""
When the second tick is taken to have happened.
"""

MOMENT_OF_THE_QUESTION = 2.0
"""
When the questions are taken to have been asked.
"""


@pytest.fixture()
def observer() -> EpisodeObserver:
    return EpisodeObserver()


def recorded_trial() -> RecordedTrial:
    """
    One finished trial of the recording scenario, as a run records it before anything
    observed is written onto it.
    """
    scenario = SortOnePiece()
    trial = ScenarioRunner().run_trial(scenario)
    return RecordedTrial.from_trial(trial, Episode.from_run(scenario))


def tracked_piece() -> Body:
    """
    The piece the observed events are about.
    """
    return Body(name=PrefixedName("square_hole_1_shape"))


def one_attempt() -> InsertionAttempt:
    """
    One insertion attempt that went through.
    """
    return InsertionAttempt(
        shape_name="cube", plan=minimal_plan(), outcome=InsertionOutcome.FELL_THROUGH
    )


# %% ticks


def test_a_tick_keeps_its_moment_and_its_events(observer: EpisodeObserver):
    events = [PickUpEvent(tracked_object=tracked_piece())]

    observer.tick(MOMENT_OF_THE_FIRST_TICK, events)

    [tick] = observer.ticks
    assert tick.moment == MOMENT_OF_THE_FIRST_TICK
    assert tick.events == events


def test_ticks_are_kept_in_the_order_they_happened(observer: EpisodeObserver):
    observer.tick(MOMENT_OF_THE_FIRST_TICK, [])
    observer.tick(MOMENT_OF_THE_SECOND_TICK, [])

    assert [tick.moment for tick in observer.ticks] == [
        MOMENT_OF_THE_FIRST_TICK,
        MOMENT_OF_THE_SECOND_TICK,
    ]


def test_the_monitor_hook_ticks_the_observer_with_what_it_was_handed(
    observer: EpisodeObserver,
):
    """
    The event monitor hands its listener what a tick detected and nothing else, so the
    hook is what stamps the moment.
    """
    events = [TranslationEvent(tracked_object=tracked_piece())]

    ObserverListener(observer=observer).receive(events)

    [tick] = observer.ticks
    assert tick.events == events
    assert 0.0 <= tick.moment <= observer.elapsed_seconds


# %% questions


def test_asking_scores_every_question_of_the_set_and_stamps_the_moment(
    observer: EpisodeObserver, scene: QuestionedScene
):
    rows = observer.ask(scene.question_set, scene.robot, MOMENT_OF_THE_QUESTION)

    assert observer.queries == rows
    assert [row.question for row in rows] == scene.question_set.questions
    assert {row.moment for row in rows} == {MOMENT_OF_THE_QUESTION}
    assert all(row.answered_correctly is True for row in rows)


def test_questions_asked_twice_are_kept_in_the_order_they_were_asked(
    observer: EpisodeObserver, scene: QuestionedScene
):
    first = observer.ask(scene.question_set, scene.robot, MOMENT_OF_THE_FIRST_TICK)
    second = observer.ask(scene.question_set, scene.robot, MOMENT_OF_THE_QUESTION)

    assert observer.queries == first + second


# %% the plans the robot performed


def test_a_performed_plan_is_kept(observer: EpisodeObserver):
    plan = minimal_plan()

    performed = observer.performed(plan)

    assert observer.plans == [performed]
    assert performed.plan is plan


# %% insertion attempts


def test_an_attempt_is_kept(observer: EpisodeObserver):
    attempt = one_attempt()

    observer.attempted(attempt)

    assert observer.insertion_attempts == [attempt]


# %% writing what was observed onto the trial


def test_what_was_observed_is_written_onto_the_trial(
    observer: EpisodeObserver, scene: QuestionedScene
):
    observer.tick(
        MOMENT_OF_THE_FIRST_TICK, [PickUpEvent(tracked_object=tracked_piece())]
    )
    rows = observer.ask(scene.question_set, scene.robot, MOMENT_OF_THE_QUESTION)
    attempt = one_attempt()
    observer.attempted(attempt)
    trial = recorded_trial()

    performed = observer.performed(minimal_plan())

    written = observer.into(trial)

    assert written is trial
    assert [tick.moment for tick in trial.ticks] == [MOMENT_OF_THE_FIRST_TICK]
    assert trial.queries == rows
    assert trial.plans == [performed]
    assert trial.insertion_attempts == [attempt]


def test_the_trial_is_handed_the_instant_it_began(observer: EpisodeObserver):
    """
    A plan's nodes and a monitor's events carry instants rather than seconds into the
    trial, so the trial keeps the instant it began, which is what places them.
    """
    observer.restart()
    began_at = observer.began_at

    trial = observer.into(recorded_trial())

    assert trial.began_at == began_at


def test_the_next_trial_starts_with_nothing_observed(observer: EpisodeObserver):
    """
    A run repeats its scenario, and what one trial observed must not be written onto
    the trial after it.
    """
    observer.tick(MOMENT_OF_THE_FIRST_TICK, [])
    observer.attempted(one_attempt())
    observer.performed(minimal_plan())
    observer.into(recorded_trial())

    next_trial = observer.into(recorded_trial())

    assert next_trial.ticks == []
    assert next_trial.queries == []
    assert next_trial.plans == []
    assert next_trial.insertion_attempts == []


def test_restarting_measures_moments_from_the_restart(observer: EpisodeObserver):
    observer.restart()

    assert observer.elapsed_seconds < MOMENT_OF_THE_FIRST_TICK


def test_restarting_notes_the_instant_the_trial_begins(observer: EpisodeObserver):
    before = datetime.now()

    observer.restart()

    assert before <= observer.began_at <= datetime.now()


# %% what was observed survives the database


def test_ticks_and_scored_queries_round_trip_through_the_database(
    experiments_database_session, observer: EpisodeObserver, scene: QuestionedScene
):
    """
    A tick's events and a scored query's question are what a later question about the
    history reaches, so both have to come back from the database as they went in.
    """
    session = experiments_database_session
    observer.tick(
        MOMENT_OF_THE_FIRST_TICK, [PickUpEvent(tracked_object=tracked_piece())]
    )
    rows = observer.ask(scene.question_set, scene.robot, MOMENT_OF_THE_QUESTION)
    trial = observer.into(recorded_trial())

    session.add(to_dao(trial))
    session.commit()

    [restored] = [
        row.from_dao() for row in session.scalars(select(RecordedTrialDAO)).all()
    ]
    [tick] = restored.ticks
    assert tick.moment == MOMENT_OF_THE_FIRST_TICK
    assert [type(event) for event in tick.events] == [PickUpEvent]
    assert [type(query.question) for query in restored.queries] == [
        type(row.question) for row in rows
    ]
    assert [query.answered_correctly for query in restored.queries] == [
        row.answered_correctly for row in rows
    ]
    assert {query.moment for query in restored.queries} == {MOMENT_OF_THE_QUESTION}
