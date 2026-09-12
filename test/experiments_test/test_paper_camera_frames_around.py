"""
What the robot's camera saw on either side of an event, as one picture.

The panel that says an event was really seen rather than only reported: the scene a
moment before it and the scene a moment after, side by side, so a reader can tell that
the piece really did end up in the gripper.

Only a run on the robot records a camera, so everything here that needs actual frames is
skipped wherever the recordings are not on disk, the same way
:mod:`test_paper_camera_frame` is.
"""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest

from experiments.episodes.artifacts import EpisodeArtifact, EpisodeArtifacts
from experiments.episodes.trace import TimedFrames
from experiments.paper.camera_frame import (
    CAPTION_HEIGHT,
    BagFrameAt,
    BagFramesAround,
    NoCameraRecordingError,
    RecordedFramesAround,
    RunFile,
    captions_at,
)
from experiments.paper.chart import TimelineSpan

from .test_montessori_bag_replay import demo_recording
from .test_paper_camera_frame import (
    ASKED_AT,
    TRIAL_DURATION,
    episode_artifacts,
    keep_a_recording,
)

# %% the stretch the pair is taken either side of

MOVED_FOR = 2.0
"""
How long the object was moving, in seconds.
"""

MOVED_OVER = TimelineSpan(ASKED_AT, MOVED_FOR)
"""
The stretch of the trial the object moved over.
"""


def pair(
    artifacts: EpisodeArtifacts, over: TimelineSpan = MOVED_OVER
) -> BagFramesAround:
    """
    The pair of frames this test reads either side of a stretch of the trial.

    :param artifacts: The episode's own directory.
    :param over: The stretch the object moved over.
    """
    return BagFramesAround(
        over=over, artifacts=artifacts, trial_duration=TRIAL_DURATION
    )


def test_the_two_frames_are_taken_either_side_of_the_event(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    The point of the pair is the change across the stretch, so one frame is taken as it
    began and the other as it ended.
    """
    either_side = pair(episode_artifacts)
    assert (either_side.before.moment, either_side.after.moment) == (
        MOVED_OVER.start,
        MOVED_OVER.end,
    )
    assert either_side.instants == (MOVED_OVER.start, MOVED_OVER.end)


def test_each_frame_reads_the_same_recording_as_the_pair(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    Both frames come out of the one recording the run left, read the same way a single
    frame of the same card is.
    """
    either_side = pair(episode_artifacts)
    assert isinstance(either_side.before, BagFrameAt)
    assert either_side.before.expected_at == either_side.expected_at
    assert either_side.after.trial_duration == TRIAL_DURATION


def test_an_event_at_the_very_start_is_still_shown_from_the_beginning(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    An event in the first moments of a run has no second before it, so the frame before
    it is the first one the camera recorded rather than a place the recording does not
    reach.
    """
    assert pair(episode_artifacts, TimelineSpan(0.0, MOVED_FOR)).before.fraction == 0.0


def test_an_event_at_the_very_end_is_still_shown_to_the_end(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    An event in the last moments of a run has no second after it either.
    """
    assert (
        pair(episode_artifacts, TimelineSpan(TRIAL_DURATION, MOVED_FOR)).after.fraction
        == 1.0
    )


# %% a run that recorded no camera


def test_a_run_that_recorded_no_camera_says_so(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A simulated run records no camera, which is what lets a card leave this panel out
    rather than fail on it.
    """
    assert not pair(episode_artifacts).was_recorded


def test_a_run_that_recorded_one_is_read_from_it(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    A run on the robot leaves its recording among its own files, which is where the pair
    looks for it.
    """
    keep_a_recording(episode_artifacts)
    assert pair(episode_artifacts).was_recorded


def test_asking_a_run_that_recorded_no_camera_for_the_pair_raises(
    episode_artifacts: EpisodeArtifacts,
) -> None:
    """
    Asked for the picture anyway, a run that recorded nothing says what is missing and
    where it would have been.
    """
    with pytest.raises(NoCameraRecordingError):
        pair(episode_artifacts).image


# %% the picture the two make


@pytest.mark.skipif(
    not demo_recording.is_dir(),
    reason=f"{demo_recording} is not in this checkout; recordings are not committed",
)
def test_the_two_frames_are_written_side_by_side(
    episode_artifacts: EpisodeArtifacts, tmp_path: Path
) -> None:
    """
    The pair is one figure of the paper rather than two, so the two frames are written
    as one picture with the earlier one on the left.
    """
    run_files = episode_artifacts.directory / EpisodeArtifact.RUN_FILES
    run_files.mkdir(parents=True)
    (run_files / RunFile.CAMERA_RECORDING).symlink_to(demo_recording)
    either_side = pair(episode_artifacts)

    written = either_side.write(tmp_path / "either_side.png")

    side_by_side = imageio.imread(written)
    one = either_side.before.image
    assert side_by_side.shape[0] == one.shape[0] + CAPTION_HEIGHT
    assert side_by_side.shape[1] == 2 * one.shape[1] + either_side.gap


# %% the two frames of a run that kept what its camera saw

FRAME_SIDE = 24
"""
Pixel width and height of the frames kept here.
"""


def kept_frames() -> TimedFrames:
    """
    What a camera saw at every whole second of a trial, each frame one flat shade
    numbered by its second.
    """
    frames = TimedFrames()
    for second in range(int(TRIAL_DURATION) + 1):
        frames.keep(
            np.full((FRAME_SIDE, FRAME_SIDE, 3), second * 10, dtype=np.uint8),
            float(second),
        )
    return frames


def test_the_two_frames_of_a_kept_camera_are_taken_either_side_of_the_stretch() -> None:
    either_side = RecordedFramesAround(over=MOVED_OVER, frames=kept_frames())

    assert either_side.before.image[0, 0, 0] == round(MOVED_OVER.start) * 10
    assert either_side.after.image[0, 0, 0] == round(MOVED_OVER.end) * 10


def test_the_frames_are_the_last_before_the_stretch_and_the_first_after_it() -> None:
    """
    A change that took less than the time between two frames still shows as one: the
    earlier frame is the last taken before it began, the later the first taken after it
    ended, and the pair says the instants those frames were actually taken at.
    """
    within_a_second = TimelineSpan(ASKED_AT + 0.25, 0.5)
    either_side = RecordedFramesAround(over=within_a_second, frames=kept_frames())

    assert either_side.instants == (ASKED_AT, ASKED_AT + 1.0)
    assert either_side.before.image[0, 0, 0] == round(ASKED_AT) * 10
    assert either_side.after.image[0, 0, 0] == round(ASKED_AT + 1.0) * 10


def test_the_two_frames_of_a_kept_camera_differ_when_the_camera_saw_a_change() -> None:
    """
    The pair exists to show a change, so with a camera that saw one the two frames it
    hands back are not the same picture.
    """
    either_side = RecordedFramesAround(over=MOVED_OVER, frames=kept_frames())

    assert not np.array_equal(either_side.before.image, either_side.after.image)


def test_each_frame_of_the_pair_says_when_it_was_taken() -> None:
    """
    A reader is told which frame is which and at what second of the trial each was
    taken, rather than left to guess.
    """
    before, after = captions_at((MOVED_OVER.start, MOVED_OVER.end))

    assert before == "before, %.1f s" % MOVED_OVER.start
    assert after == "after, %.1f s" % MOVED_OVER.end


def test_the_kept_frames_are_written_side_by_side_with_their_captions(
    tmp_path: Path,
) -> None:
    either_side = RecordedFramesAround(over=MOVED_OVER, frames=kept_frames())

    written = imageio.imread(either_side.write(tmp_path / "either_side.png"))

    assert written.shape[0] == FRAME_SIDE + CAPTION_HEIGHT
    assert written.shape[1] == 2 * FRAME_SIDE + either_side.gap
