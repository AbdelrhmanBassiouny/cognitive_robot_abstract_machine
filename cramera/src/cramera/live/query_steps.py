"""
Letting the viewer step through the queries a running demo asks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class QueryStepControl(ABC):
    """
    What holds a running demo at each query it asks, and lets the viewer move on.
    """

    @abstractmethod
    def advance(self) -> None:
        """
        Let the demo carry on from the step it is held at.
        """

    @abstractmethod
    def set_stepping(self, is_stepping: bool, holds_nested: bool) -> None:
        """
        Choose whether the demo is held at every query it asks.

        :param is_stepping: Whether the demo is held at every query until the viewer
            moves on.
        :param holds_nested: Whether it is also held at queries asked while another is
            answered.
        """
