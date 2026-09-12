"""
Reading back what the robot's own camera saw at the moment a query was asked.

A run on the robot records its camera beside its rows; a simulated one does not, and
saying so is what lets a card leave the panel out rather than draw an empty one. The one
test that opens a real recording needs the recordings themselves -- gigabytes the
repository does not carry -- so it is skipped wherever they are not on disk, the same way
:mod:`test_montessori_bag_replay` is.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.artifacts import EpisodeArtifact, EpisodeArtifacts
from experiments.episodes.episode import Episode
from experiments.paper.camera_frame import (
    BagFrameAt,
    NoCameraRecordingError,
    RunFile,
)

from .test_montessori_bag_replay import demo_recording

# %% an episode and what it did or did not record

TRIAL_DURATION = 8.0
"""
How long the trial ran, in seconds.
"""

ASKED_AT = 2.0
"""
The moment the query was asked at, in seconds from the start of the trial.
"""


@pytest.fixture
def episode_artifacts(tmp_path: Path) -> EpisodeArtifacts:
    """
    One episode's own directory, holding nothing yet.
    """
    episode = Episode(
        scenario_name="shape_sorting", execution_type=ExecutionType.SIMULATED
    )
    return EpisodeArtifacts(episode=episode, directory=tmp_path / episode.identifier)


def keep_a_recording(artifacts: EpisodeArtifacts) -> Path:
    """
    Put an empty recording where the run would have left one.

    :param artifacts: The episode's own directory.
    :return: The recording's directory.
    """
    bag = artifacts.directory / EpisodeArtifact.RUN_FILES / RunFile.CAMERA_RECORDING
    bag.mkdir(parents=True)
    return bag


# %% a run that recorded no camera


def test_an_episode_without_a_recording_says_so(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A simulated run has no camera to show, which is said rather than left to fail
    wherever the recording would have been read.
    """
    with pytest.raises(NoCameraRecordingError):
        BagFrameAt(
            artifacts=episode_artifacts, moment=ASKED_AT, trial_duration=TRIAL_DURATION
        ).image


def test_the_episode_that_recorded_nothing_is_the_one_named(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    The complaint names the episode and where its recording would have been, so a corpus
    of many runs says which of them is missing one.
    """
    frame = BagFrameAt(
        artifacts=episode_artifacts, moment=ASKED_AT, trial_duration=TRIAL_DURATION
    )
    with pytest.raises(NoCameraRecordingError) as raised:
        frame.recording
    assert raised.value.episode_identifier == episode_artifacts.episode.identifier
    assert raised.value.expected_at == (
        episode_artifacts.directory
        / EpisodeArtifact.RUN_FILES
        / RunFile.CAMERA_RECORDING
    )


def test_a_run_that_recorded_a_camera_is_read_from_it(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    The recording a run left is the one read back, found under the run's own files.
    """
    bag = keep_a_recording(episode_artifacts)
    assert (
        BagFrameAt(
            artifacts=episode_artifacts, moment=ASKED_AT, trial_duration=TRIAL_DURATION
        ).recording
        == bag
    )


# %% where in the recording a moment falls


def test_a_moment_is_read_as_its_share_of_the_trial(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A recording covers the trial, so the moment a query was asked at is that much of the
    way through it.
    """
    assert (
        BagFrameAt(
            artifacts=episode_artifacts, moment=ASKED_AT, trial_duration=TRIAL_DURATION
        ).fraction
        == ASKED_AT / TRIAL_DURATION
    )


def test_a_moment_past_the_end_of_the_trial_is_read_as_its_last_frame(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A query asked as the trial was closing has no frame after it, so it is shown the last
    one there is.
    """
    assert (
        BagFrameAt(
            artifacts=episode_artifacts,
            moment=TRIAL_DURATION * 2,
            trial_duration=TRIAL_DURATION,
        ).fraction
        == 1.0
    )


def test_a_trial_that_took_no_time_is_read_as_its_first_frame(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A trial with no length to divide by is read at its beginning rather than left to
    divide by zero.
    """
    assert (
        BagFrameAt(
            artifacts=episode_artifacts, moment=ASKED_AT, trial_duration=0.0
        ).fraction
        == 0.0
    )


# %% reading a real recording


@pytest.mark.skipif(
    not demo_recording.is_dir(),
    reason=f"{demo_recording} is not in this checkout; recordings are not committed",
)
def test_the_frame_nearest_a_moment_is_the_one_the_recording_holds_there(
    episode_artifacts: EpisodeArtifacts, tmp_path: Path
) -> None:
    """
    The frame read back is a picture of what the camera saw, of the size the camera
    published, and it is written out as one.
    """
    run_files = episode_artifacts.directory / EpisodeArtifact.RUN_FILES
    run_files.mkdir(parents=True)
    (run_files / RunFile.CAMERA_RECORDING).symlink_to(demo_recording)

    frame = BagFrameAt(
        artifacts=episode_artifacts, moment=ASKED_AT, trial_duration=TRIAL_DURATION
    )
    assert frame.image.shape[2] == 3
    written = frame.write(tmp_path / "camera_frame.png")
    assert written.is_file()
