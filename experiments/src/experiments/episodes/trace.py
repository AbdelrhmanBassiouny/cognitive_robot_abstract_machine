"""
What a run kept of its world as it went: where every joint stood, and what a camera saw,
sampled along the seconds of a trial.

The rows of a trial say what happened and when; these say what the world looked like
while it did, so a moment of the trial can be put back in front of a reader -- the robot
in the pose it was in, the camera showing what it showed -- rather than described.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from krrood.exceptions import DataclassException
from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo
from semantic_digital_twin.callbacks.callback import StateChangeCallback
from semantic_digital_twin.world import World
from typing_extensions import Callable, Dict, List, Optional, Self

# %% asking a trace for a moment it holds nothing of


@dataclass
class TraceIsEmptyError(DataclassException):
    """
    Raised when a trace that holds no sample is asked what it held at some moment.
    """

    moment: float
    """
    Seconds into the trial that was asked for.
    """

    def error_message(self) -> str:
        return "Nothing was traced, so there is no sample nearest %.2f s." % self.moment

    def suggest_correction(self) -> str:
        return (
            "A trace is filled by sampling the world while the trial runs; a trial that "
            "sampled nothing has nothing to put back."
        )


def nearest(moments: np.ndarray, moment: float) -> int:
    """
    Which of the given moments is closest to the one asked for.

    :param moments: Seconds into the trial each sample was taken at, in the order they
        were taken.
    :param moment: Seconds into the trial that is asked for.
    :raises TraceIsEmptyError: If there is no sample at all.
    """
    if moments.size == 0:
        raise TraceIsEmptyError(moment=moment)
    return int(np.argmin(np.abs(moments - moment)))


# %% where every joint stood


class JointTraceField:
    """
    What the file a joint trace is written to holds, by the name each part is stored
    under.
    """

    NAMES = "names"
    MOMENTS = "moments"
    POSITIONS = "positions"


@dataclass(frozen=True)
class JointPositions:
    """
    Where every joint of the world stood at one moment of a trial.
    """

    moment: float
    """
    Seconds into the trial the positions were sampled at.
    """

    positions: Dict[str, float]
    """
    Each joint's position, by the joint's full name.
    """

    def restore_into(self, world: World) -> None:
        """
        Put every joint of the given world that this sample holds back where it stood.

        A joint of the world the sample does not hold is left where it is, so a world
        the run added a body to after the sample is still put back as far as the sample
        goes.

        :param world: The world to put back.
        """
        for degree_of_freedom in world.degrees_of_freedom:
            name = str(degree_of_freedom.name)
            if name not in self.positions:
                continue
            world.state[degree_of_freedom.id].position = self.positions[name]
        world.notify_state_change()


@dataclass
class JointTrace:
    """
    Where every joint of a world stood, sampled along one trial.

    Joints are kept by their full names rather than by the world's own identifiers, so a
    trace read back from disk finds the joints of a world built afresh.
    """

    names: List[str] = field(default_factory=list)
    """
    The full name of each joint, in the order its positions are stored in.
    """

    moments: List[float] = field(default_factory=list)
    """
    Seconds into the trial each sample was taken at, in the order they were taken.
    """

    positions: List[np.ndarray] = field(default_factory=list)
    """
    One row per sample, holding every joint's position in the order of :attr:`names`.
    """

    def sample(self, world: World, moment: float) -> None:
        """
        Keep where every joint of the world stands now.

        The first sample settles which joints the trace holds; later samples hold the
        same ones in the same order.

        :param world: The world to read.
        :param moment: Seconds into the trial it is read at.
        """
        stood = world.state.to_position_dict()
        if not self.names:
            self.names = [str(name) for name in stood]
        by_name = {str(name): position for name, position in stood.items()}
        self.moments.append(moment)
        self.positions.append(
            np.array([by_name[name] for name in self.names], dtype=float)
        )

    @property
    def is_empty(self) -> bool:
        """
        Whether nothing has been sampled yet.
        """
        return not self.moments

    def at(self, moment: float) -> JointPositions:
        """
        Where every joint stood at the sample nearest the given moment.

        :param moment: Seconds into the trial.
        :raises TraceIsEmptyError: If nothing was sampled.
        """
        index = nearest(np.array(self.moments, dtype=float), moment)
        return JointPositions(
            moment=self.moments[index],
            positions=dict(zip(self.names, self.positions[index].tolist())),
        )

    def write(self, path: Path) -> Path:
        """
        Leave the trace at the given path.

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            **{
                JointTraceField.NAMES: np.array(self.names),
                JointTraceField.MOMENTS: np.array(self.moments, dtype=float),
                JointTraceField.POSITIONS: (
                    np.array(self.positions, dtype=float)
                    if self.positions
                    else np.zeros((0, len(self.names)))
                ),
            },
        )
        return path

    @classmethod
    def read(cls, path: Path) -> Self:
        """
        The trace a run left at the given path.

        :param path: The file it was written to.
        """
        with np.load(path) as stored:
            return cls(
                names=stored[JointTraceField.NAMES].tolist(),
                moments=stored[JointTraceField.MOMENTS].tolist(),
                positions=list(stored[JointTraceField.POSITIONS]),
            )


# %% tracing the joints as the world is driven

TRACE_PERIOD = 0.1
"""
Seconds between two samples of a trace taken as the world is driven, unless told
otherwise.

A world driven by a motion changes state far more often than a picture of a moment
needs, so the samples are thinned to this.
"""


@dataclass(eq=False)
class JointTraceRecorder(StateChangeCallback):
    """
    Samples where every joint of a world stands whenever the world changes, at most once
    per period, for as long as it is running.

    Told about every state change of the world it is built on, the way the video
    recorder is, so whatever drives the world -- a plan, physics, a synchroniser
    following the robot -- is traced without being asked to.
    """

    clock: Callable[[], float] = field(kw_only=True, default=time.monotonic)
    """
    Reads how far into the trial the run is, which each sample is stamped with.
    """

    period: float = field(kw_only=True, default=TRACE_PERIOD)
    """
    Seconds between two samples, as the clock reads them.
    """

    trace: JointTrace = field(kw_only=True, default_factory=JointTrace)
    """
    The samples kept so far.
    """

    _next_at: Optional[float] = field(init=False, default=None)
    """
    The reading of the clock the next sample is due at, or None before the first.
    """

    def on_state_change(self, **kwargs) -> None:
        moment = self.clock()
        if self._next_at is not None and moment < self._next_at:
            return
        self._next_at = moment + self.period
        self.trace.sample(self._world, moment)


# %% what a camera saw


class TimedFramesFile:
    """
    The two files a set of timed frames is written as: the frames as a video, and the
    moments beside it.
    """

    MOMENTS_SUFFIX = ".moments.npy"


@dataclass
class TimedFrames:
    """
    What a camera saw along one trial, each frame with the moment it was taken at.

    A video alone times its frames by their place in it, which says nothing about the
    trial once the run that filmed it was not paced to the clock; the moments are what
    put a frame back at the second of the trial it shows.
    """

    frames: List[np.ndarray] = field(default_factory=list)
    """
    The frames, in the order they were taken, as red, green and blue.
    """

    moments: List[float] = field(default_factory=list)
    """
    Seconds into the trial each frame was taken at.
    """

    frames_per_second: int = 15
    """
    The rate the frames are played back at when written as a video.
    """

    def keep(self, frame: np.ndarray, moment: float) -> None:
        """
        Keep one frame.

        :param frame: What the camera saw.
        :param moment: Seconds into the trial it saw it at.
        """
        self.frames.append(frame)
        self.moments.append(moment)

    @property
    def is_empty(self) -> bool:
        """
        Whether no frame has been kept yet.
        """
        return not self.frames

    def at(self, moment: float) -> np.ndarray:
        """
        The frame taken nearest the given moment.

        :param moment: Seconds into the trial.
        :raises TraceIsEmptyError: If no frame was kept.
        """
        return self.frames[nearest(np.array(self.moments, dtype=float), moment)]

    def video(self) -> RecordedVideo:
        """
        The frames as a video to watch.
        """
        return RecordedVideo(
            frames=self.frames, frames_per_second=self.frames_per_second
        )

    def write(self, path: Path) -> Path:
        """
        Leave the frames as a video at the given path, with their moments beside it.

        :param path: The video file, its directory created if it is not there.
        :return:``path``.
        """
        self.video().write(path)
        np.save(self.moments_path_of(path), np.array(self.moments, dtype=float))
        return path

    @classmethod
    def read(cls, path: Path) -> Self:
        """
        The frames a run left as a video at the given path.

        :param path: The video file, with its moments beside it.
        """
        with imageio.get_reader(str(path)) as reader:
            frames = [np.asarray(frame) for frame in reader]
            frames_per_second = round(reader.get_meta_data()["fps"])
        return cls(
            frames=frames,
            moments=np.load(cls.moments_path_of(path)).tolist(),
            frames_per_second=frames_per_second,
        )

    @staticmethod
    def moments_path_of(path: Path) -> Path:
        """
        Where the moments of a video written at the given path are kept.

        :param path: The video file.
        """
        return path.with_suffix(TimedFramesFile.MOMENTS_SUFFIX)
