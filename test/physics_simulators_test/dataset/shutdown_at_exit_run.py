"""
A run that registers a shutdown to be run when its interpreter exits.

Run as ``python shutdown_at_exit_run.py <case>``; what it prints says whether the
registered shutdown ran.
"""

from __future__ import annotations

import gc
import sys
from dataclasses import dataclass
from enum import StrEnum

from physics_simulators.shutdown_at_exit import ShutdownAtExit

SHUTDOWN_RAN = "the shutdown ran"
"""
What the run prints when the registered shutdown is called.
"""


class ShutdownCase(StrEnum):
    """
    What a run leaves behind when it reaches the end.
    """

    REGISTERED = "registered"
    """
    Keeps both the object and its registration.
    """

    CANCELLED = "cancelled"
    """
    Takes the registration back.
    """

    COLLECTED = "collected"
    """
    Drops the object, leaving nothing to shut down.
    """


@dataclass
class AnnouncesItsShutdown:
    """
    An object that says on standard output that it has been shut down.
    """

    def shut_down(self) -> None:
        """
        Announce the shutdown.
        """
        print(SHUTDOWN_RAN)


if __name__ == "__main__":
    case = ShutdownCase(sys.argv[1])
    subject = AnnouncesItsShutdown()
    registration = ShutdownAtExit.register(subject.shut_down)
    if case is ShutdownCase.CANCELLED:
        registration.cancel()
    elif case is ShutdownCase.COLLECTED:
        del subject
        gc.collect()
