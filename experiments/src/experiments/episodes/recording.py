"""
Whether and where a run keeps the trials it finishes.

Recording is best effort: a run whose database will not take a write goes on running and
says so, rather than losing a finished run to a database problem.
:func:`~experiments.montessori.results_database.main` reports the same thing before a
world has been built, where it costs a fraction of a second rather than a minute.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from krrood.ormatic.data_access_objects.helper import to_dao
from krrood.ormatic.data_access_objects.to_dao import ToDataAccessObjectState
from sqlalchemy.orm import Session
from typing_extensions import TYPE_CHECKING, List, Optional, Protocol

from experiments.episodes.artifacts import EpisodeArtifacts, Transcript
from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.observer import EpisodeObserver
from experiments.montessori.results_database import (
    ReadOnlyResultsDatabase,
    ResultsDatabase,
    UnreachableResultsDatabase,
    database_label,
    verify_reachable,
    verify_writable,
)
from experiments.scenarios.runner import ScenarioRunner, ScenarioType
from experiments.scenarios.scenario import WorldType

if TYPE_CHECKING:
    from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo

    from experiments.scenarios.trial import Trial

logger = logging.getLogger(__name__)


class RecordsTrials(Protocol):
    """
    Somewhere a run's finished trials go.
    """

    def record(self, trial: RecordedTrial) -> None:
        """
        Keep one finished trial.
        """

    def close(self) -> None:
        """
        Stop recording, releasing whatever was held open.
        """


@dataclass
class RecordsTrialsToADatabase:
    """
    Keeps every finished trial in a database, one commit each.

    Committed as each trial finishes rather than once at the end, so a run interrupted
    halfway keeps everything it had finished by then.
    """

    session: Session
    """
    The open session trials are committed through.
    """

    conversion_state: ToDataAccessObjectState = field(
        default_factory=ToDataAccessObjectState
    )
    """
    Conversion state shared by every trial of the run.

    It is what keeps an episode one row: a trial converted through it finds the episode
    already converted for the trial before it, rather than making a second one.
    """

    def record(self, trial: RecordedTrial) -> None:
        """
        Commit one finished trial, under the episode it belongs to.

        :param trial: The trial to keep.
        """
        self.session.add(to_dao(trial, self.conversion_state))
        self.session.commit()

    def close(self) -> None:
        """
        Close the session trials were committed through.
        """
        self.session.close()


@dataclass
class RecordsNothing:
    """
    Keeps no trial at all, for a run that would rather run than record.
    """

    def record(self, trial: RecordedTrial) -> None:
        """
        Keep nothing.

        :param trial: The trial that is not kept.
        """

    def close(self) -> None:
        """
        Close nothing.
        """


def open_recording(results_database: ResultsDatabase) -> RecordsTrials:
    """
    Start keeping finished trials, or keep none if the database refuses them.

    Records through the database object it is given rather than one of its own, so
    whatever reads a run's episodes back reads the very rows the run is writing -- which
    for an in-memory database is only true of a shared connection.

    :param results_database: The database to record to.
    :return: A recorder writing to that database, or one keeping nothing when it cannot
        be reached or will not take a write.
    """
    try:
        verify_reachable(results_database.uri)
        verify_writable(results_database.uri)
    except (UnreachableResultsDatabase, ReadOnlyResultsDatabase) as error:
        logger.warning("%s", error)
        logger.warning("Running anyway; this run's episode is not being recorded.")
        return RecordsNothing()
    logger.info("Recording episodes to %s.", database_label(results_database.uri))
    return RecordsTrialsToADatabase(session=results_database.open_session())


# %% a run that records the episode it is making


class FilmsTrials(Protocol):
    """
    Something that films each trial of a run and hands the video over once the trial has
    finished.
    """

    def video_of_the_trial(self) -> RecordedVideo:
        """
        The video of the trial that has just finished.
        """


@dataclass
class EpisodeRecording(ScenarioRunner[ScenarioType, WorldType]):
    """
    A run whose finished trials are kept as the trials of one episode, together with
    what was observed inside them and the artifacts they leave behind.
    """

    episode: Episode = field(kw_only=True)
    """
    The episode this run is making, describing the scenario and conditions it runs
    under.
    """

    records_trials: RecordsTrials = field(default_factory=RecordsNothing, kw_only=True)
    """
    Where each finished trial goes.
    """

    observer: EpisodeObserver = field(default_factory=EpisodeObserver, kw_only=True)
    """
    What collects, inside each trial, what this runner cannot see for itself.
    """

    artifacts: Optional[EpisodeArtifacts] = field(default=None, kw_only=True)
    """
    Where the episode's video and transcript are kept, or None to keep neither.
    """

    film: Optional[FilmsTrials] = field(default=None, kw_only=True)
    """
    What films each trial, or None for a run that is not filmed.
    """

    recorded_trials: List[RecordedTrial] = field(init=False, default_factory=list)
    """
    The trials recorded so far, which is what the transcript is rendered over.
    """

    video: Optional[RecordedVideo] = field(init=False, default=None)
    """
    The video of every filmed trial so far, as one video, or None before the first.
    """

    def trial_started(self, scenario: ScenarioType, world: WorldType) -> None:
        """
        Start the observer's clock with the trial, so its moments and the trial's agree.

        :param scenario: The scenario the trial runs.
        :param world: The world the trial is about to run in.
        """
        self.observer.restart()

    def trial_finished(self, scenario: ScenarioType, trial: Trial) -> None:
        """
        Keep the trial that has just finished as one of this episode's, with everything
        observed inside it, and bring the episode's artifacts up to date.

        The artifacts are rewritten as each trial finishes rather than once at the end,
        for the same reason the trial is committed now: a run that dies keeps what it
        had finished.

        :param scenario: The scenario the trial ran.
        :param trial: The trial that has finished.
        """
        recorded = self.observer.into(RecordedTrial.from_trial(trial, self.episode))
        self.records_trials.record(recorded)
        self.recorded_trials.append(recorded)
        if self.film is not None:
            self._extend_the_video(self.film.video_of_the_trial())
        if self.artifacts is None:
            return
        self.artifacts.keep_transcript(
            Transcript(episode=self.episode, trials=self.recorded_trials)
        )
        if self.video is not None:
            self.artifacts.keep_video(self.video)

    def _extend_the_video(self, filmed: RecordedVideo) -> None:
        """
        Append one trial's video to the episode's.

        :param filmed: The video of the trial that has just finished.
        """
        if self.video is None:
            self.video = filmed
            return
        self.video.frames.extend(filmed.frames)
