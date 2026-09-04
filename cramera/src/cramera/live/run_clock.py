"""
How far a run has got, as the viewer's timeline measures along.

A timeline drawn against the wall clock keeps moving while the run it plots stands
still, so the marks on it and the instant it points at stop meaning the same thing. This
clock stops with the run instead, and starts again from zero when a new one begins.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from typing_extensions import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class RunClockReading:
    """
    What a run clock says at one instant, as the viewer's timeline reads it.
    """

    elapsed: float
    """
    Seconds the run has been going, excluding the time it spent paused.
    """

    running: bool
    """
    Whether :attr:`elapsed` is still growing.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the viewer's timeline reads.
        """
        return {"elapsed": self.elapsed, "running": self.running}


@dataclass
class RunClock:
    """
    A stopwatch over one run, paused and restarted along with it.

    Read on the viewer's HTTP threads while the run drives it from its own, so every
    reading and every change is taken under one lock.
    """

    monotonic_seconds: Callable[[], float] = time.monotonic
    """
    Where the elapsing time is read from, in seconds that only ever grow.
    """

    _started_at: float = field(default=0.0, init=False)
    """
    The reading this run began at.
    """

    _paused_at: Optional[float] = field(default=None, init=False)
    """
    The reading the run stopped at, or nothing while it is going.
    """

    _paused_total: float = field(default=0.0, init=False)
    """
    How much of the time since :attr:`_started_at` the run spent paused.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards every field above.
    """

    def __post_init__(self) -> None:
        self._started_at = self.monotonic_seconds()

    # %% what the timeline asks of it
    def reading(self) -> RunClockReading:
        """
        Where the run has got to, and whether it is still getting anywhere.
        """
        with self._lock:
            return RunClockReading(
                elapsed=self._elapsed(), running=self._paused_at is None
            )

    def elapsed_seconds(self) -> float:
        """
        Seconds the run has been going, excluding the time it spent paused.
        """
        with self._lock:
            return self._elapsed()

    def _elapsed(self) -> float:
        """
        Seconds the run has been going, with :attr:`_lock` already held.
        """
        until = self.monotonic_seconds() if self._paused_at is None else self._paused_at
        return until - self._started_at - self._paused_total

    # %% what the run asks of it
    def pause(self) -> None:
        """
        Stop measuring, leaving the reading where it stands.
        """
        with self._lock:
            if self._paused_at is None:
                self._paused_at = self.monotonic_seconds()

    def resume(self) -> None:
        """
        Carry on measuring from where a pause stopped.
        """
        with self._lock:
            if self._paused_at is None:
                return
            self._paused_total += self.monotonic_seconds() - self._paused_at
            self._paused_at = None

    def restart(self) -> None:
        """
        Measure a new run, from zero and going, whatever the last one was doing.
        """
        with self._lock:
            self._started_at = self.monotonic_seconds()
            self._paused_total = 0.0
            self._paused_at = None
