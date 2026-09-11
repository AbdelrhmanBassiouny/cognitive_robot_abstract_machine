"""
What the robot's own camera saw while a query was being answered.

The panels of a query card only a run on the robot has: a rendered twin shows what the
robot took the scene to be, and these show what it was actually looking at while it took
it to be that -- at the moment the query was asked, or on either side of the event the
query is about.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from krrood.exceptions import DataclassException

from experiments.episodes.artifacts import EpisodeArtifact, EpisodeArtifacts
from experiments.montessori.perception.camera import decode_compressed_color_image
from experiments.montessori.perception.recordings import REFERENCE_FRAME, RecordedCamera
from experiments.paper.panel import CardPanel

# %% what a run leaves its camera in


class RunFile(StrEnum):
    """
    What a run leaves among its own files that a query card reads back, named as the run
    writes it.
    """

    CAMERA_RECORDING = "bag"
    """
    Directory of the recording the robot's camera published into.
    """


# %% how far either side of an event its two frames are taken

EITHER_SIDE = 1.0
"""
How far either side of an event the two frames showing it are taken, in seconds.

Far enough that the earlier frame is genuinely before the change and the later one
genuinely shows it, close enough that nothing else about the scene has moved on.
"""

FRAME_GAP = 8
"""
How many pixels of blank are left between the two frames, so the pair reads as two
pictures rather than one wide one.
"""


# %% asking a run that recorded no camera


@dataclass
class NoCameraRecordingError(DataclassException):
    """
    Raised when an episode is asked what its camera saw and it recorded none.
    """

    episode_identifier: str
    """
    The episode that was asked.
    """

    expected_at: Path
    """
    Where its camera's recording would be if it had kept one.
    """

    def error_message(self) -> str:
        return "Episode %s kept no camera recording at %s." % (
            self.episode_identifier,
            self.expected_at,
        )

    def suggest_correction(self) -> str:
        return (
            "Only a run on the robot records its camera, so a simulated episode has no "
            "camera frame to show and its cards are drawn without that panel."
        )


# %% the frame itself


@dataclass
class BagFrameAt(CardPanel):
    """
    The colour frame an episode's camera recorded nearest one moment of its trial.
    """

    artifacts: EpisodeArtifacts
    """
    The episode's own files, among which its camera's recording is kept.
    """

    moment: float
    """
    Seconds between the start of the trial and the moment the frame is wanted for.
    """

    trial_duration: float
    """
    How long the trial ran, in seconds, which is what turns a moment of it into a place
    in the recording.
    """

    reference_frame: str = REFERENCE_FRAME
    """
    The frame the camera's pose is read in.
    """

    @property
    def expected_at(self) -> Path:
        """
        Where the run's camera recording is kept, whether or not it kept one.
        """
        return (
            self.artifacts.directory
            / EpisodeArtifact.RUN_FILES
            / RunFile.CAMERA_RECORDING
        )

    @property
    def was_recorded(self) -> bool:
        """
        Whether the episode kept a camera recording to read a frame out of, which is
        what lets a card leave the panel out rather than fail on it.
        """
        return self.expected_at.is_dir()

    @property
    def recording(self) -> Path:
        """
        The directory the run left its camera's recording in.

        :raises NoCameraRecordingError: When the episode kept none.
        """
        if not self.was_recorded:
            raise NoCameraRecordingError(
                episode_identifier=self.artifacts.episode.identifier,
                expected_at=self.expected_at,
            )
        return self.expected_at

    @property
    def fraction(self) -> float:
        """
        How far through the recording the moment falls, from 0 at its first frame to 1 at
        its last.

        A moment outside the trial is read as its nearest end rather than as a place the
        recording does not reach, and a trial that took no time at all is read as its
        first frame.
        """
        if self.trial_duration <= 0.0:
            return 0.0
        return min(max(self.moment / self.trial_duration, 0.0), 1.0)

    @property
    def image(self) -> np.ndarray:
        """
        The colour image the camera published nearest the moment, in OpenCV's blue,
        green, red order.

        :raises NoCameraRecordingError: When the episode kept no camera recording.
        :raises NothingRecordedOnTopic: When the recording holds no colour image a depth
            image was published before.
        """
        recorded = RecordedCamera(
            bag=self.recording, reference_frame=self.reference_frame
        ).image_at(self.fraction)
        return decode_compressed_color_image(
            recorded.color_payload, recorded.color_format
        )

    def write(self, path: Path) -> Path:
        """
        Leave this frame at the given path.

        :param path: The file it is written to, its directory created if it is not there.
        :return: ``path``.
        :raises NoCameraRecordingError: When the episode kept no camera recording.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))
        return path


# %% the two frames either side of an event


@dataclass
class BagFramesAround(CardPanel):
    """
    The colour frames an episode's camera recorded either side of one moment, written as
    one picture with the earlier one on the left.

    What makes an event visible rather than only reported: the scene before it and the
    scene after it, from the camera that was actually looking at it.
    """

    artifacts: EpisodeArtifacts
    """
    The episode's own files, among which its camera's recording is kept.
    """

    moment: float
    """
    Seconds between the start of the trial and the event the frames are taken around.
    """

    trial_duration: float
    """
    How long the trial ran, in seconds.
    """

    either_side: float = EITHER_SIDE
    """
    How far either side of the moment the two frames are taken, in seconds.
    """

    gap: int = FRAME_GAP
    """
    How many pixels of blank are left between the two frames.
    """

    reference_frame: str = REFERENCE_FRAME
    """
    The frame the camera's pose is read in.
    """

    @property
    def before(self) -> BagFrameAt:
        """
        The frame recorded before the event.
        """
        return self._frame_at(self.moment - self.either_side)

    @property
    def after(self) -> BagFrameAt:
        """
        The frame recorded after the event.
        """
        return self._frame_at(self.moment + self.either_side)

    @property
    def expected_at(self) -> Path:
        """
        Where the run's camera recording is kept, whether or not it kept one.
        """
        return self.before.expected_at

    @property
    def was_recorded(self) -> bool:
        """
        Whether the episode kept a camera recording to read the two frames out of.
        """
        return self.before.was_recorded

    @property
    def image(self) -> np.ndarray:
        """
        The two frames side by side, in OpenCV's blue, green, red order.

        :raises NoCameraRecordingError: When the episode kept no camera recording.
        """
        earlier = self.before.image
        later = self.after.image
        blank = np.zeros(
            (earlier.shape[0], self.gap, earlier.shape[2]), dtype=earlier.dtype
        )
        return np.hstack((earlier, blank, later))

    def write(self, path: Path) -> Path:
        """
        Leave the pair at the given path.

        :param path: The file it is written to, its directory created if it is not there.
        :return: ``path``.
        :raises NoCameraRecordingError: When the episode kept no camera recording.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))
        return path

    def _frame_at(self, moment: float) -> BagFrameAt:
        """
        One of the pair, read out of the same recording as the other.

        :param moment: Seconds into the trial the frame is wanted for, which the frame
            itself reads as the nearest end of the recording where it falls outside the
            trial.
        """
        return BagFrameAt(
            artifacts=self.artifacts,
            moment=moment,
            trial_duration=self.trial_duration,
            reference_frame=self.reference_frame,
        )
