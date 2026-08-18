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
from cramera.live.run_clock import RunClock, RunClockReading
from segmind.datastructures.events import DetectionEvent, EventWithTrackedObjects
from typing_extensions import List


@dataclass
class MontessoriLiveEventSource(LiveEventSource):
    """
    Everything a sort has detected so far, in the shape the viewer's timeline plots.
    """

    clock: RunClock
    """
    How far the run had got when each detection arrived, and the axis the timeline plots
    them along.

    Handed in rather than made here, because it is the run's clock: it is the run that
    pauses and restarts it, and a clock of this source's own would keep going while the
    run it reports on stood still.
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

    def clock_reading(self) -> RunClockReading:
        """
        How far the run has got along the axis its detections are stamped against.
        """
        return self.clock.reading()

    def receive(self, events: List[DetectionEvent]) -> None:
        """
        Take what a monitor has just detected.

        :param events: The events noticed since this was last called, oldest first.
        """
        described = [self._describe(event) for event in events]
        with self._lock:
            self._detected.extend(described)

    def _describe(self, event: DetectionEvent) -> DetectedEvent:
        """
        One segmind event as the viewer's timeline reads it.

        The run's own clock is read now rather than derived from the event's wall-clock
        stamp: a detection is handed over on the tick it was noticed on, and the wall
        clock has no idea how much of the run so far was spent paused.

        :param event: The event that was detected.
        """
        involved = (
            event.tracked_objects if isinstance(event, EventWithTrackedObjects) else []
        )
        return DetectedEvent(
            kind=type(event).__name__,
            detected_at=event.timestamp,
            seconds_into_run=self.clock.elapsed_seconds(),
            participants=[str(entity.name) for entity in involved],
        )
