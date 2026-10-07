"""
An overlay for tests: it stamps how far the video has played into one pixel, so a test
reads back which moment an overlay was drawn for.
"""

from __future__ import annotations

from dataclasses import dataclass

from experiments.video.timeline import Frame, Overlay


@dataclass
class ProgressStamp(Overlay):
    """
    Writes the share of the video played, scaled to a byte, into the top left pixel.
    """

    def drawn_over(self, frame: Frame, seconds: float, runs_for: float) -> Frame:
        stamped = frame.copy()
        stamped[0, 0] = stamped_value(seconds, runs_for)
        return stamped


def stamped_value(seconds: float, runs_for: float) -> int:
    """
    :param seconds: A moment of the video.
    :param runs_for: How long the video lasts.
    :return: The byte :class:`ProgressStamp` writes for that moment.
    """
    return round(255 * seconds / runs_for)
