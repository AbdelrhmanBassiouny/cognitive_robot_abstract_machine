"""
What the robot's own camera saw at the moment a query was asked.

The third panel of a query card, and the one only a run on the robot has: a rendered twin
shows what the robot took the scene to be, and this shows what it was actually looking at
while it took it to be that.
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
    def recording(self) -> Path:
        """
        The directory the run left its camera's recording in.

        :raises NoCameraRecordingError: When the episode kept none.
        """
        bag = (
            self.artifacts.directory
            / EpisodeArtifact.RUN_FILES
            / RunFile.CAMERA_RECORDING
        )
        if not bag.is_dir():
            raise NoCameraRecordingError(
                episode_identifier=self.artifacts.episode.identifier, expected_at=bag
            )
        return bag

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
