"""
The picture, the narration and the subtitles joined into one mp4.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import imageio_ffmpeg
from typing_extensions import Optional

from experiments.video.encoding import VideoFile

# %% the voice and the subtitles, joined to the picture


@dataclass
class Muxer:
    """
    Joins a silent video, its narration and its subtitles into one mp4.

    The picture is copied as it is; the narration is encoded as AAC, the codec every
    player decodes; the subtitles, where they are not burned into the picture, go in as
    a text track the viewer can switch off, on by default.
    """

    ffmpeg: Path = field(default_factory=lambda: Path(imageio_ffmpeg.get_ffmpeg_exe()))
    """
    The encoder binary.
    """

    audio_bit_rate: int = 64_000
    """
    Bits per second the narration is encoded at: one channel of speech needs no more.
    """

    subtitle_allowance: int = 40_000
    """
    Bytes set aside for the subtitle track and what joining the streams adds to the
    file.
    """

    def bytes_for_sound(self, duration: timedelta) -> int:
        """
        :param duration: How long the video plays.
        :return: The bytes the narration and the subtitles take over it, to keep out of
            the picture's budget.
        """
        return (
            int(self.audio_bit_rate / 8 * duration.total_seconds())
            + self.subtitle_allowance
        )

    def joined(
        self,
        video: VideoFile,
        soundtrack: Path,
        path: Path,
        subtitles: Optional[Path] = None,
    ) -> VideoFile:
        """
        :param video: The silent video.
        :param soundtrack: The narration, as a wave file as long as the video.
        :param path: Where the joined mp4 goes.
        :param subtitles: The subtitles, as a SubRip file, or None where they are
            already in the picture.
        :return: The file written.
        """
        command = [
            str(self.ffmpeg),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video.path),
            "-i",
            str(soundtrack),
        ]
        if subtitles is not None:
            command += ["-i", str(subtitles)]
        command += ["-map", "0:v:0", "-map", "1:a:0"]
        if subtitles is not None:
            command += ["-map", "2:s:0"]
        command += [
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            str(self.audio_bit_rate),
            "-ac",
            "1",
            "-metadata:s:a:0",
            "language=eng",
        ]
        if subtitles is not None:
            command += [
                "-c:s",
                "mov_text",
                "-metadata:s:s:0",
                "language=eng",
                "-disposition:s:0",
                "default",
            ]
        command += ["-movflags", "+faststart", str(path)]
        subprocess.run(command, check=True)
        return VideoFile(path=path)
