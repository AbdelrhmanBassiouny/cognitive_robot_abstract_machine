"""
Tests for whether and where a run keeps the trials it finishes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from coraplex.datastructures.enums import ExecutionType
from sqlalchemy import func, select

from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.recording import (
    EpisodeRecording,
    RecordsNothing,
    RecordsTrialsToADatabase,
    open_recording,
)
from experiments.montessori.results_database import (
    IN_MEMORY_DATABASE_URI,
    ResultsDatabase,
)
from experiments.orm.ormatic_interface import EpisodeDAO, RecordedTrialDAO
from experiments.scenarios.trial import TrialOutcome

from .test_scenarios import (
    PiecePushedAway,
    SortOnePiece,
    SortingStep,
    WithoutThePiecePose,
)

UNREACHABLE_URI = (
    "postgresql+psycopg://recorder:hunter2@127.0.0.1:1/montessori_sorting_results"
)
"""
A Postgres URI on a port nothing listens on, carrying a password a log must not repeat.
"""


def sorting_episode() -> Episode:
    """
    An episode of one simulated sorting run.
    """
    return Episode(
        scenario_name="montessori_sorting", execution_type=ExecutionType.SIMULATED
    )


def finished_trial(episode: Episode) -> RecordedTrial:
    """
    One trial of the given episode that reached its goal.

    :param episode: The episode the trial belongs to.
    """
    return RecordedTrial(episode=episode, outcome=TrialOutcome.SUCCEEDED, duration=1.0)


def recorded_count(results_database: ResultsDatabase, data_access_object: type) -> int:
    """
    How many rows of one kind a database holds.

    :param results_database: The database to count in.
    :param data_access_object: The generated data access object to count.
    """
    with results_database.open_session() as session:
        return session.scalar(select(func.count()).select_from(data_access_object))


# %% recording to a database that takes writes
def test_a_finished_trial_is_kept(tmp_path):
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))

    recording = open_recording(database)
    recording.record(finished_trial(sorting_episode()))
    recording.close()

    assert recorded_count(database, RecordedTrialDAO) == 1


def test_the_trials_of_one_run_share_one_episode_row(tmp_path):
    """
    The recorder commits each trial as it finishes, so the episode they belong to is
    written by the first of them and found again by the rest rather than written anew.
    """
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))
    episode = sorting_episode()

    recording = open_recording(database)
    recording.record(finished_trial(episode))
    recording.record(finished_trial(episode))
    recording.close()

    assert recorded_count(database, RecordedTrialDAO) == 2
    assert recorded_count(database, EpisodeDAO) == 1


def test_a_trial_is_kept_before_the_recording_is_closed(tmp_path):
    """
    A run that dies keeps the trials it had finished, which is only true if each one is
    committed as it ends rather than at the end of the run.
    """
    database = ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))
    episode = sorting_episode()

    recording = open_recording(database)
    recording.record(finished_trial(episode))

    assert recorded_count(database, RecordedTrialDAO) == 1
    recording.close()


def test_a_writable_database_is_recorded_to(tmp_path):
    recording = open_recording(
        ResultsDatabase(uri="sqlite:///%s" % (tmp_path / "results.db"))
    )

    assert isinstance(recording, RecordsTrialsToADatabase)
    recording.close()


def test_an_in_memory_database_is_read_back_through_the_same_object():
    """
    An in-memory database is what a run falls back to, and the viewer's episodic-memory
    questions are answered from the very object the run recorded through.
    """
    database = ResultsDatabase(uri=IN_MEMORY_DATABASE_URI)

    recording = open_recording(database)
    recording.record(finished_trial(sorting_episode()))

    assert recorded_count(database, RecordedTrialDAO) == 1
    recording.close()


# %% a database that will not take them
def test_a_run_that_cannot_reach_a_database_records_nothing(caplog):
    """
    A database problem must cost a run its episode, never the run itself.
    """
    with caplog.at_level(logging.WARNING):
        recording = open_recording(ResultsDatabase(uri=UNREACHABLE_URI))

    assert isinstance(recording, RecordsNothing)


def test_a_run_that_cannot_record_says_so_without_the_password(caplog):
    """
    The URI usually comes from an environment variable that carries a password, and a
    demo's log is pasted into issues and chats.
    """
    with caplog.at_level(logging.WARNING):
        open_recording(ResultsDatabase(uri=UNREACHABLE_URI))

    assert "montessori_sorting_results" in caplog.text
    assert "hunter2" not in caplog.text


def test_a_run_that_cannot_record_is_told_it_is_not_recording(caplog):
    """
    Nothing else in the run's output would reveal that its episode is being dropped.
    """
    with caplog.at_level(logging.WARNING):
        open_recording(ResultsDatabase(uri=UNREACHABLE_URI))

    assert "not being recorded" in caplog.text


def test_a_read_only_database_records_nothing(tmp_path):
    path = tmp_path / "results.db"
    ResultsDatabase(uri="sqlite:///%s" % path).open_session().close()

    recording = open_recording(
        ResultsDatabase(uri="sqlite:///file:%s?mode=ro&uri=true" % path)
    )

    assert isinstance(recording, RecordsNothing)


# %% recording nothing at all
def test_recording_nothing_keeps_nothing():
    recording = RecordsNothing()

    recording.record(finished_trial(sorting_episode()))
    recording.close()


# %% a run that records the episode it is making


@dataclass
class TrialsKeptInMemory:
    """
    Somewhere a run's trials go that a test can read back without a database.
    """

    trials: list[RecordedTrial] = field(default_factory=list)
    """
    The trials recorded so far, in order.
    """

    def record(self, trial: RecordedTrial) -> None:
        self.trials.append(trial)

    def close(self) -> None:
        pass


def test_every_trial_of_a_run_is_recorded_under_one_episode():
    """
    A run makes one episode, so every trial it finishes names that one rather than an
    episode of its own.
    """
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    kept = TrialsKeptInMemory()

    EpisodeRecording(repetitions=3, episode=episode, records_trials=kept).run(scenario)

    assert len(kept.trials) == 3
    assert {trial.episode.identifier for trial in kept.trials} == {episode.identifier}


def test_a_recorded_trial_carries_what_its_trial_measured():
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    kept = TrialsKeptInMemory()

    report = EpisodeRecording(episode=episode, records_trials=kept).run(scenario)

    [recorded_trial] = kept.trials
    [trial] = report.trials
    assert recorded_trial.outcome is trial.outcome
    assert recorded_trial.duration == trial.duration


def test_a_run_describes_the_conditions_and_perturbations_it_was_made_under():
    """
    The conditions act on a live world, so what an episode keeps of them is their names.
    """
    episode = Episode.from_run(
        SortOnePiece(),
        conditions=[WithoutThePiecePose()],
        perturbations=[PiecePushedAway(step=SortingStep.PICK_UP)],
    )

    assert episode.condition_names == [WithoutThePiecePose.__name__]
    assert episode.perturbation_names == [PiecePushedAway.__name__]
    assert episode.scenario_name == SortOnePiece.name
