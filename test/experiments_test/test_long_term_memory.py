"""
Asking the recorded episodes the questions a live world is asked.

An EQL query over the results database is answered with the domain objects the run
wrote, and a report rebuilt from those objects measures what the run that wrote them
measured.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from experiments.episodes.episode import (
    Episode,
    InsertionAttempt,
    InsertionOutcome,
    RecordedMotion,
    RecordedTrial,
)
from experiments.episodes.long_term_memory import (
    LongTermMemory,
    UnrecordedEpisodeError,
)
from experiments.episodes.recording import EpisodeRecording, open_recording
from experiments.montessori.results_database import ResultsDatabase
from experiments.scenarios.report import GoalReached, Metric, Report, TrialDuration
from experiments.scenarios.trial import TrialOutcome
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from krrood.entity_query_language.factories import an, contains, entity, variable

from .test_episode_recording import sorting_episode
from .test_episodes import SortingFailureType, minimal_plan
from .test_scenarios import SortOnePiece

SQUARE_HOLE = "square_hole_1"
"""
The shape the one attempt asked after below was made at.
"""

ROUND_HOLE = "circular_hole_1"
"""
The shape the other recorded attempt was made at, so a question about the square one has
something to leave out.
"""

MOMENT_THE_REACH_BEGAN = 1.5
"""
When the first of the two recorded motions began, in seconds from the start of the
trial.
"""

MOMENT_THE_REACH_ENDED = 4.0
"""
When it ended, leaving a gap before the next one that neither of them ran in.
"""

MOMENT_THE_GRASP_BEGAN = 4.5
"""
When the second recorded motion began.
"""

MOMENT_THE_GRASP_ENDED = 9.0
"""
When it ended, which is before the trial did.
"""

MOMENT_ONLY_THE_GRASP_RAN_AT = 5.0
"""
A moment the second motion ran at and the first did not, which is what a question about
one moment has to single it out by.
"""


@pytest.fixture()
def results_database(tmp_path) -> ResultsDatabase:
    """
    A results database of this test's own, on disk so a run and a question reach it
    through sessions of their own.
    """
    return ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))


def record(results_database: ResultsDatabase, *trials: RecordedTrial) -> None:
    """
    Record the given trials the way a run records them, and stop recording.

    :param results_database: The database to record to.
    :param trials: The finished trials to keep.
    """
    recording = open_recording(results_database)
    for trial in trials:
        recording.record(trial)
    recording.close()


def succeeded_trial(episode: Episode, duration: float) -> RecordedTrial:
    """
    One trial of the given episode that reached its goal.

    :param episode: The episode the trial belongs to.
    :param duration: How long the trial took.
    """
    return RecordedTrial(
        episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=duration
    )


# %% recalling what a run recorded


def test_a_recalled_trial_is_the_object_the_run_recorded(results_database):
    """
    The SQL backend is one of the paper's four, which it can only be by answering in the
    objects the other three answer in rather than in rows.
    """
    episode = sorting_episode()
    record(results_database, succeeded_trial(episode, duration=12.5))

    [trial] = LongTermMemory(results_database).recall_trials(episode.identifier)

    assert isinstance(trial, RecordedTrial)
    assert trial.outcome is TrialOutcome.SUCCEEDED
    assert trial.duration == 12.5


def test_the_trials_of_one_episode_are_recalled_under_one_episode(results_database):
    """
    A run makes one episode, so the trials recalled from it name one object rather than a
    copy each -- which is only true if one conversion state serves the whole answer.
    """
    episode = sorting_episode()
    record(
        results_database,
        succeeded_trial(episode, duration=1.0),
        succeeded_trial(episode, duration=2.0),
    )

    first, second = LongTermMemory(results_database).recall_trials(episode.identifier)

    assert first.episode is second.episode
    assert first.episode.identifier == episode.identifier


def test_only_the_asked_episode_is_recalled(results_database):
    """
    A database holds every run ever made, so recalling an episode has to reach that
    episode's trials and no others.
    """
    asked_after = sorting_episode()
    another_run = sorting_episode()
    record(
        results_database,
        succeeded_trial(asked_after, duration=1.0),
        succeeded_trial(another_run, duration=2.0),
    )

    trials = LongTermMemory(results_database).recall_trials(asked_after.identifier)

    assert [trial.duration for trial in trials] == [1.0]


def test_an_episode_the_database_does_not_hold_recalls_no_trial(results_database):
    """
    Recalling is an ordinary question with an ordinary empty answer; it is the report
    below that has to tell an unfound episode from one that measured nothing.
    """
    assert LongTermMemory(results_database).recall_trials("never recorded") == []


# %% asking the history a question of one's own


def test_a_question_about_the_history_is_answered_with_domain_objects(
    results_database,
):
    """
    How often the square hole failed is a question about every run ever made, so it is
    asked of the recorded attempts themselves rather than of one episode's trials.
    """
    trial = RecordedTrial(
        episode=sorting_episode(),
        outcome=TrialOutcome.FAILED,
        duration=8.0,
        insertion_attempts=[
            InsertionAttempt(
                shape_name=SQUARE_HOLE,
                plan=minimal_plan(),
                outcome=InsertionOutcome.DID_NOT_FALL_THROUGH,
                observed_failure=SortingFailureType.WRONG_HOLE,
            ),
            InsertionAttempt(
                shape_name=ROUND_HOLE,
                plan=minimal_plan(),
                outcome=InsertionOutcome.FELL_THROUGH,
            ),
        ],
    )
    record(results_database, trial)

    attempt = variable(type_=InsertionAttempt, domain=[])
    [answered] = LongTermMemory(results_database).answer(
        an(entity(attempt).where(attempt.shape_name == SQUARE_HOLE))
    )

    assert isinstance(answered, InsertionAttempt)
    assert answered.shape_name == SQUARE_HOLE
    assert answered.observed_failure is SortingFailureType.WRONG_HOLE


# %% the motions a run ran


def trial_that_ran_two_motions(episode: Episode) -> RecordedTrial:
    """
    One trial that ran a motion, waited, and ran another.

    :param episode: The episode the trial belongs to.
    """
    return RecordedTrial(
        episode=episode,
        outcome=TrialOutcome.SUCCEEDED,
        duration=10.0,
        motions=[
            RecordedMotion(
                motion_statechart=MotionStatechart(),
                start_moment=MOMENT_THE_REACH_BEGAN,
                end_moment=MOMENT_THE_REACH_ENDED,
            ),
            RecordedMotion(
                motion_statechart=MotionStatechart(),
                start_moment=MOMENT_THE_GRASP_BEGAN,
                end_moment=MOMENT_THE_GRASP_ENDED,
            ),
        ],
    )


def test_the_motions_of_one_episode_are_answered_from_the_database(results_database):
    """
    A trial holds its motions in a collection, so asking which motions a run made
    crosses the association table the generated interface reaches that collection
    through.
    """
    episode = sorting_episode()
    trial = trial_that_ran_two_motions(episode)
    record(results_database, trial)

    recorded_trial = variable(type_=RecordedTrial, domain=[])
    motion = variable(type_=RecordedMotion, domain=[])
    answered = LongTermMemory(results_database).answer(
        an(
            entity(motion).where(
                recorded_trial.episode.identifier == episode.identifier,
                contains(recorded_trial.motions, motion),
            )
        )
    )

    assert sorted(one.start_moment for one in answered) == [
        one.start_moment for one in trial.motions
    ]
    assert sorted(one.end_moment for one in answered) == [
        one.end_moment for one in trial.motions
    ]


def test_the_motion_that_was_running_at_a_moment_is_the_one_answered(results_database):
    """
    What the spans are recorded for: the motion a question about a moment is about is
    the one whose span holds that moment, which is asked as a condition on the spans
    rather than by reading every motion back and picking one out afterwards.
    """
    trial = trial_that_ran_two_motions(sorting_episode())
    record(results_database, trial)
    _, grasp = trial.motions

    motion = variable(type_=RecordedMotion, domain=[])
    [answered] = LongTermMemory(results_database).answer(
        an(
            entity(motion).where(
                motion.start_moment <= MOMENT_ONLY_THE_GRASP_RAN_AT,
                motion.end_moment >= MOMENT_ONLY_THE_GRASP_RAN_AT,
            )
        )
    )

    assert answered.start_moment == grasp.start_moment
    assert answered.end_moment == grasp.end_moment


# %% the report a run rendered, rebuilt from what it recorded


@dataclass
class RecordedRun:
    """
    A finished run, as both the episode it recorded and the report it rendered.
    """

    episode: Episode
    """
    The episode the run made, which its report is asked for again by.
    """

    report: Report
    """
    What the run itself reported over the trials still in its own process.
    """


@pytest.fixture()
def measured_metrics() -> list[Metric]:
    """
    The metrics both the run and the report read back from the database measure.
    """
    return [GoalReached(), TrialDuration()]


@pytest.fixture()
def recorded_run(results_database, measured_metrics) -> RecordedRun:
    """
    A finished run of three trials, recorded to the database as it went.
    """
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    recording = open_recording(results_database)
    report = EpisodeRecording(
        repetitions=3,
        metrics=measured_metrics,
        episode=episode,
        records_trials=recording,
    ).run(scenario)
    recording.close()
    return RecordedRun(episode=episode, report=report)


def test_a_report_read_from_the_database_measures_what_the_run_measured(
    results_database, measured_metrics, recorded_run
):
    """
    Every experiment's report is computed from the database, so it has to say what the
    run's own report said over the same trials.
    """
    reread = LongTermMemory(results_database).report_on(
        recorded_run.episode.identifier, measured_metrics
    )

    assert [reread.summarize(metric) for metric in measured_metrics] == [
        recorded_run.report.summarize(metric) for metric in measured_metrics
    ]


def test_a_report_read_from_the_database_names_the_scenario_that_ran(
    results_database, measured_metrics, recorded_run
):
    """
    The scenario is read off the recalled episode rather than asked of whoever wants the
    report, which would let a report name a scenario its trials never ran.
    """
    reread = LongTermMemory(results_database).report_on(
        recorded_run.episode.identifier, measured_metrics
    )

    assert reread.scenario_name == recorded_run.report.scenario_name


def test_a_report_over_an_episode_the_database_does_not_hold_is_refused(
    results_database, measured_metrics
):
    """
    An empty report reads as a run that measured nothing rather than as one that was
    never found, so the episode nothing was found under is named instead.
    """
    with pytest.raises(UnrecordedEpisodeError):
        LongTermMemory(results_database).report_on("never recorded", measured_metrics)
