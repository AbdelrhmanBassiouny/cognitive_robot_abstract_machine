"""
What a running demo has to offer for the viewer to drive it.

The bridge depends on this abstraction only: it relays commands and republishes state,
while what pausing or restarting *means* stays with the demo that registered itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from krrood.exceptions import DataclassException
from typing_extensions import Any, Dict


class RunCommand(StrEnum):
    """
    What the viewer can ask a running demo to do.
    """

    PAUSE = "pause"
    """
    Stop the run where it stands, so its state can be inspected and asked about.
    """

    RESUME = "resume"
    """
    Carry on from where a pause stopped.
    """

    RESTART = "restart"
    """
    Abandon the current run and execute the whole thing again from the start.
    """

    ENABLE_LOOP = "enable_loop"
    """
    Keep starting a new run each time one finishes.
    """

    DISABLE_LOOP = "disable_loop"
    """
    Stop after the run in progress.
    """

    @classmethod
    def of_name(cls, name: str) -> RunCommand:
        """
        Read a command off the wire.

        :param name: The command name as the viewer sent it.
        :raises UnknownRunCommand: When no command goes by that name.
        """
        if name not in cls._value2member_map_:
            raise UnknownRunCommand(name=name)
        return cls(name)


class RunActivity(StrEnum):
    """
    What a run is busy with, for the viewer to say so rather than only *paused* or not.
    """

    STARTING = "starting"
    """
    Building the world the run needs.
    """

    SORTING = "sorting"
    """
    Executing the run itself.
    """

    FINISHED = "finished"
    """
    Done, and holding its final state for inspection.
    """


@dataclass
class NoRunControlRegistered(DataclassException):
    """
    Raised when the bridge is asked to drive a run and no demo offered to be driven.
    """

    def error_message(self) -> str:
        return "no run control is registered on this bridge"

    def suggest_correction(self) -> str:
        return "Start the demo with its viewer support enabled."


@dataclass
class UnknownRunCommand(DataclassException):
    """
    Raised when the viewer asks for something that is not a :class:`RunCommand`.
    """

    name: str
    """
    The command name that was sent.
    """

    def error_message(self) -> str:
        return "'%s' is not a run command" % self.name

    def suggest_correction(self) -> str:
        return "Use one of: %s." % ", ".join(command.value for command in RunCommand)


@dataclass(frozen=True)
class RunControlState:
    """
    Where a run stands, as the viewer's controls render it.
    """

    paused: bool
    """
    Whether the run is stopped where it stands.
    """

    looping: bool
    """
    Whether another run starts once this one finishes.
    """

    restart_pending: bool
    """
    Whether a restart was asked for and has not been acted on yet.
    """

    activity: RunActivity
    """
    What the run is busy with.
    """

    iteration: int
    """
    Which run this is, counting from the first.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the viewer's controls read.

        Carries no title: which demo this is stays with the control, not with the state
        it reports over and over.
        """
        return {
            "paused": self.paused,
            "looping": self.looping,
            "restart_pending": self.restart_pending,
            "activity": self.activity.value,
            "iteration": self.iteration,
        }


class LiveRunControl(ABC):
    """
    One running demo, as something the viewer can drive.
    """

    @abstractmethod
    def title(self) -> str:
        """
        Short name of the run, shown beside its controls.
        """

    @abstractmethod
    def state(self) -> RunControlState:
        """
        Where the run stands right now.
        """

    @abstractmethod
    def apply(self, command: RunCommand) -> None:
        """
        Do what the viewer asked, or record it to be done at the next safe point.

        :param command: What the viewer asked for.
        """
