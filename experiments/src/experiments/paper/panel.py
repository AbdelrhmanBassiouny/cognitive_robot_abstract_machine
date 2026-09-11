"""
What a query card is made of: the kinds of picture it can show, and the one thing every
picture of it can do.

Kept apart from the cards themselves so everything that draws a panel -- the scene, the
two charts and the camera -- can all say they draw one without any of them having to
know what a card is.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from semantic_digital_twin.world_description.geometry import Color

# %% the colour every panel picks the answer out in

ANSWER_COLOR = Color(1.0, 0.78, 0.06, 1.0)
"""
What a card draws the answer in, whichever of its pictures is drawing it.

One colour across every panel is what lets the reader carry an answer from one to the
next: the body picked out of the scene, the row of the event it is about, and the item
of the plan that accounts for that event are all the same amber.
"""

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

    PLAN_TIMELINE = "plan_timeline"
    """
    What the robot was running while those events were reported.
    """

    POSE_CHANGE = "pose_change"
    """
    The twin with the object drawn where it was and where it ended up, in one view.
    """

    CAMERA_FRAME = "camera_frame"
    """
    What the robot's own camera saw at that moment, which only a run on the robot has.
    """

    CAMERA_BEFORE_AND_AFTER = "camera_before_and_after"
    """
    What that camera saw on either side of the event, side by side.
    """

    @property
    def caption(self) -> str:
        """
        What this picture shows, as the paper's reader is told it under the figure.
        """
        return _PANEL_CAPTIONS[self]


_PANEL_CAPTIONS = {
    PanelKind.SCENE: "drawn into the digital twin.",
    PanelKind.TIMELINE: "against the events of the run, with the query's own moment "
    "marked.",
    PanelKind.PLAN_TIMELINE: "against the plan the robot was running, with the item "
    "that accounts for the event picked out.",
    PanelKind.POSE_CHANGE: "drawn into the twin where it was and where it ended up, "
    "the earlier pose ghosted.",
    PanelKind.CAMERA_FRAME: "as the robot's camera saw it at that moment.",
    PanelKind.CAMERA_BEFORE_AND_AFTER: "as the robot's camera saw it just before and "
    "just after.",
}
"""
What each kind of picture shows, kept beside the members rather than in them so a member
names the situation it means and not the wording it is rendered with.
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

        :param path: The file it is written to, its directory created if it is not
            there.
        :return:``path``.
        """
