"""
Letting the viewer step through the queries a running demo asks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

# %% where a demo is held


class StepMoment(StrEnum):
    """
    The moments of a query a demo is held at.
    """

    ASKED = "asked"
    """
    The query was asked; nothing answers it yet.
    """

    ANSWERED = "answered"
    """
    The query's answering ended.
    """


@dataclass(frozen=True)
class HeldStep:
    """
    A query a demo is held at, and the moment of it.
    """

    number: int
    """
    The query's place among every query the demo asked, from 0.
    """

    moment: StepMoment
    """
    How far the query had come.
    """


# %% controlling the stepping


class QueryStepControl(ABC):
    """
    What holds a running demo at each query it asks, and lets the viewer move on.
    """

    @abstractmethod
    def advance(self, held_at: HeldStep | None = None) -> None:
        """
        Let the demo carry on from the step it is held at.

        :param held_at: The step the viewer saw the demo held at; the demo carries on
            only while it is still held there, so a viewer that has not yet seen a
            newer step cannot skip it.
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
