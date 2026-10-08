"""
What is drawn over a whole video rather than one scene of it.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.video.canvas import NEUTRAL_THEME, VideoTheme
from experiments.video.timeline import Frame, Overlay

PROGRESS_BAR_THICKNESS = 5
"""
Pixels the progress bar is high.
"""


@dataclass
class ProgressBar(Overlay):
    """
    A thin bar along the top of every frame, filled in the theme's accent as far as the
    video has played, so it grows on across the scenes as one bar.
    """

    theme: VideoTheme = NEUTRAL_THEME
    """
    The colours of the bar: the accent for what has played, the panel colour for what
    has not.
    """

    thickness: int = PROGRESS_BAR_THICKNESS
    """
    Pixels the bar is high.
    """

    def drawn_over(self, frame: Frame, seconds: float, runs_for: float) -> Frame:
        width = frame.shape[1]
        played = round(width * min(max(seconds / runs_for, 0.0), 1.0))
        drawn = frame.copy()
        drawn[: self.thickness, :played] = self.theme.accent
        drawn[: self.thickness, played:] = self.theme.panel
        return drawn
