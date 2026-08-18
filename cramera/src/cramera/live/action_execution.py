"""
What a running demo has to offer for the viewer to have it act.

The bridge depends on this abstraction only: it relays the request and republishes what
became of it, while what an action *is* and when it is safe to run stays with the demo
that registered itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from krrood.exceptions import DataclassException
from typing_extensions import Any, Dict, List, Optional


@dataclass
class NoActionExecutionRegistered(DataclassException):
    """
    Raised when the bridge is asked to have an action performed and no demo offered to
    perform one.
    """

    def error_message(self) -> str:
        return "no action execution is registered on this bridge"

    def suggest_correction(self) -> str:
        return "Start the demo with its viewer support enabled."


@dataclass
class UnknownPerformableAction(DataclassException):
    """
    Raised when the viewer asks for an action the running demo cannot perform.
    """

    name: str
    """
    The action name that was asked for.
    """

    offered: List[str] = field(default_factory=list)
    """
    The names the demo does perform.
    """

    def error_message(self) -> str:
        return "'%s' is not an action this demo performs" % self.name

    def suggest_correction(self) -> str:
        if not self.offered:
            return "Ask a query that answers with actions to see what can be performed."
        return "Use one of: %s." % ", ".join(self.offered)


@dataclass(frozen=True)
class ActionExecutionState:
    """
    What a running demo is doing with the actions the viewer asked it to perform.
    """

    performing: Optional[str] = None
    """
    Name of the action being carried out right now, or None while none is.
    """

    requested: List[str] = field(default_factory=list)
    """
    Names of the actions asked for and not started yet, in the order they were asked
    for.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the viewer's perform buttons read.

        Carries no title: which demo this is stays with the execution, not with the
        state it reports over and over.
        """
        return {"performing": self.performing, "requested": list(self.requested)}


class LiveActionExecution(ABC):
    """
    One running demo, as something the viewer can have carry out an action.
    """

    @abstractmethod
    def title(self) -> str:
        """
        Short name of what performs the actions, shown beside their buttons.
        """

    @abstractmethod
    def state(self) -> ActionExecutionState:
        """
        What the demo is doing with the actions asked of it right now.
        """

    @abstractmethod
    def perform(self, name: str) -> None:
        """
        Carry out the named action, or record it to be carried out at the next safe
        point.

        :param name: Name of the action the viewer asked for, as its answer row carried
            it.
        :raises UnknownPerformableAction: When the demo performs no action by that name.
        """
