"""
The rolling recording a live demo keeps of itself, so moments of it can be replayed.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field

from typing_extensions import Any, Deque, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from cramera.live.bridge import WorldStateSnapshot


@dataclass(frozen=True)
class RecordedFrame:
    """
    One world snapshot as it was published, stamped with when it was captured.
    """

    at: float
    """
    When this frame was captured, in seconds since the epoch.
    """

    state: WorldStateSnapshot
    """
    The world snapshot captured at :attr:`at`.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON shape the replay viewer steps through: the capture time plus the
        snapshot parts that place the robot and the objects.
        """
        return {
            "at": self.at,
            "frames": self.state.frames,
            "base": self.state.base,
            "objects": self.state.objects,
        }


@dataclass
class DemoRecording:
    """
    A rolling record of a demo's world states, bounded in rate and duration.

    Written by the simulation thread on every published snapshot and read by HTTP
    threads serving replay clips, so all access is guarded by its own lock.
    """

    max_duration_seconds: float = 600.0
    """
    How far back frames are kept; older ones are dropped as new ones arrive.
    """

    min_interval_seconds: float = 0.05
    """
    The least time between two kept frames, capping the recording's rate below the
    simulation's own tick rate.
    """

    _frames: Deque[RecordedFrame] = field(default_factory=deque)
    """
    The kept frames, oldest first.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards :attr:`_frames` between the recording thread and the clip readers.
    """

    def record(self, at: float, state: WorldStateSnapshot) -> None:
        """
        Keep one world snapshot, unless the last kept frame is too recent.

        :param at: When the snapshot was captured, in seconds since the epoch.
        :param state: The snapshot to keep.
        """
        with self._lock:
            if self._frames and at - self._frames[-1].at < self.min_interval_seconds:
                return
            self._frames.append(RecordedFrame(at=at, state=state))
            horizon = at - self.max_duration_seconds
            while self._frames and self._frames[0].at < horizon:
                self._frames.popleft()

    def clip(self, start: float, end: float) -> List[RecordedFrame]:
        """
        The kept frames whose capture time falls within ``[start, end]``.

        :param start: When the clip begins, in seconds since the epoch.
        :param end: When the clip ends, in seconds since the epoch.
        """
        with self._lock:
            return [frame for frame in self._frames if start <= frame.at <= end]

    def clear(self) -> None:
        """
        Drop every kept frame, as when the recorded world is replaced.
        """
        with self._lock:
            self._frames.clear()
