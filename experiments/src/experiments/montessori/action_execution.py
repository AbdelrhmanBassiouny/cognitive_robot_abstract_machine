"""
Having a running Montessori sort insert a shape the viewer picked, out of its own turn.

Two threads meet here, as they do in :mod:`experiments.montessori.run_control`: the
viewer's HTTP threads only ever add a request, and the thread running the sort takes
them one at a time at the checkpoint between shapes — the only place an insertion can be
started without interrupting one already under way.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from cramera.live.action_execution import (
    ActionExecutionState,
    LiveActionExecution,
    UnknownPerformableAction,
)
from typing_extensions import Dict, List, Optional

from experiments.montessori.performable_insertions import PerformableInsertion


@dataclass
class SortingActionExecution(LiveActionExecution):
    """
    A Montessori sort, as something the viewer can ask to insert a shape.
    """

    _offered: Dict[str, PerformableInsertion] = field(default_factory=dict)
    """
    The insertions this sort can carry out, by the name the viewer asks for them by.
    """

    _requested: List[str] = field(default_factory=list)
    """
    Names of the insertions asked for and not started yet, oldest first.
    """

    _performing: Optional[str] = None
    """
    Name of the insertion being carried out right now, or None while none is.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards every field above, between the viewer's threads and the sorting thread.
    """

    # %% what the viewer asks of it
    def title(self) -> str:
        """
        What the viewer names this demo.
        """
        return "Montessori sorting"

    def state(self) -> ActionExecutionState:
        """
        What this sort is doing with the insertions asked of it.
        """
        with self._lock:
            return ActionExecutionState(
                performing=self._performing, requested=list(self._requested)
            )

    def perform(self, name: str) -> None:
        """
        Queue one insertion, to be carried out at the next checkpoint between shapes.

        :param name: Name of the insertion the viewer asked for.
        :raises UnknownPerformableAction: When this scene offers no such insertion.
        """
        with self._lock:
            if name not in self._offered:
                raise UnknownPerformableAction(name=name, offered=sorted(self._offered))
            self._requested.append(name)

    # %% what the sorting thread asks of it
    def offer(self, insertions: List[PerformableInsertion]) -> None:
        """
        Declare what this sort can be asked to insert, as a newly built world offers it.

        Requests for a world that is gone are dropped with it: the shapes they name
        belong to bodies that no longer exist.

        :param insertions: The insertions the built scene makes possible.
        """
        with self._lock:
            self._offered = {insertion.name: insertion for insertion in insertions}
            self._requested = []
            self._performing = None

    def take_requested(self) -> Optional[PerformableInsertion]:
        """
        The insertion to carry out next, marked as being performed, or None when the
        viewer has asked for none.
        """
        with self._lock:
            if not self._requested:
                return None
            self._performing = self._requested.pop(0)
            return self._offered[self._performing]

    def finish_requested(self) -> None:
        """
        Record that the insertion in hand has been carried out.
        """
        with self._lock:
            self._performing = None
