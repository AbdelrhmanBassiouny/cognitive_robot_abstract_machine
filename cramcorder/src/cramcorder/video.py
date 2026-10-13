"""
Moving pictures: what any video, scene or recording is to what plays it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta

from cramcorder.frame import Frame

# %% a video


class Video(ABC):
    """
    Moving pictures: a frame for any moment, and how long they play.
    """

    @property
    @abstractmethod
    def duration(self) -> timedelta:
        """
        How long it plays.
        """

    @abstractmethod
    def frame_at(self, moment: timedelta) -> Frame:
        """
        :param moment: A moment from its start, within its duration.
        :return: The frame shown then.
        """
