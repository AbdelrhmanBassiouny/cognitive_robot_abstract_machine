"""
Subtitles drawn into the picture, so they are part of the video itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
from semantic_digital_twin.spatial_types.spatial_types import Point2
from typing_extensions import Sequence

from cramcorder.frame import Frame
from cramcorder.narration import NarratedTimeline
from cramcorder.subtitles import SubtitleCue, SubtitleRoom
from cramcorder.theme import VideoTheme
from cramcorder.timeline import Timeline
from cramcorder.typesetting import Anchor, TextSize, Typesetting

# %% how the rows are drawn


@dataclass
class CaptionStyle(ABC):
    """
    How the rows of a subtitle are drawn into a frame.
    """

    @abstractmethod
    def captioned(self, frame: Frame, rows: Sequence[str]) -> Frame:
        """
        :param frame: The frame.
        :param rows: The rows of the subtitle, at most two.
        :return: A copy of the frame with the rows written in.
        """


@dataclass
class BandCaption(CaptionStyle):
    """
    Rows written in the band every scene keeps clear at the bottom of the picture, from
    one fixed baseline: in the theme's text colour on its page, and white on a band
    shaded towards black wherever footage fills the frame.
    """

    theme: VideoTheme = field(default_factory=VideoTheme.neutral)
    """
    The page the band is told apart from footage by, and the colour written on it.
    """

    top: int = 12
    """
    Pixels under the stage the first row hangs from: the rows keep one baseline whether
    one or two are written.
    """

    row_pitch: int = 38
    """
    Pixels from one row to the next.
    """

    page_likeness: int = 20
    """
    How far the band's mean colour may lie from the page's, per channel, for the band to
    be the page rather than footage.
    """

    shade: float = 0.72
    """
    How dark the band over footage is shaded at its bottom.
    """

    def captioned(self, frame: Frame, rows: Sequence[str]) -> Frame:
        """
        :param frame: The frame.
        :param rows: The rows of the subtitle, at most two.
        :return: A copy of the frame with the rows written in the band.
        """
        resolution = frame.resolution
        band_top = resolution.stage_height
        on_page = self.is_page(Frame(frame.pixels[int(band_top) :]))
        if not on_page:
            frame = frame.darkened(
                Frame.box(
                    0,
                    band_top - self.top * 2,
                    resolution.width,
                    resolution.height - band_top + self.top * 2,
                ),
                self.shade,
            )
        lettering = Typesetting(
            size=TextSize.BODY,
            color=self.theme.text if on_page else self.theme.footage_text,
            typeface=self.theme.typeface,
        )
        for number, row in enumerate(rows):
            frame = lettering.written(
                frame,
                row,
                Point2(
                    resolution.width / 2, band_top + self.top + number * self.row_pitch
                ),
                Anchor.CENTRE_TOP,
            )
        return frame

    def is_page(self, band: Frame) -> bool:
        """
        :param band: The band of a frame.
        :return: Whether it is the theme's page rather than footage.
        """
        mean = band.pixels.reshape(-1, 3).mean(axis=0)
        page = np.array(Frame.bytes_of(self.theme.page))
        return bool(np.abs(mean - page).max() <= self.page_likeness)


@dataclass
class BoxedCaption(CaptionStyle):
    """
    Rows written in white on a box shaded towards black, centred over the bottom of the
    picture, so they read on any scene alike.
    """

    theme: VideoTheme = field(default_factory=VideoTheme.neutral)
    """
    The colour the rows are written in.
    """

    row_pitch: int = 38
    """
    Pixels from one row to the next.
    """

    shade: float = 0.66
    """
    How dark the box behind the rows is shaded.
    """

    padding: int = 25
    """
    Pixels between the rows and the sides of the box.
    """

    padding_above_and_below: int = 14
    """
    Pixels between the rows and the top and bottom of the box.
    """

    corner_radius: int = 11
    """
    Pixels the corners of the box are rounded by.
    """

    margin: int = 20
    """
    Pixels between the box and the bottom of the frame.
    """

    def captioned(self, frame: Frame, rows: Sequence[str]) -> Frame:
        """
        :param frame: The frame.
        :param rows: The rows of the subtitle, at most two.
        :return: A copy of the frame with the rows written on a shaded box.
        """
        resolution = frame.resolution
        lettering = Typesetting(size=TextSize.BODY, color=self.theme.footage_text)
        width = max(lettering.width_of(row) for row in rows) + 2 * self.padding
        height = (
            TextSize.BODY
            + (len(rows) - 1) * self.row_pitch
            + 2 * self.padding_above_and_below
        )
        top = resolution.height - self.margin - height
        box = Frame.box((resolution.width - width) / 2, top, width, height)
        frame = frame.shaded(box, self.shade, self.corner_radius)
        for number, row in enumerate(rows):
            frame = lettering.written(
                frame,
                row,
                Point2(
                    resolution.width / 2,
                    top + self.padding_above_and_below + number * self.row_pitch,
                ),
                Anchor.CENTRE_TOP,
            )
        return frame


# %% a timeline with its captions


@dataclass
class Subtitled(Timeline):
    """
    A timeline with its captions drawn into the picture.
    """

    cues: list[SubtitleCue] = field(default_factory=list)
    """
    The subtitles, in order, each fitting the room.
    """

    room: SubtitleRoom = field(default_factory=SubtitleRoom.burned_in)
    """
    How much text one subtitle shows: the rows a cue is written on.
    """

    style: CaptionStyle = field(default_factory=BandCaption)
    """
    How a cue's rows are drawn.
    """

    @classmethod
    def over(
        cls,
        narrated: NarratedTimeline,
        room: SubtitleRoom | None = None,
        style: CaptionStyle | None = None,
    ) -> Subtitled:
        """
        :param narrated: A timeline with what is said over it, its overlays kept.
        :param room: How much text one subtitle shows; the burned-in room if not given.
        :param style: How a cue's rows are drawn; in the band if not given.
        :return: The timeline with the narration's subtitles drawn into the picture.
        """
        fitting = room if room is not None else SubtitleRoom.burned_in()
        timeline = narrated.role_taker
        return cls(
            timeline.scenes,
            timeline.frames_per_second,
            timeline.dissolve,
            timeline.overlays,
            cues=narrated.narration.cues(fitting),
            room=fitting,
            style=style if style is not None else BandCaption(),
        )

    def cue_at(self, moment: timedelta) -> SubtitleCue | None:
        """
        :param moment: A moment of the video.
        :return: The subtitle shown then, if one is.
        """
        return next((cue for cue in self.cues if cue.start <= moment < cue.end), None)

    def frame_at(self, moment: timedelta) -> Frame:
        """
        :param moment: The moment, from the video's start.
        :return: What the video shows then, with the subtitle of the moment drawn in.
        """
        frame = super().frame_at(moment)
        cue = self.cue_at(moment)
        if cue is None:
            return frame
        return self.style.captioned(frame, cue.rows(self.room))
