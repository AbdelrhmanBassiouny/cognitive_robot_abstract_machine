"""
What to replay of a recorded demo around one answered moment, and what it shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from typing_extensions import Any, ClassVar, Dict, List


@dataclass(frozen=True)
class ReplayWindow:
    """
    The span of a recorded demo worth replaying around one moment.

    A moment by itself is too short to watch, so the window leads and trails it by fixed
    shifts, just far enough to show it happening.
    """

    LEAD_SECONDS: ClassVar[float] = 1.0
    """
    How long before its moment a replay begins.
    """

    TAIL_SECONDS: ClassVar[float] = 1.0
    """
    How long after its moment a replay ends.
    """

    start: float
    """
    When the replay begins, in seconds since the epoch.
    """

    end: float
    """
    When the replay ends, in seconds since the epoch.
    """

    @classmethod
    def around(cls, moment: datetime) -> ReplayWindow:
        """
        The window worth replaying around one moment.

        :param moment: When the thing worth watching happened.
        """
        at = moment.timestamp()
        return cls(start=at - cls.LEAD_SECONDS, end=at + cls.TAIL_SECONDS)

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON shape the viewer opens a replay from.
        """
        return {"start": self.start, "end": self.end}


@dataclass(frozen=True)
class ReplayedMoment:
    """
    One moment an answer row offers to replay, and what watching it shows.

    The span alone says only when to play; a viewer that is to name what it is showing
    and point at what it happened to needs the moment's own title and objects too.
    """

    window: ReplayWindow
    """
    The span of the recording the replay plays.
    """

    label: str = ""
    """
    What happened at the moment, as the row offering it is titled, or empty when the row
    names nothing.
    """

    objects: List[str] = field(default_factory=list)
    """
    Names of the objects the moment happened to, which a replay points out.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON shape the viewer opens an annotated replay from.
        """
        return {
            **self.window.to_payload(),
            "label": self.label,
            "objects": list(self.objects),
        }
