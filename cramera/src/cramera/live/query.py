"""
What a running demo has to offer for its own state to be queryable.

The bridge depends on this abstraction only, so a demo supplies its domain vocabulary
without cramera knowing anything about that demo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from typing_extensions import List, TYPE_CHECKING

if TYPE_CHECKING:
    from cramera.knowledge.presets import Preset
    from cramera.knowledge.query_domain import QueryDomain


class NoQuerySourceRegistered(Exception):
    """
    Raised when the bridge is asked a question and no demo offered to answer it.
    """

    def __init__(self) -> None:
        super().__init__("no query source is registered on this bridge")


class LiveQuerySource(ABC):
    """
    One running demo's queryable state.

    A source declares what its state *is*; how a question is compiled, evaluated and
    rendered is not its concern.
    """

    @abstractmethod
    def title(self) -> str:
        """
        Short name of what is being queried, shown as the panel's answer source.
        """

    @abstractmethod
    def domains(self) -> List[QueryDomain]:
        """
        The ready-made variables a question about this demo may range over.

        Read whenever a query runs, so an answer reflects the demo's current state.
        """

    @abstractmethod
    def presets(self) -> List[Preset]:
        """
        Ready-made queries the panel offers as buttons.
        """
