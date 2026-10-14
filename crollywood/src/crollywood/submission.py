"""
What a venue accepts a video as.

A venue takes a video no longer, larger, shorter in height or slower in frame rate than
it states. Each venue's own limits are declared where its videos are made;
:meth:`~crollywood.encoding.VideoFile.check_within` checks a file against them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from krrood.units import DataSize


@dataclass(frozen=True)
class SubmissionLimits:
    """
    What a venue accepts a video attachment as.
    """

    longest: timedelta
    """
    The longest it may play.
    """

    largest: DataSize
    """
    The most it may take on disk.
    """

    lowest: int
    """
    The fewest rows of pixels a frame may have.
    """

    slowest: int
    """
    The fewest frames one second may hold.
    """

    def size_budget_for(self, duration: timedelta) -> DataSize:
        """
        :param duration: How long the video plays.
        :return: What a video that long may take: the largest file allowed, in
            proportion to how much of the longest allowed length it plays.
        """
        return self.largest.scaled(min(duration / self.longest, 1.0))
