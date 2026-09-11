"""
What a query card is made of: the kinds of picture it can show, and the one thing every
picture of it can do.

Kept apart from the cards themselves so the three things that draw a panel -- the scene,
the timeline and the camera -- can all say they draw one without any of them having to
know what a card is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

# %% which picture of a card a panel is


class PanelKind(StrEnum):
    """
    The kinds of picture a query card can show, each named by what it shows.

    A member's value is what the panel's own file is called after the card's name, so
    the card and the Typst it writes name a panel once.
    """

    SCENE = "scene"
    """
    The twin with the things the answer names picked out of it.
    """

    TIMELINE = "timeline"
    """
    When each kind of event was reported, with the moment the query was asked marked.
    """

    CAMERA_FRAME = "camera_frame"
    """
    What the robot's own camera saw at that moment, which only a run on the robot has.
    """


# %% one picture of a card


@dataclass
class CardPanel(ABC):
    """
    One picture a query card shows, whatever it is a picture of.
    """

    @abstractmethod
    def write(self, path: Path) -> Path:
        """
        Leave this picture at the given path.

        :param path: The file it is written to, its directory created if it is not there.
        :return: ``path``.
        """
