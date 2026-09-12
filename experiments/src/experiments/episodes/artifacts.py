"""
What an episode keeps outside the database: the video of the run, the files the run
produced, and the transcript of every question it was asked.

The rows say what happened; these are what a reader - or a vision-language model - can
look at. They are addressed by the episode's identifier rather than held in its row, the
same separation :mod:`~experiments.montessori.results_database` already draws between
where a run records and what it records.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from krrood.exceptions import DataclassException
from typing_extensions import TYPE_CHECKING, List, Sequence

from experiments.episodes.episode import Episode, RecordedTrial
from experiments.episodes.trace import JointTrace, TimedFrames, TimedFramesFile

if TYPE_CHECKING:
    from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo

# %% what an episode keeps, and where


class EpisodeArtifact(StrEnum):
    """
    What one episode keeps beside its rows, each under this name in the episode's own
    directory.
    """

    VIDEO = "video.mp4"
    TRANSCRIPT = "transcript.md"
    RUN_FILES = "files"
    """
    Directory holding the files the run itself produced, rather than a file of its own.
    """
    TRIALS = "trials"
    """
    Directory holding what each trial kept of its own, one directory per trial.
    """


class TrialArtifact(StrEnum):
    """
    What one trial keeps of its own, each under this name in the trial's directory.
    """

    JOINT_TRACE = "joints.npz"
    """
    Where every joint stood along the trial.
    """

    CAMERA = "camera.mp4"
    """
    What the robot's camera saw along the trial, with the moments beside it.
    """


ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE = "EPISODE_ARTIFACTS_DIRECTORY"
"""
Environment variable overriding :data:`DEFAULT_ARTIFACT_DIRECTORY` for every run.
"""

DEFAULT_ARTIFACT_DIRECTORY = Path.home() / "episode-artifacts"
"""
Where artifacts are kept when :data:`ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE` is unset.

Configured rather than derived from the results database's own location: the database a
run records to is normally Postgres, which has no filesystem place for a video to sit
beside, so "beside the database" is a relationship between two configured locations.
"""


def configured_artifact_directory() -> Path:
    """
    The directory an episode's artifacts are kept in when a run is not given one.
    """
    from_environment = os.getenv(ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE)
    if from_environment is None:
        return DEFAULT_ARTIFACT_DIRECTORY
    return Path(from_environment)


@dataclass
class ArtifactDirectory:
    """
    Where every episode's artifacts are kept, beside the database holding their rows.
    """

    path: Path = field(default_factory=configured_artifact_directory)
    """
    The directory each episode is given a directory of its own inside.
    """

    def open_for(self, episode: Episode) -> EpisodeArtifacts:
        """
        Start keeping one episode's artifacts, in a directory named after its identifier.

        :param episode: The episode whose artifacts are kept.
        """
        return EpisodeArtifacts(
            episode=episode, directory=self.path / episode.identifier
        )


# %% one episode's own


@dataclass
class ArtifactNotKept(DataclassException):
    """
    Raised when an episode is asked for an artifact it never kept.
    """

    episode_identifier: str
    """
    The episode that was asked.
    """

    artifact: EpisodeArtifact
    """
    The artifact it does not have.
    """

    def error_message(self) -> str:
        return "Episode %s kept no %s." % (self.episode_identifier, self.artifact.name)

    def suggest_correction(self) -> str:
        return (
            "A run keeps its artifacts as it makes them, so an episode recorded before "
            "the run was asked for one has rows but no %s. Check the directory the run "
            "recorded to, which is %s unless the run was given another."
        ) % (self.artifact.value, ARTIFACT_DIRECTORY_ENVIRONMENT_VARIABLE)


@dataclass
class EpisodeArtifacts:
    """
    One episode's video, its own files and its transcript, kept together.

    Made by :meth:`ArtifactDirectory.open_for`, which is what settles where they go.
    """

    episode: Episode
    """
    The run these artifacts are of.
    """

    directory: Path
    """
    Where they are kept, named after the episode's identifier.
    """

    def keep_video(self, video: RecordedVideo) -> Path:
        """
        Encode a recorded run into this episode's video.

        :param video: The frames captured while the run happened.
        :return: The video that was written.
        """
        return video.write(self.directory / EpisodeArtifact.VIDEO)

    def keep_file(self, path: Path) -> Path:
        """
        Take a copy of one file the run produced.

        Copied rather than moved, so the run keeps whatever it is still writing to and an
        episode's own copy outlives it.

        :param path: The file the run produced.
        :return: The copy this episode keeps.
        """
        run_files = self.directory / EpisodeArtifact.RUN_FILES
        run_files.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copy2(path, run_files / path.name))

    def keep_directory(self, path: Path) -> Path:
        """
        Take a copy of one directory the run produced, with everything in it.

        What a recording that is a directory of files, such as a bag, is kept as: one
        run file holding all of them.

        :param path: The directory the run produced.
        :return: The copy this episode keeps.
        """
        run_files = self.directory / EpisodeArtifact.RUN_FILES
        run_files.mkdir(parents=True, exist_ok=True)
        return Path(shutil.copytree(path, run_files / path.name))

    def keep_transcript(self, transcript: Transcript) -> Path:
        """
        Render this episode's questions and answers into one readable document.

        :param transcript: What the run was asked and what it answered.
        :return: The transcript that was written.
        """
        written = self.directory / EpisodeArtifact.TRANSCRIPT
        written.parent.mkdir(parents=True, exist_ok=True)
        written.write_text(transcript.render())
        return written

    def trial(self, number: int) -> TrialArtifacts:
        """
        What one trial of this episode keeps of its own.

        :param number: Which trial, counted from one in the order they ran.
        """
        return TrialArtifacts(
            episode=self.episode,
            number=number,
            directory=self.directory / EpisodeArtifact.TRIALS / str(number),
        )

    @property
    def video(self) -> Path:
        """
        The video of this episode's run.

        :raises ArtifactNotKept: When the run kept no video.
        """
        return self._kept(EpisodeArtifact.VIDEO)

    @property
    def transcript(self) -> Path:
        """
        The document holding every question this episode was asked, with its answer.

        :raises ArtifactNotKept: When the run kept no transcript.
        """
        return self._kept(EpisodeArtifact.TRANSCRIPT)

    @property
    def run_files(self) -> List[Path]:
        """
        The files the run itself produced, in name order.

        Empty for a run that produced none, which is a run with nothing to keep rather
        than an episode missing something - unlike the video and the transcript, these are
        a collection.
        """
        run_files = self.directory / EpisodeArtifact.RUN_FILES
        if not run_files.is_dir():
            return []
        return sorted(run_files.iterdir())

    def _kept(self, artifact: EpisodeArtifact) -> Path:
        """
        One of this episode's single-file artifacts, insisting it is actually there.

        :param artifact: The artifact to find.
        :raises ArtifactNotKept: When it was never kept.
        """
        path = self.directory / artifact
        if not path.is_file():
            raise ArtifactNotKept(
                episode_identifier=self.episode.identifier, artifact=artifact
            )
        return path


# %% what one trial keeps of its own


@dataclass
class TrialArtifactNotKept(DataclassException):
    """
    Raised when a trial is asked for something it never kept.
    """

    episode_identifier: str
    """
    The episode the trial belongs to.
    """

    number: int
    """
    Which trial was asked, counted from one.
    """

    artifact: TrialArtifact
    """
    What it does not have.
    """

    def error_message(self) -> str:
        return "Trial %d of episode %s kept no %s." % (
            self.number,
            self.episode_identifier,
            self.artifact.name,
        )

    def suggest_correction(self) -> str:
        return (
            "A run keeps a trial's trace and camera as the trial goes, so a trial "
            "without them was recorded by a run that was not asked to trace it."
        )


@dataclass
class TrialArtifacts:
    """
    What one trial of an episode keeps of its own: where its joints stood and what
    its camera saw, along its seconds.

    Made by :meth:`EpisodeArtifacts.trial`, which is what settles where they go.
    """

    episode: Episode
    """
    The run the trial belongs to.
    """

    number: int
    """
    Which trial this is, counted from one in the order they ran.
    """

    directory: Path
    """
    Where the trial's own files are kept.
    """

    def keep_joint_trace(self, trace: JointTrace) -> Path:
        """
        Keep where every joint stood along the trial.

        :param trace: The trace the run took.
        :return: The file it was written to.
        """
        return trace.write(self.directory / TrialArtifact.JOINT_TRACE)

    def keep_camera(self, frames: TimedFrames) -> Path:
        """
        Keep what the robot's camera saw along the trial.

        :param frames: The frames the run took, with their moments.
        :return: The video they were written to.
        """
        return frames.write(self.directory / TrialArtifact.CAMERA)

    @property
    def kept_a_joint_trace(self) -> bool:
        """
        Whether the run traced the trial's joints.
        """
        return (self.directory / TrialArtifact.JOINT_TRACE).is_file()

    @property
    def kept_a_camera(self) -> bool:
        """
        Whether the run kept what the robot's camera saw.
        """
        return (self.directory / TrialArtifact.CAMERA).is_file()

    @property
    def joint_trace(self) -> JointTrace:
        """
        Where every joint stood along the trial.

        :raises TrialArtifactNotKept: When the run traced no joints.
        """
        return JointTrace.read(self._kept(TrialArtifact.JOINT_TRACE))

    @property
    def camera(self) -> TimedFramesFile:
        """
        What the robot's camera saw along the trial, read a frame at a time.

        :raises TrialArtifactNotKept: When the run kept no camera.
        """
        return TimedFramesFile(self._kept(TrialArtifact.CAMERA))

    def _kept(self, artifact: TrialArtifact) -> Path:
        """
        One of this trial's files, insisting it is actually there.

        :param artifact: The artifact to find.
        :raises TrialArtifactNotKept: When it was never kept.
        """
        path = self.directory / artifact
        if not path.is_file():
            raise TrialArtifactNotKept(
                episode_identifier=self.episode.identifier,
                number=self.number,
                artifact=artifact,
            )
        return path


# %% what the run was asked, as one document


@dataclass
class Transcript:
    """
    Every question one episode was asked, with the answer it gave.

    Rendered from the same queries the trials' rows carry, so a reader and a query over
    the database are shown the same exchange.
    """

    episode: Episode
    """
    The run being transcribed.
    """

    trials: Sequence[RecordedTrial]
    """
    Its trials, in the order they ran.
    """

    def render(self) -> str:
        """
        This transcript as one readable document.
        """
        lines = [
            "# Episode %s" % self.episode.identifier,
            "",
            "- Scenario: %s" % self.episode.scenario_name,
            "- Ran: %s" % self.episode.execution_type.value,
            "- Recorded at: %s" % self.episode.recorded_at.isoformat(),
        ]
        for number, trial in enumerate(self.trials, start=1):
            lines.extend(["", "## Trial %d" % number, ""])
            lines.extend(self._questions_of(trial))
        return "\n".join(lines) + "\n"

    @staticmethod
    def _questions_of(trial: RecordedTrial) -> List[str]:
        """
        One trial's exchange, as the lines it is rendered on.

        :param trial: The trial to read the questions off.
        """
        if not trial.queries:
            return ["No questions were asked."]
        lines = []
        for query in trial.queries:
            lines.extend(
                [
                    "**Q** (%.2f s) %s" % (query.moment, query.text),
                    "**A** (%.3f s) %s" % (query.latency, query.answer),
                    "",
                ]
            )
        return lines[:-1]
