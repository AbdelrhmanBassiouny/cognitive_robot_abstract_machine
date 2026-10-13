"""
A storyboard turned into a finished mp4: the slides grown to hold their lines, the
narration said and placed, the picture encoded to a size budget, the narration and the
subtitles joined to it, and the file checked against a venue's limits where one is
given.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from pathlib import Path


from cramcorder.captions import BandCaption, CaptionStyle, Subtitled
from cramcorder.encoding import (
    EncoderPreset,
    H264Encoder,
    SubmissionLimits,
    VideoFile,
)
from cramcorder.muxer import Muxer
from cramcorder.narration import NarratedTimeline, Storyboard
from cramcorder.speech import KokoroVoice, Voice
from cramcorder.timeline import Overlay, Timeline
from krrood.units import BitRate, DataSize

logger = logging.getLogger(__name__)


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

    dissolve: timedelta = timedelta(seconds=0.5)
    """
    How long each scene takes to dissolve into the next.
    """

    subtitling: Subtitling = Subtitling.BURNED_IN
    """
    How the subtitles go in.
    """

    captions: CaptionStyle = field(default_factory=BandCaption)
    """
    How burned-in subtitles are drawn.
    """

    overlays: list[Overlay] = field(default_factory=list)
    """
    What is drawn over every frame, whatever scene plays, such as a
    :class:`~cramcorder.overlays.ProgressBar`.
    """

    limits: SubmissionLimits | None = None
    """
    What a venue accepts the video as, if the video is made for one: the picture is
    then encoded to the venue's size limit and the file checked against every limit.
    """

    preset: EncoderPreset = EncoderPreset.SLOW
    """
    How long the encoder may take to make the file small.
    """

    picture_bit_rate: BitRate = field(
        default_factory=lambda: BitRate(DataSize(2_000_000))
    )
    """
    How much data one second of picture may take where no venue limits the file: what
    keeps slides and footage at 720 rows sharp.
    """

    muxer: Muxer = field(default_factory=Muxer)
    """
    What joins the picture, the narration and the subtitles.
    """

    def narrated_timeline(self) -> NarratedTimeline:
        """
        The timeline with its slides grown to hold their lines, and the narration placed
        on it, checked to run clear of itself and of the video's end.

        :return: The timeline with its narration.
        :raises NarrationOverrun: If a line runs into the next or past the end.
        """
        self.storyboard.fitted_to(self.voice)
        timeline = Timeline(
            self.storyboard.scenes,
            frames_per_second=self.frames_per_second,
            dissolve=self.dissolve,
            overlays=self.overlays,
        )
        narrated = NarratedTimeline(
            role_taker=timeline,
            narration=self.storyboard.narrated_by(self.voice, dissolve=self.dissolve),
        )
        narrated.check()
        return narrated

    def picture_of(self, narrated: NarratedTimeline) -> Timeline:
        """
        :param narrated: The narrated timeline.
        :return: What is encoded as the picture: the timeline with its subtitles drawn
            in when they are burned in, else the timeline alone.
        """
        if self.subtitling is not Subtitling.BURNED_IN:
            return narrated.role_taker
        return Subtitled.over(narrated, style=self.captions)

    def picture_budget_for(self, duration: timedelta) -> DataSize:
        """
        :param duration: How long the video plays.
        :return: What the picture may take, leaving room for the sound.
        """
        allowed = (
            self.picture_bit_rate.over(duration)
            if self.limits is None
            else self.limits.size_budget_for(duration)
        )
        return allowed - self.muxer.size_of_sound(duration)

    def written_to(self, path: Path) -> VideoFile:
        """
        Render and encode the video.

        :param path: Where the mp4 goes; the SubRip file of soft subtitles goes beside
            it.
        :return: The file written.
        :raises VideoOutsideTheLimits: If the limits are given and the file breaks one.
        """
        narrated = self.narrated_timeline()
        duration = narrated.duration
        logger.info(
            "%.1f s of video in %d scenes",
            duration.total_seconds(),
            len(narrated.scenes),
        )
        picture = self.picture_of(narrated)
        encoder = H264Encoder(
            size_budget=self.picture_budget_for(duration), preset=self.preset
        )
        silent = encoder.encode(picture, path.with_name(path.stem + "_silent.mp4"))
        soundtrack = narrated.soundtrack().written_to(path.with_suffix(".wav"))
        subtitles = (
            narrated.narration.written_to(path.with_suffix(".srt"))
            if self.subtitling is Subtitling.SOFT
            else None
        )
        video = self.muxer.joined(silent, soundtrack, path, subtitles=subtitles)
        silent.path.unlink()
        soundtrack.unlink()
        if self.limits is not None:
            self.limits.check(video)
        logger.info(
            "%s: %.1f s, %d bytes",
            video.path,
            video.duration.total_seconds(),
            video.size.bytes,
        )
        return video
