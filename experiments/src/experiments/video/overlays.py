"""
What is drawn over a whole video rather than one scene of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from experiments.video.frame import Frame
from experiments.video.theme import VideoTheme
from experiments.video.timeline import Overlay


@dataclass
class ProgressBar(Overlay):
    """
    A thin bar along the top of every frame, filled in the theme's accent as far as the
    video has played, so it grows on across the scenes as one bar.
    """

    theme: VideoTheme = field(default_factory=VideoTheme.neutral)
    """
    The colours of the bar: the accent for what has played, the panel colour for what
    has not.
    """

    thickness: int = 5
    """
    Pixels the bar is high.
    """

    def drawn_over(self, frame: Frame, moment: timedelta, runs_for: timedelta) -> Frame:
        """
        :param frame: The frame of the scenes at that moment.
        :param moment: The moment, from the video's start.
        :param runs_for: How long the video lasts.
        :return: A copy of the frame with the bar drawn along its top.
        """
        width = frame.resolution.width
        played = round(width * min(max(moment / runs_for, 0.0), 1.0))
        drawn = frame.pixels.copy()
        drawn[: self.thickness, :played] = Frame.bytes_of(self.theme.accent)
        drawn[: self.thickness, played:] = Frame.bytes_of(self.theme.panel)
        return Frame(drawn)
