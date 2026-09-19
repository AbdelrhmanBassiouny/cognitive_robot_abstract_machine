"""
The slides the video opens and closes with: the paper's title and number at the start,
and where its code is at the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List

from experiments.paper.lettering import Face
from experiments.video.canvas import (
    VIDEO_RESOLUTION,
    Anchor,
    Ink,
    Area,
    Typesetting,
    filled,
)
from experiments.video.script import VideoScript
from experiments.video.timeline import Frame, Resolution, Scene, eased

RULE_WIDTH = 120
"""
How wide the short rule under the title is, in pixels.
"""


@dataclass
class TitleSlide(Scene):
    """
    The paper's title, the conference and the submission number, fading in.
    """

    script: VideoScript
    """
    The words.
    """

    held_for: float = 6.0
    """
    How long the slide is shown, in seconds.
    """

    fade: float = 1.0
    """
    How long the words take to appear, in seconds.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        centre_x = self.resolution.width / 2
        title = Typesetting(size=40, face=Face.BOLD)
        wrapped = title.wrapped(self.script.title, self.resolution.width * 0.78)
        lines = wrapped.count("\n") + 1
        title_top = self.resolution.height * 0.30 - lines * 27
        frame = title.written(frame, wrapped, (centre_x, title_top), Anchor.CENTRE_TOP)
        rule_y = title_top + lines * 54 + 30
        frame = filled(
            frame,
            Area(centre_x - RULE_WIDTH / 2, rule_y, RULE_WIDTH, 3),
            Ink.PERCEPTION.rgb,
        )
        frame = Typesetting(size=28, color=Ink.MUTED.rgb).written(
            frame, self.script.kind, (centre_x, rule_y + 60), Anchor.CENTRE_MIDDLE
        )
        frame = Typesetting(size=28, color=Ink.TEXT.rgb).written(
            frame,
            self.script.submission_line,
            (centre_x, rule_y + 110),
            Anchor.CENTRE_MIDDLE,
        )
        return self._faded_in(frame, seconds)

    def _faded_in(self, frame: Frame, seconds: float) -> Frame:
        """
        The frame faded up from white over the first moments.
        """
        weight = eased(seconds / self.fade)
        blank = self.resolution.blank(255)
        return (blank * (1 - weight) + frame * weight + 0.5).astype("uint8")


@dataclass
class ClosingSlide(Scene):
    """
    Where the code is, on the last frames.
    """

    script: VideoScript
    """
    The words.
    """

    held_for: float = 5.0
    """
    How long the slide is shown, in seconds.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        centre = (self.resolution.width / 2, self.resolution.height / 2)
        frame = Typesetting(size=30, face=Face.BOLD).written(
            frame,
            "Code and recorded episodes",
            (centre[0], centre[1] - 40),
            Anchor.CENTRE_MIDDLE,
        )
        frame = Typesetting(size=24, color=Ink.SIMULATION.rgb).written(
            frame,
            self.script.repository_link,
            (centre[0], centre[1] + 20),
            Anchor.CENTRE_MIDDLE,
        )
        return frame


@dataclass
class TextSlide(Scene):
    """
    A few lines of text, held for a while.
    """

    lines: List[str]
    """
    The lines, the first set larger.
    """

    held_for: float = 4.0
    """
    How long the slide is shown, in seconds.
    """

    resolution: Resolution = VIDEO_RESOLUTION
    """
    The size of the slide.
    """

    @property
    def duration(self) -> float:
        return self.held_for

    def picture_at(self, seconds: float) -> Frame:
        frame = self.resolution.blank(255)
        centre_x = self.resolution.width / 2
        top = self.resolution.height / 2 - 30 * len(self.lines)
        for number, line in enumerate(self.lines):
            setting = Typesetting(size=40, face=Face.BOLD) if number == 0 else Typesetting(size=26, color=Ink.MUTED.rgb)
            frame = setting.written(frame, line, (centre_x, top + number * 60 + (20 if number else 0)), Anchor.CENTRE_MIDDLE)
        return frame
