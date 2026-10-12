"""
Frames written out as one H.264 video no larger than a byte budget.

A venue takes a video no longer, larger, shorter in height or slower in frame rate than
it states, so the encoder is told the size it may not exceed and picks the bit rate from
that and the length, in two passes, and the file that comes out can be checked against
every limit before it is handed on.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import imageio_ffmpeg
import numpy as np


from cramcorder.exceptions import (
    EncodingFailed,
    NothingToRead,
    VideoOutsideTheLimits,
)
from cramcorder.frame import Frame, Resolution
from cramcorder.timeline import Timeline

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
        """
        :return: The file opened for reading.
        """
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
    def duration(self) -> timedelta:
        """
        How long it plays.
        """
        return timedelta(seconds=self.frame_count / self.frames_per_second)

    def frame_at(self, moment: timedelta) -> Frame:
        """
        :param moment: The moment, from the video's start.
        :return: The frame there, as red, green and blue.
        :raises NothingToRead: If the file holds no frame there.
        """
        opened = self._opened()
        opened.set(
            cv2.CAP_PROP_POS_FRAMES,
            round(moment.total_seconds() * self.frames_per_second),
        )
        read, frame = opened.read()
        if not read:
            raise NothingToRead(path=self.path, moment=moment)
        return Frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


# %% the limits


@dataclass(frozen=True)
class SubmissionLimits:
    """
    What a venue accepts a video attachment as.
    """

    longest: timedelta
    """
    The longest it may play.
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

    def byte_budget_for(self, duration: timedelta) -> int:
        """
        :param duration: How long the video plays.
        :return: The bytes a video that long may take: the largest file allowed, in
            proportion to how much of the longest allowed length it plays.
        """
        return int(self.largest * min(duration / self.longest, 1.0))

    def check(self, video: VideoFile) -> None:
        """
        :param video: The video to check.
        :raises VideoOutsideTheLimits: If it breaks any limit.
        """
        broken = []
        if video.duration > self.longest:
            broken.append(
                f"plays {video.duration.total_seconds():.1f} s, over "
                f"{self.longest.total_seconds():.0f} s"
            )
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

    pixel_format: str = "yuv420p"
    """
    The chroma layout every player decodes, which needs even frame sides.
    """

    bit_rate_headroom: float = 0.90
    """
    How much of the byte budget the video stream is aimed at, leaving the container and
    the encoder's own overshoot room under the limit.
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

    def bit_rate_for(self, duration: timedelta) -> int:
        """
        :param duration: How long the video plays.
        :return: The bits per second that fill the budget over that time, less headroom.
        """
        return int(
            self.size_budget * 8 * self.bit_rate_headroom / duration.total_seconds()
        )

    def _keep_losslessly(self, timeline: Timeline, master: Path) -> None:
        """
        Pipe every frame into a lossless file.

        :param timeline: What to keep.
        :param master: Where the lossless file goes.
        :raises EncodingFailed: If the encoder program exits with an error.
        """
        first = next(iter(timeline.frames()))
        resolution = first.resolution
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
            process.stdin.write(np.ascontiguousarray(frame.pixels).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise EncodingFailed(path=master)

    def _two_passes(
        self, master: Path, path: Path, duration: timedelta, log_prefix: Path
    ) -> None:
        """
        Encode the master twice at the budget's bit rate, the second pass reading the
        first's log.

        :param master: The lossless file.
        :param path: Where the mp4 goes.
        :param duration: How long the video plays.
        :param log_prefix: Where the first pass keeps what the second reads.
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
            self.pixel_format,
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
