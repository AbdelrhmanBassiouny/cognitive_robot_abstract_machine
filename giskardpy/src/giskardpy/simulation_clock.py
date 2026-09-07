from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SimulationClock(ABC):
    """
    A simulation's own notion of time, and whether that simulation can still advance it.

    A standing-still clock on its own says nothing about why it stands still: a
    simulation that is deliberately held reads exactly like one that has ended. Anything
    waiting on simulated time has to tell those apart, since the first is worth waiting
    for and the second never arrives.
    """

    @property
    @abstractmethod
    def time(self) -> float:
        """
        The simulation's current time in seconds.
        """

    @property
    @abstractmethod
    def has_stopped(self) -> bool:
        """
        Whether the simulation is over, so its time will never advance again.

        A paused simulation has not stopped: its time is standing still, but it is
        expected to resume.
        """
