"""
What the robot's own camera saw while a query was being answered.

The panels of a query card only a run on the robot has: a rendered twin shows what the
robot took the scene to be, and these show what it was actually looking at while it took
it to be that -- at the moment the query was asked, or on either side of the event the
query is about.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import Tuple

from experiments.episodes.artifacts import EpisodeArtifact, EpisodeArtifacts
from experiments.episodes.trace import FramesByMoment, TimedFrame
from experiments.paper.chart import TimelineSpan
from experiments.montessori.perception.camera import decode_compressed_color_image
from experiments.montessori.perception.recordings import REFERENCE_FRAME, RecordedCamera
from experiments.paper.lettering import Face, Lettering
from experiments.paper.panel import CardPanel
from semantic_digital_twin.world_description.geometry import Color

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


# %% how the two frames are laid side by side

FRAME_GAP = 8
"""
How many pixels of blank are left between the two frames, so the pair reads as two
pictures rather than one wide one.
"""

CAPTION_HEIGHT = 22
"""
How tall the strip under each frame saying when it was taken is, in pixels.
"""

CAPTION_SIZE = 15
"""
How tall the letters of that caption are, in pixels.
"""

CAPTION_BACKGROUND = Color(0.96, 0.96, 0.97, 1.0)
"""
What the strip under each frame is.
"""

BEFORE_CAPTION = "before, %.1f s"
"""
What is written under the earlier frame, given the second of the trial it was taken at.
"""

AFTER_CAPTION = "after, %.1f s"
"""
What is written under the later frame.
"""


def side_by_side(
    earlier: np.ndarray,
    later: np.ndarray,
    captions: Tuple[str, str],
    gap: int = FRAME_GAP,
    lettering: Lettering = Lettering(size=CAPTION_SIZE, face=Face.REGULAR, inset=6),
) -> np.ndarray:
    """
    Two frames as one picture, the earlier on the left, each with a line under it saying
    when it was taken.

    :param earlier: The earlier frame.
    :param later: The later frame, of the same size.
    :param captions: What is written under the earlier and the later frame.
    :param gap: How many pixels of blank are left between the two.
    :param lettering: How the captions are set.
    :return: The pair, in the channel order the frames came in.
    """
    columns = []
    for frame, caption in zip((earlier, later), captions):
        strip = lettering.band(
            caption, frame.shape[1], CAPTION_HEIGHT, CAPTION_BACKGROUND
        )
        columns.append(np.vstack((frame, strip.astype(frame.dtype))))
    blank = np.full(
        (columns[0].shape[0], gap, columns[0].shape[2]), 255, dtype=earlier.dtype
    )
    return np.hstack((columns[0], blank, columns[1]))


def captions_at(instants: Tuple[float, float]) -> Tuple[str, str]:
    """
    What is written under the earlier and the later frame.

    :param instants: Seconds into the trial each of the two was taken at.
    """
    return (BEFORE_CAPTION % instants[0], AFTER_CAPTION % instants[1])


# %% the two frames either side of a stretch of the trial


@dataclass
class FramesAround(CardPanel, ABC):
    """
    Two frames of the robot's camera, one from just before a stretch of the trial and
    one from just after it, laid side by side.
    """

    over: TimelineSpan
    """
    The stretch of the trial the frames are taken either side of: the seconds
    something happened over.
    """

    @property
    @abstractmethod
    def instants(self) -> Tuple[float, float]:
        """
        Seconds into the trial the earlier and the later frame were taken at, which is
        what a chart of the same trial marks so a reader can find each frame on it.
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


# %% the two frames of a run that kept a bag


@dataclass
class BagFramesAround(FramesAround):
    """
    The colour frames an episode's camera recorded either side of a stretch of the
    trial, written as one picture with the earlier one on the left.

    What makes an event visible rather than only reported: the scene before it and the
    scene after it, from the camera that was actually looking at it.
    """

    artifacts: EpisodeArtifacts
    """
    The episode's own files, among which its camera's recording is kept.
    """

    trial_duration: float
    """
    How long the trial ran, in seconds.
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
        The frame recorded as the stretch began.
        """
        return self._frame_at(self.over.start)

    @property
    def after(self) -> BagFrameAt:
        """
        The frame recorded as the stretch ended.
        """
        return self._frame_at(self.over.end)

    @property
    def instants(self) -> Tuple[float, float]:
        return (self.over.start, self.over.end)

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
        The two frames side by side, in OpenCV's blue, green, red order, each saying
        when it was taken.

        :raises NoCameraRecordingError: When the episode kept no camera recording.
        """
        return side_by_side(
            cv2.cvtColor(self.before.image, cv2.COLOR_BGR2RGB),
            cv2.cvtColor(self.after.image, cv2.COLOR_BGR2RGB),
            captions_at(self.instants),
            self.gap,
        )[:, :, ::-1]

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


# %% the two frames of a run that kept what its camera saw


@dataclass
class RecordedFramesAround(FramesAround):
    """
    The frames a run's own camera took either side of a stretch of the trial, written
    as one picture with the earlier one on the left.

    What a run that kept its camera along the trial -- a simulated one filming the
    camera the twin states, or any run that traced its frames with their moments --
    shows in place of a bag. The earlier frame is the last one taken before the stretch
    began and the later one the first taken after it ended, so a change that took less
    than the time between two frames still shows as one.
    """

    frames: FramesByMoment
    """
    What the camera saw along the trial, asked for by the moment a frame was taken at.
    """

    gap: int = FRAME_GAP
    """
    How many pixels of blank are left between the two frames.
    """

    @property
    def before(self) -> TimedFrame:
        """
        The last frame taken before the stretch began.
        """
        return self.frames.last_at_or_before(self.over.start)

    @property
    def after(self) -> TimedFrame:
        """
        The first frame taken after the stretch ended.
        """
        return self.frames.first_at_or_after(self.over.end)

    @property
    def instants(self) -> Tuple[float, float]:
        return (self.before.moment, self.after.moment)

    @property
    def image(self) -> np.ndarray:
        """
        The two frames side by side, as red, green and blue, each saying when it was
        taken.
        """
        before, after = self.before, self.after
        return side_by_side(
            before.image,
            after.image,
            captions_at((before.moment, after.moment)),
            self.gap,
        )

    def write(self, path: Path) -> Path:
        """
        Leave the pair at the given path.

        :param path: The file it is written to, its directory created if it is not there.
        :return: ``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.image)
        return path
