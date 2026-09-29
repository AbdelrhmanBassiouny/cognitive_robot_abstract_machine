"""
A storyboard turned into a finished mp4: the slides grown to hold their lines, the
narration said and placed, the picture encoded to a byte budget, the narration and the
subtitles joined to it, and the file checked against a venue's limits where one is
given.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from typing_extensions import Optional, Tuple

from experiments.video.encoding import (
    H264Encoder,
    Muxer,
    SubmissionLimits,
    VideoFile,
    bytes_for_sound,
)
from experiments.video.narration import (
    KokoroVoice,
    Narration,
    Storyboard,
    Subtitled,
    Voice,
)
from experiments.video.timeline import Timeline

logger = logging.getLogger(__name__)

BYTES_PER_SECOND = 250_000
"""
The bytes one second of picture may take where no venue limits the file: two megabits a
second, which keeps slides and footage at 720 rows sharp.
"""


class Subtitling(StrEnum):
    """
    How the subtitles go into the video.
    """

    BURNED_IN = "burned-in"
    """
    Drawn into the picture, in the band every scene keeps clear: part of the video.
    """

    SOFT = "soft"
    """
    A text track the viewer can switch off, with the same cues as a SubRip file next to
    the mp4 for players that take one.
    """


class EncoderPreset(StrEnum):
    """
    How long the encoder may take to make the file small, as it names its presets.
    """

    FAST = "fast"
    """
    Quick, for a draft to look at.
    """

    SLOW = "slow"
    """
    Thorough, for the video handed on.
    """


@dataclass
class VideoProduction:
    """
    Makes a narrated, subtitled mp4 from a storyboard.
    """

    storyboard: Storyboard
    """
    The scenes in order, each with the lines that start with it.
    """

    voice: Voice = field(default_factory=KokoroVoice)
    """
    What says the narration.
    """

    frames_per_second: int = 25
    """
    The rate the video plays at.
    """

    dissolve: float = 0.5
    """
    Seconds each scene takes to dissolve into the next.
    """

    subtitling: Subtitling = Subtitling.BURNED_IN
    """
    How the subtitles go in.
    """

    limits: Optional[SubmissionLimits] = None
    """
    What a venue accepts the video as, if the video is made for one: the picture is
    then encoded to the venue's byte limit and the file checked against every limit.
    """

    preset: EncoderPreset = EncoderPreset.SLOW
    """
    How long the encoder may take to make the file small.
    """

    def narrated_timeline(self) -> Tuple[Timeline, Narration]:
        """
        The timeline with its slides grown to hold their lines, and the narration
        placed on it, checked to run clear of itself and of the video's end.

        :raises NarrationOverrun: If a line runs into the next or past the end.
        """
        self.storyboard.fitted_to(self.voice)
        timeline = Timeline(
            self.storyboard.scenes,
            frames_per_second=self.frames_per_second,
            dissolve=self.dissolve,
        )
        narration = self.storyboard.narrated_by(self.voice, dissolve=self.dissolve)
        narration.check(runs_for=timeline.duration)
        return timeline, narration

    def picture_budget_for(self, duration: float) -> int:
        """
        :param duration: How long the video plays, in seconds.
        :return: The bytes the picture may take, leaving room for the sound.
        """
        allowed = (
            BYTES_PER_SECOND * duration
            if self.limits is None
            else self.limits.byte_budget_for(duration)
        )
        return int(allowed) - bytes_for_sound(duration)

    def written_to(self, path: Path) -> VideoFile:
        """
        Render and encode the video.

        :param path: Where the mp4 goes; the SubRip file of soft subtitles goes beside
            it.
        :return: The file written.
        :raises VideoOutsideTheLimits: If the limits are given and the file breaks one.
        """
        timeline, narration = self.narrated_timeline()
        logger.info(
            "%.1f s of video in %d scenes", timeline.duration, len(timeline.scenes)
        )
        burned_in = self.subtitling is Subtitling.BURNED_IN
        picture = Subtitled.over(timeline, narration) if burned_in else timeline
        encoder = H264Encoder(
            size_budget=self.picture_budget_for(timeline.duration),
            preset=self.preset.value,
        )
        silent = encoder.encode(picture, path.with_name(path.stem + "_silent.mp4"))
        soundtrack = narration.soundtrack(runs_for=timeline.duration).written_to(
            path.with_suffix(".wav")
        )
        subtitles = (
            None if burned_in else narration.written_to(path.with_suffix(".srt"))
        )
        video = Muxer().joined(silent, soundtrack, path, subtitles=subtitles)
        silent.path.unlink()
        soundtrack.unlink()
        if self.limits is not None:
            self.limits.check(video)
        logger.info("%s: %.1f s, %d bytes", video.path, video.duration, video.size)
        return video
