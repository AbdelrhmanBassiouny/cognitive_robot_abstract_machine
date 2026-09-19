"""
Frames written out as one H.264 video small enough to submit.

The conference takes an mp4 no longer, larger, shorter in height or slower in frame rate
than its call for papers states, so the encoder is told the size it may not exceed and
picks the bit rate from that and the length, in two passes, and the file that comes out
is checked against every limit before it is handed on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import imageio_ffmpeg
import numpy as np
from krrood.exceptions import DataclassException
from typing_extensions import List, Optional

from experiments.video.timeline import Frame, Resolution, Timeline

PIXEL_FORMAT = "yuv420p"
"""
The chroma layout every player decodes, which needs even frame sides.
"""

BIT_RATE_HEADROOM = 0.90
"""
How much of the byte budget the video stream is aimed at, leaving the container and the
encoder's own overshoot room under the limit.
"""

# %% the file that comes out


@dataclass(frozen=True)
class VideoFile:
    """
    A video on disk, read for what a submission is checked on.
    """

    path: Path
    """
    Where it lies.
    """

    @property
    def size(self) -> int:
        """
        How many bytes it takes.
        """
        return self.path.stat().st_size

    def _opened(self) -> cv2.VideoCapture:
        return cv2.VideoCapture(str(self.path))

    @property
    def resolution(self) -> Resolution:
        """
        The size of its frames.
        """
        opened = self._opened()
        return Resolution(
            width=int(opened.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(opened.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    @property
    def frames_per_second(self) -> float:
        """
        How many frames one second of it holds.
        """
        return float(self._opened().get(cv2.CAP_PROP_FPS))

    @property
    def frame_count(self) -> int:
        """
        How many frames it holds.
        """
        return int(self._opened().get(cv2.CAP_PROP_FRAME_COUNT))

    @property
    def duration(self) -> float:
        """
        How long it plays, in seconds.
        """
        return self.frame_count / self.frames_per_second

    def frame_at(self, seconds: float) -> Frame:
        """
        One frame read back, as red, green and blue.

        :param seconds: The moment, from the video's start.
        """
        opened = self._opened()
        opened.set(cv2.CAP_PROP_POS_FRAMES, round(seconds * self.frames_per_second))
        read, frame = opened.read()
        if not read:
            raise ValueError(f"nothing to read at {seconds:.3f} s of {self.path}")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


# %% the limits


@dataclass
class VideoOutsideTheLimits(DataclassException):
    """
    Raised when a video breaks a limit the conference states for a submission.
    """

    video: VideoFile
    """
    The video checked.
    """

    broken: List[str]
    """
    What it breaks, one line each.
    """

    def error_message(self) -> str:
        return f"{self.video.path} cannot be submitted: " + "; ".join(self.broken)

    def suggest_correction(self) -> str:
        return (
            "Shorten the script, lower the size budget or raise the frame rate or "
            "resolution the timeline is rendered at."
        )


@dataclass(frozen=True)
class SubmissionLimits:
    """
    What the conference accepts a video attachment as.
    """

    longest: float
    """
    The longest it may play, in seconds.
    """

    largest: int
    """
    The most bytes it may take.
    """

    lowest: int
    """
    The fewest rows of pixels a frame may have.
    """

    slowest: int
    """
    The fewest frames one second may hold.
    """

    @classmethod
    def icra_2027(cls) -> SubmissionLimits:
        """
        The limits the ICRA 2027 call for papers states for a video attachment.
        """
        return cls(longest=180.0, largest=20_000_000, lowest=480, slowest=20)

    def check(self, video: VideoFile) -> None:
        """
        :param video: The video to check.
        :raises VideoOutsideTheLimits: If it breaks any limit.
        """
        broken = []
        if video.duration > self.longest:
            broken.append(f"plays {video.duration:.1f} s, over {self.longest:.0f} s")
        if video.size > self.largest:
            broken.append(f"takes {video.size} bytes, over {self.largest}")
        if video.resolution.height < self.lowest:
            broken.append(
                f"is {video.resolution.height} rows tall, under {self.lowest}"
            )
        if video.frames_per_second < self.slowest:
            broken.append(
                f"plays {video.frames_per_second:.1f} frames a second, under "
                f"{self.slowest}"
            )
        if broken:
            raise VideoOutsideTheLimits(video=video, broken=broken)


# %% the encoder


@dataclass
class H264Encoder:
    """
    Writes a timeline out as an H.264 mp4 no larger than a byte budget.

    The frames are first kept losslessly, since two passes have to read them, and then
    encoded twice at the bit rate the budget and the length allow.
    """

    size_budget: int
    """
    The most bytes the file may take.
    """

    preset: str = "slow"
    """
    The encoder's speed-against-size trade, as it names them.
    """

    ffmpeg: Path = field(default_factory=lambda: Path(imageio_ffmpeg.get_ffmpeg_exe()))
    """
    The encoder binary.
    """

    def encode(self, timeline: Timeline, path: Path) -> VideoFile:
        """
        Write the timeline out.

        :param timeline: What to write.
        :param path: Where the mp4 goes.
        :return: The file written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="video_master_") as scratch:
            master = Path(scratch) / "master.mkv"
            self._keep_losslessly(timeline, master)
            self._two_passes(master, path, timeline.duration, Path(scratch) / "pass")
        return VideoFile(path=path)

    def bit_rate_for(self, duration: float) -> int:
        """
        :param duration: How long the video plays, in seconds.
        :return: The bits per second that fill the budget over that time, less headroom.
        """
        return int(self.size_budget * 8 * BIT_RATE_HEADROOM / duration)

    def _keep_losslessly(self, timeline: Timeline, master: Path) -> None:
        """
        Pipe every frame into a lossless file.
        """
        first = next(iter(timeline.frames()))
        resolution = Resolution.of(first)
        command = [
            str(self.ffmpeg),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{resolution.width}x{resolution.height}",
            "-r",
            str(timeline.frames_per_second),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-qp",
            "0",
            "-preset",
            "ultrafast",
            str(master),
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        for frame in timeline.frames():
            process.stdin.write(np.ascontiguousarray(frame).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError(f"ffmpeg failed to keep the frames of {master}")

    def _two_passes(
        self, master: Path, path: Path, duration: float, log_prefix: Path
    ) -> None:
        """
        Encode the master twice at the budget's bit rate, the second pass reading the
        first's log.
        """
        bit_rate = self.bit_rate_for(duration)
        shared = [
            str(self.ffmpeg),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(master),
            "-c:v",
            "libx264",
            "-preset",
            self.preset,
            "-profile:v",
            "high",
            "-pix_fmt",
            PIXEL_FORMAT,
            "-b:v",
            str(bit_rate),
            "-maxrate",
            str(int(bit_rate * 1.5)),
            "-bufsize",
            str(bit_rate * 2),
            "-passlogfile",
            str(log_prefix),
            "-movflags",
            "+faststart",
        ]
        subprocess.run(
            shared + ["-pass", "1", "-an", "-f", "mp4", "/dev/null"], check=True
        )
        subprocess.run(shared + ["-pass", "2", "-an", str(path)], check=True)
