"""
What the run's camera saw while a query was being answered.

The panels of a query card that show the run rather than the answer: a rendered twin
shows what the robot took the scene to be, and these show what it was actually looking
at while it took it to be that -- at the moment the query was asked, or on either side
of the event the query is about. A run on the robot recorded its camera; a run in
simulation is shown as the twin stood at those moments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import cv2
import imageio.v2 as imageio
import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import Optional, Tuple

from experiments.episodes.artifacts import EpisodeArtifacts, RunFile
from experiments.episodes.trace import (
    FramesByMoment,
    JointTrace,
    TimedFrame,
    standing_at,
)
from experiments.paper.chart import TimelineSpan
from experiments.montessori.perception.camera import decode_compressed_color_image
from experiments.montessori.perception.recordings import REFERENCE_FRAME, RecordedCamera
from experiments.paper.lettering import Face, Lettering
from experiments.paper.panel import CardPanel
from experiments.paper.run_plan import TrialClock
from experiments.paper.scene import SceneRender
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.adapters.picture import Viewpoint
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.geometry import Color

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
    The stretch of the trial the frames are taken either side of: the seconds something
    happened over.
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
            "Only a run on the robot records its camera; a simulated episode is shown "
            "as the twin stood along its joint trace instead, or without that panel "
            "where it traced none."
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

    clock: TrialClock
    """
    Where the trial's seconds start on the wall clock, which is what turns a moment of
    it into the stamp the recording wrote the frame under.
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
        return self.artifacts.run_file(RunFile.CAMERA_RECORDING)

    @property
    def was_recorded(self) -> bool:
        """
        Whether the episode kept a camera recording to read a frame out of, which is
        what lets a card leave the panel out rather than fail on it.
        """
        return self.artifacts.kept_a_camera_recording

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
    def stamp(self) -> int:
        """
        The moment as the recording stamps it: nanoseconds since the epoch on the wall
        clock the trial began on.
        """
        return self.clock.stamp_of(self.moment)

    @property
    def image(self) -> np.ndarray:
        """
        The colour image the camera published nearest the moment, in OpenCV's blue,
        green, red order.

        A moment the recording does not reach -- the trial's first seconds where the
        recording opened after the trial began, or its last where it closed before the
        trial ended -- is shown the nearest frame the recording holds.

        :raises NoCameraRecordingError: When the episode kept no camera recording.
        :raises NothingRecordedOnTopic: When the recording holds no colour image a depth
            image was published before.
        """
        recorded = RecordedCamera(
            bag=self.recording, reference_frame=self.reference_frame
        ).image_nearest(self.stamp)
        return decode_compressed_color_image(
            recorded.color_payload, recorded.color_format
        )

    def write(self, path: Path) -> Path:
        """
        Leave this frame at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
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

    clock: TrialClock
    """
    Where the trial's seconds start on the wall clock the recording stamps its frames
    on.
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

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        :raises NoCameraRecordingError: When the episode kept no camera recording.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB))
        return path

    def _frame_at(self, moment: float) -> BagFrameAt:
        """
        One of the pair, read out of the same recording as the other.

        :param moment: Seconds into the trial the frame is wanted for, which the frame
            itself reads as the nearest end of the recording where the recording does
            not reach it.
        """
        return BagFrameAt(
            artifacts=self.artifacts,
            moment=moment,
            clock=self.clock,
            reference_frame=self.reference_frame,
        )


# %% the two frames of a run that kept what its camera saw


@dataclass
class RecordedFramesAround(FramesAround):
    """
    The frames a run's own camera took either side of a stretch of the trial, written as
    one picture with the earlier one on the left.

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

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.image)
        return path


# %% the frame of a run that kept what its camera saw


@dataclass
class RecordedFrameAt(CardPanel):
    """
    The frame a run's own camera took nearest one moment of the trial.
    """

    frames: FramesByMoment
    """
    What the camera saw along the trial, asked for by the moment a frame was taken at.
    """

    moment: float
    """
    Seconds into the trial the frame is wanted for.
    """

    @property
    def image(self) -> np.ndarray:
        """
        The frame taken nearest the moment, as red, green and blue.
        """
        return self.frames.at(self.moment)

    def write(self, path: Path) -> Path:
        """
        Leave this frame at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        imageio.imwrite(str(path), self.image)
        return path


# %% the frames of a run in simulation, drawn from the twin


@dataclass
class TwinFrames(FramesByMoment):
    """
    What a run in simulation showed along the trial, drawn from the twin stood at each
    sample of the run's joint trace.

    A run in simulation has no camera to record, but it traced where every joint stood,
    and the twin put back there is the scene as the run showed it at that moment. Each
    frame is drawn when it is asked for.
    """

    world: World
    """
    The twin the run happened in, which is stood at each sample and put back afterwards.
    """

    trace: JointTrace
    """
    Where every joint stood along the trial.
    """

    camera: Optional[MujocoCamera] = None
    """
    The camera the run's robot looks through, as the twin states it on the robot, or
    None to draw the frames from an overview of the whole scene.

    Each frame is drawn from where the camera stands once the twin is stood at that
    sample, since the camera moves with the body it hangs on.
    """

    def moments_taken(self) -> np.ndarray:
        return np.array(self.trace.moments, dtype=float)

    def frame(self, index: int) -> np.ndarray:
        with standing_at(self.world, self.trace.at(self.trace.moments[index])) as world:
            viewpoint = (
                Viewpoint.through(self.camera, world)
                if self.camera is not None
                else None
            )
            return (
                SceneRender(world=world, viewpoint=viewpoint, label_answers=False)
                .of([])
                .image
            )
