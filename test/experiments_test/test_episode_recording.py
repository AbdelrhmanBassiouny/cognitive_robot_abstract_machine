"""
Tests for whether and where a run keeps the trials it finishes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy
import pytest
from coraplex.datastructures.enums import ExecutionType
from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo
from semantic_digital_twin.testing import two_arm_robot_world
from sqlalchemy import func, select
from typing_extensions import Optional

from experiments.episodes.artifacts import (
    ArtifactDirectory,
    ArtifactNotKept,
    EpisodeArtifacts,
    Transcript,
)
from experiments.episodes.episode import (
    Episode,
    InsertionAttempt,
    InsertionOutcome,
    RecordedTrial,
)
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

from .test_episodes import minimal_plan
from .test_questions import robot, scene
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


# %% a run that observes its trials and keeps their artifacts


FRAME_SIDE = 16
"""
Pixel width and height of the frames the filmed trials are made of, kept small because
what is asserted is that the video was written rather than what it shows.
"""


@dataclass
class FilmsEveryTrial:
    """
    Stands in for the scene a scenario films, handing back a short video of each trial.
    """

    frames_per_trial: int = 3
    """
    How many frames one trial's video holds.
    """

    def video_of_the_trial(self) -> RecordedVideo:
        return RecordedVideo(
            frames=[
                numpy.full((FRAME_SIDE, FRAME_SIDE, 3), index * 10, dtype=numpy.uint8)
                for index in range(self.frames_per_trial)
            ],
            frames_per_second=30,
        )


def observing_recording(
    episode: Episode,
    kept: TrialsKeptInMemory,
    artifacts: Optional[EpisodeArtifacts] = None,
    film: Optional[FilmsEveryTrial] = None,
    repetitions: int = 1,
) -> EpisodeRecording:
    """
    A run of the recording scenario that observes its trials and keeps what they left.

    :param episode: The episode the run makes.
    :param kept: Where its trials go.
    :param artifacts: Where its artifacts go, if anywhere.
    :param film: What films its trials, if anything.
    :param repetitions: How many trials it runs.
    """
    return EpisodeRecording(
        repetitions=repetitions,
        episode=episode,
        records_trials=kept,
        artifacts=artifacts,
        film=film,
    )


def test_what_the_observer_saw_is_recorded_on_the_trial():
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    kept = TrialsKeptInMemory()
    recording = observing_recording(episode, kept)
    attempt = InsertionAttempt(
        shape_name="cube", plan=minimal_plan(), outcome=InsertionOutcome.FELL_THROUGH
    )
    recording.observer.tick(0.5, [])
    recording.observer.attempted(attempt)

    recording.run(scenario)

    [trial] = kept.trials
    assert [tick.moment for tick in trial.ticks] == [0.5]
    assert trial.insertion_attempts == [attempt]


def test_every_trial_is_numbered_in_the_order_it_ran():
    """
    What a trial kept of its own among the episode's artifacts is addressed by its
    number, so each trial knows which of the episode's it is.
    """
    scenario = SortOnePiece()
    kept = TrialsKeptInMemory()
    recording = observing_recording(Episode.from_run(scenario), kept, repetitions=2)

    recording.run(scenario)

    assert [trial.number for trial in kept.trials] == [1, 2]


def test_the_observer_starts_afresh_with_every_trial():
    """
    A tick observed in one trial belongs to it alone, and the observer's clock is
    restarted as each trial begins.
    """
    scenario = SortOnePiece()
    kept = TrialsKeptInMemory()
    recording = observing_recording(Episode.from_run(scenario), kept, repetitions=2)
    recording.observer.tick(0.5, [])

    recording.run(scenario)

    assert [len(trial.ticks) for trial in kept.trials] == [1, 0]


def test_the_transcript_is_kept_with_every_trial_asked_so_far(tmp_path, scene):
    """
    Rewritten as each trial finishes rather than once at the end, so a run that dies
    keeps the transcript of the trials it finished.
    """
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)
    kept = TrialsKeptInMemory()
    recording = observing_recording(episode, kept, artifacts=artifacts, repetitions=2)
    recording.observer.ask(scene.question_set, scene.robot, 1.0)

    recording.run(scenario)

    assert (
        artifacts.transcript.read_text()
        == Transcript(episode=episode, trials=kept.trials).render()
    )


def test_the_video_of_every_trial_is_kept_as_one_video(tmp_path):
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)
    film = FilmsEveryTrial()
    recording = observing_recording(
        episode, TrialsKeptInMemory(), artifacts=artifacts, film=film, repetitions=2
    )

    recording.run(scenario)

    assert artifacts.video.stat().st_size > 0
    assert len(recording.video.frames) == film.frames_per_trial * 2


def test_a_run_that_films_nothing_keeps_no_video(tmp_path):
    scenario = SortOnePiece()
    episode = Episode.from_run(scenario)
    artifacts = ArtifactDirectory(path=tmp_path).open_for(episode)

    observing_recording(episode, TrialsKeptInMemory(), artifacts=artifacts).run(
        scenario
    )

    with pytest.raises(ArtifactNotKept):
        artifacts.video


def test_a_run_without_artifacts_records_its_trials_all_the_same():
    scenario = SortOnePiece()
    kept = TrialsKeptInMemory()

    observing_recording(Episode.from_run(scenario), kept, film=FilmsEveryTrial()).run(
        scenario
    )

    assert len(kept.trials) == 1
