"""
Reading back what the robot's own camera saw at the moment a query was asked.

A run on the robot records its camera beside its rows; a simulated one does not, and
saying so is what lets a card leave the panel out rather than draw an empty one. The
frame is found by the stamp the recording wrote it under, read off the trial's own
clock, so what is asserted here is read off a small recording written at known moments.
The one test that opens a real recording needs the recordings themselves -- gigabytes
the repository does not carry -- so it is skipped wherever they are not on disk, the
same way :mod:`test_montessori_bag_replay` is.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from coraplex.datastructures.enums import ExecutionType

from experiments.episodes.artifacts import EpisodeArtifacts, RunFile
from experiments.episodes.episode import Episode
from experiments.montessori.perception.recordings import REFERENCE_FRAME, RecordedCamera
from experiments.paper.camera_frame import BagFrameAt, NoCameraRecordingError
from experiments.paper.run_plan import NANOSECONDS_PER_SECOND, TrialClock

from .test_montessori_bag_replay import demo_recording
from .test_montessori_recorded_camera import (
    A_SECOND,
    FRAMES_TAKEN,
    RECORDING_BEGAN_AT,
    shade_of,
    write_recording,
)

# %% an episode and what it did or did not record

ASKED_AT = 2.0
"""
The moment the query was asked at, in seconds from the start of the trial.
"""

TRIAL_BEGAN_AT = datetime.fromtimestamp(RECORDING_BEGAN_AT / NANOSECONDS_PER_SECOND)
"""
When the trial began on the wall clock: the instant the recording wrote its first frame
under.
"""

CLOCK = TrialClock(origin=TRIAL_BEGAN_AT)
"""
The trial's clock, starting with the recording.
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
    bag = artifacts.run_file(RunFile.CAMERA_RECORDING)
    bag.mkdir(parents=True)
    return bag


def keep_the_frames_taken(artifacts: EpisodeArtifacts, tmp_path: Path) -> None:
    """
    Leave the recording of :data:`FRAMES_TAKEN` as the episode's camera recording.

    :param artifacts: The episode's own directory.
    :param tmp_path: Where the recording is written before the episode keeps it.
    """
    artifacts.keep_camera_recording(
        write_recording(tmp_path / "recording", FRAMES_TAKEN)
    )


def frame_at(artifacts: EpisodeArtifacts, moment: float, clock: TrialClock = CLOCK):
    """
    The frame the episode's camera recorded nearest a moment of the trial.
    """
    return BagFrameAt(artifacts=artifacts, moment=moment, clock=clock)


def shade_shown(artifacts: EpisodeArtifacts, moment: float, clock: TrialClock = CLOCK):
    """
    The one shade of the flat frame shown for a moment of the trial.
    """
    return shade_of(frame_at(artifacts, moment, clock).image)


# %% a run that recorded no camera


def test_an_episode_without_a_recording_says_so(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A simulated run has no camera to show, which is said rather than left to fail
    wherever the recording would have been read.
    """
    with pytest.raises(NoCameraRecordingError):
        frame_at(episode_artifacts, ASKED_AT).image


def test_the_episode_that_recorded_nothing_is_the_one_named(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    The complaint names the episode and where its recording would have been, so a corpus
    of many runs says which of them is missing one.
    """
    frame = frame_at(episode_artifacts, ASKED_AT)
    with pytest.raises(NoCameraRecordingError) as raised:
        frame.recording
    assert raised.value.episode_identifier == episode_artifacts.episode.identifier
    assert raised.value.expected_at == episode_artifacts.run_file(
        RunFile.CAMERA_RECORDING
    )


def test_a_run_that_recorded_a_camera_is_read_from_it(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    The recording a run left is the one read back, found under the run's own files.
    """
    bag = keep_a_recording(episode_artifacts)
    assert frame_at(episode_artifacts, ASKED_AT).recording == bag


# %% which frame a moment of the trial is shown


def test_a_moment_is_asked_for_by_the_stamp_the_recording_wrote_it_under(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    The recording stamps its frames on the wall clock and the trial counts its seconds
    from an instant of that clock, so a moment of the trial names one stamp.
    """
    assert frame_at(episode_artifacts, ASKED_AT).stamp == CLOCK.stamp_of(ASKED_AT)


def test_the_frame_shown_is_the_one_recorded_at_that_moment(
    episode_artifacts: EpisodeArtifacts, tmp_path: Path
) -> None:
    keep_the_frames_taken(episode_artifacts, tmp_path)
    for frame in FRAMES_TAKEN:
        assert (
            shade_shown(episode_artifacts, CLOCK.seconds_of_stamp(frame.stamp))
            == frame.shade
        )


def test_a_trial_that_began_before_its_recording_opened_shows_the_first_frame_first(
    episode_artifacts: EpisodeArtifacts, tmp_path: Path
) -> None:
    """
    A run starts its trial's clock and then opens its bag, which waits for the topics to
    appear, so the trial's first moments come before the recording's first frame and are
    shown it rather than a place the recording does not reach.
    """
    keep_the_frames_taken(episode_artifacts, tmp_path)
    began_a_second_before = TrialClock(
        origin=datetime.fromtimestamp(
            (RECORDING_BEGAN_AT - A_SECOND) / NANOSECONDS_PER_SECOND
        )
    )

    assert (
        shade_shown(episode_artifacts, 0.0, began_a_second_before)
        == FRAMES_TAKEN[0].shade
    )


def test_a_moment_past_the_end_of_the_recording_is_shown_its_last_frame(
    episode_artifacts: EpisodeArtifacts, tmp_path: Path
) -> None:
    """
    A query asked as the trial was closing has no frame after it, so it is shown the last
    one there is.
    """
    keep_the_frames_taken(episode_artifacts, tmp_path)
    after_the_last = CLOCK.seconds_of_stamp(FRAMES_TAKEN[-1].stamp + A_SECOND)

    assert shade_shown(episode_artifacts, after_the_last) == FRAMES_TAKEN[-1].shade


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
    bag = episode_artifacts.run_file(RunFile.CAMERA_RECORDING)
    bag.parent.mkdir(parents=True)
    bag.symlink_to(demo_recording)
    began_with_the_recording = TrialClock(
        origin=datetime.fromtimestamp(
            RecordedCamera(bag=bag, reference_frame=REFERENCE_FRAME).colour_stamps()[0]
            / NANOSECONDS_PER_SECOND
        )
    )

    frame = frame_at(episode_artifacts, ASKED_AT, began_with_the_recording)
    assert frame.image.shape[2] == 3
    written = frame.write(tmp_path / "camera_frame.png")
    assert written.is_file()
