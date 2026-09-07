"""
Time a test moves on by hand, for anything measured against a monotonic reading.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WoundClock:
    """
    A monotonic reading that only ever moves when a test says it does.
    """

    seconds: float = 0.0
    """
    What the reading currently is.
    """

    def read(self) -> float:
        """
        The reading as it stands.
        """
        return self.seconds

    def advance(self, seconds: float) -> None:
        """
        Let that much time pass.

        :param seconds: How much time passes.
        """
        self.seconds += seconds
