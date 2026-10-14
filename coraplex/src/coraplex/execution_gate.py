"""
Pausing a robot between two control ticks, and resuming it where it stopped.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class ExecutionGate:
    """
    Lets whoever watches a robot pause its motions and resume them.

    The control loop passes the gate before every tick, so a paused robot holds the
    state it reached and carries on from it once resumed.
    """

    _running: threading.Event = field(default_factory=threading.Event, init=False)
    """
    Set while the robot may move.
    """

    def __post_init__(self) -> None:
        self._running.set()

    @property
    def is_paused(self) -> bool:
        """
        :return: Whether the robot is held still.
        """
        return not self._running.is_set()

    def pause(self) -> None:
        """
        Hold the robot still at its next control tick.
        """
        self._running.clear()

    def resume(self) -> None:
        """
        Let the robot carry on from where it was held.
        """
        self._running.set()

    def wait_while_paused(self) -> None:
        """
        Return as soon as the robot may move.
        """
        self._running.wait()
