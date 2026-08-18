"""
What a running Montessori sort tells the viewer's timeline it has just noticed.

The detections themselves are segmind's, and are handed over on the thread that plans
the motion they were noticed during; the timeline is answered on an HTTP thread. So each
one is turned into the viewer's own shape as it arrives, and the timeline only ever
reads a finished list -- the same discipline the rest of the bridge keeps.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from cramera.live.events import DetectedEvent, LiveEventSource
from segmind.datastructures.events import DetectionEvent, EventWithTrackedObjects
from typing_extensions import List


@dataclass
class MontessoriLiveEventSource(LiveEventSource):
    """
    Everything a sort has detected so far, in the shape the viewer's timeline plots.
    """

    _detected: List[DetectedEvent] = field(default_factory=list)
    """
    What has been noticed so far, oldest first.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards :attr:`_detected` against the run appending to it while the viewer reads it.
    """

    def title(self) -> str:
        """
        What the timeline names this source.
        """
        return "Montessori sorting"

    def events(self) -> List[DetectedEvent]:
        """
        Everything detected so far, oldest first.
        """
        with self._lock:
            return list(self._detected)

    def receive(self, events: List[DetectionEvent]) -> None:
        """
        Take what a monitor has just detected.

        :param events: The events noticed since this was last called, oldest first.
        """
        described = [self._describe(event) for event in events]
        with self._lock:
            self._detected.extend(described)

    @staticmethod
    def _describe(event: DetectionEvent) -> DetectedEvent:
        """
        One segmind event as the viewer's timeline reads it.

        :param event: The event that was detected.
        """
        involved = (
            event.tracked_objects if isinstance(event, EventWithTrackedObjects) else []
        )
        return DetectedEvent(
            kind=type(event).__name__,
            detected_at=event.timestamp,
            participants=[str(entity.name) for entity in involved],
        )
