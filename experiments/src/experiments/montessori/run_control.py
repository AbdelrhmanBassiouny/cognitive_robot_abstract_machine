"""
Driving a running Montessori sort from the viewer: pause it, restart it, loop it.

Two threads meet here. The viewer's HTTP threads only ever set flags; the thread running
the sort reads them at checkpoints between attempts, which is the only place a run can
be abandoned without leaving a half-executed plan behind. Pausing is the exception — it
freezes the physics simulation directly, so the robot stops where it is rather than at
the next checkpoint.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from cramera.live.run_control import (
    LiveRunControl,
    RunActivity,
    RunCommand,
    RunControlState,
)
from typing_extensions import Optional, Protocol, runtime_checkable


@runtime_checkable
class PausableSimulation(Protocol):
    """
    A physics simulation that can be stopped and started where it stands.
    """

    def pause_simulation(self) -> None:
        """
        Stop stepping physics, leaving the world exactly as it is.
        """

    def unpause_simulation(self) -> None:
        """
        Step physics again from where it stopped.
        """


@dataclass
class SortingRunControl(LiveRunControl):
    """
    A Montessori sort, as something the viewer can pause, restart and loop.
    """

    wait_poll_seconds: float = 0.2
    """
    How long a waiting checkpoint sleeps between re-checks.

    Bounded rather than indefinite so a run waiting here still answers a keyboard
    interrupt.
    """

    _paused: bool = False
    """
    Whether the run is stopped where it stands.
    """

    _looping: bool = False
    """
    Whether another iteration starts once this one finishes.
    """

    _restart_requested: bool = False
    """
    Whether a restart was asked for and has not been acted on yet.
    """

    _activity: RunActivity = RunActivity.STARTING
    """
    What the run is busy with.
    """

    _iteration: int = 0
    """
    Which iteration is running, counting from the first.
    """

    _simulation: Optional[PausableSimulation] = None
    """
    The physics simulation of the iteration in progress, rebuilt with each of them.
    """

    _condition: threading.Condition = field(default_factory=threading.Condition)
    """
    Guards every field above, and wakes the sorting thread when one of them changes.
    """

    # %% what the viewer asks of it
    def title(self) -> str:
        """
        What the viewer names this run.
        """
        return "Montessori sorting"

    def state(self) -> RunControlState:
        """
        Where the run stands right now.
        """
        with self._condition:
            return RunControlState(
                paused=self._paused,
                looping=self._looping,
                restart_pending=self._restart_requested,
                activity=self._activity,
                iteration=self._iteration,
            )

    def apply(self, command: RunCommand) -> None:
        """
        Do what the viewer asked, or record it for the next checkpoint.

        :param command: What the viewer asked for.
        """
        with self._condition:
            if command is RunCommand.PAUSE:
                self._pause()
            elif command is RunCommand.RESUME:
                self._resume()
            elif command is RunCommand.RESTART:
                self._restart_requested = True
                # a restart is honoured at the next checkpoint, which a paused run never
                # reaches, so asking for one has to let the run go
                self._resume()
            elif command is RunCommand.ENABLE_LOOP:
                self._looping = True
            elif command is RunCommand.DISABLE_LOOP:
                self._looping = False
            self._condition.notify_all()

    def _pause(self) -> None:
        """
        Freeze the physics of the iteration in progress, holding :attr:`_condition`.
        """
        self._paused = True
        if self._simulation is not None:
            self._simulation.pause_simulation()

    def _resume(self) -> None:
        """
        Step the physics of the iteration in progress again, holding :attr:`_condition`.
        """
        if not self._paused:
            return
        self._paused = False
        if self._simulation is not None:
            self._simulation.unpause_simulation()

    # %% what the sorting thread asks of it
    def begin_iteration(self, iteration: int, simulation: PausableSimulation) -> None:
        """
        Take over the simulation one iteration just built.

        A run paused across a rebuild stays paused: the freeze is re-applied to the
        simulation that now exists, since the one it was applied to is gone.

        :param iteration: Which iteration this is, counting from the first.
        :param simulation: The physics simulation this iteration runs in.
        """
        with self._condition:
            self._iteration = iteration
            self._simulation = simulation
            self._activity = RunActivity.SORTING
            if self._paused:
                simulation.pause_simulation()
            self._condition.notify_all()

    def finish_iteration(self) -> None:
        """
        Record that the iteration in progress is done.
        """
        with self._condition:
            self._activity = RunActivity.FINISHED
            self._condition.notify_all()

    def wait_while_paused(self) -> None:
        """
        Hold the sorting thread here for as long as the run is paused.

        Called at the points a run can be held without leaving anything half-done: the
        physics is already frozen by then, so this only keeps the next action from being
        started.
        """
        with self._condition:
            while self._paused:
                self._condition.wait(self.wait_poll_seconds)

    def restart_is_pending(self) -> bool:
        """
        Whether the run in progress should be abandoned at this checkpoint.
        """
        with self._condition:
            return self._restart_requested

    def consume_restart(self) -> None:
        """
        Record that a pending restart has been acted on.
        """
        with self._condition:
            self._restart_requested = False
            self._condition.notify_all()

    def wants_another_iteration(self) -> bool:
        """
        Whether a further iteration should be built once this one is torn down.
        """
        with self._condition:
            return self._looping or self._restart_requested

    def wait_for_another_iteration(self) -> None:
        """
        Hold the sorting thread here until the viewer asks for a further iteration.

        This is what a finished single run idles in, so its world stays up and its
        questions stay answerable until someone asks for the next one.
        """
        with self._condition:
            while not (self._looping or self._restart_requested):
                self._condition.wait(self.wait_poll_seconds)
