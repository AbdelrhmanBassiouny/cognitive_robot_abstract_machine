"""
What a running demo has to offer for the viewer to plot what it noticed.

The bridge depends on this abstraction only: it republishes detected events, while what
counts as an event, and how one is recognized, stays with the demo that registered
itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime

from krrood.exceptions import DataclassException
from typing_extensions import Any, Dict, List


@dataclass
class NoEventSourceRegistered(DataclassException):
    """
    Raised when the bridge is asked what has been detected and no demo offered to say.
    """

    def error_message(self) -> str:
        return "no event source is registered on this bridge"

    def suggest_correction(self) -> str:
        return "Start the demo with its viewer support enabled."


@dataclass(frozen=True)
class DetectedEvent:
    """
    One thing a running demo noticed happening, as the viewer's timeline plots it.
    """

    kind: str
    """
    What sort of event this is, in the demo's own vocabulary, so the viewer plots
    whatever is detected without knowing the catalogue it comes from.
    """

    detected_at: datetime
    """
    When the demo noticed it.
    """

    participants: List[str] = field(default_factory=list)
    """
    What the event happened to, the primary thing first.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the viewer's timeline reads.

        The instant is sent as seconds since the epoch, the unit the timeline's own
        arithmetic works in.
        """
        payload = asdict(self)
        payload["detected_at"] = self.detected_at.timestamp()
        return payload


class LiveEventSource(ABC):
    """
    One running demo, as something the viewer can ask what it has detected.
    """

    @abstractmethod
    def title(self) -> str:
        """
        Short name of the run the events were detected in.
        """

    @abstractmethod
    def events(self) -> List[DetectedEvent]:
        """
        Everything detected so far, oldest first.
        """
