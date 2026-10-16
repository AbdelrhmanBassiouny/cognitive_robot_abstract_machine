from __future__ import division

from dataclasses import dataclass
from datetime import timedelta

from cramph.composites import Attempt, RepeatUntil
from cramph.context import StatechartContext
from cramph.node import StatechartNode
from giskardpy.motion_statechart.monitors.progress_monitors import Stalled


@dataclass(repr=False, eq=False, kw_only=True)
class RepeatOnStall(RepeatUntil):
    """
    Runs a task again from the start whenever it stops approaching its goal.

    A task with nothing converging beneath it never approaches anything, so
    :attr:`timeout` alone decides when such an attempt is given up on.
    """

    timeout: timedelta = timedelta(seconds=5)
    """
    Simulated time without progress after which an attempt counts as failed.
    """

    minimum_convergence_rate: float = 0.05
    """
    Rate below which a task counts as not approaching its goal, as a fraction of that
    task's own threshold per second.
    """

    def expand(self, context: StatechartContext) -> None:
        """
        Turn the task into an attempt that gives up on a stall, which is the decision
        this subclass exists to make for the caller, then wire the retry loop as
        :meth:`~cramph.composites.RepeatUntil.expand` does.

        A task that already is an :class:`Attempt` keeps its own failure monitors and
        gives up on a stall as well.
        """
        if isinstance(self.task, Attempt):
            self.task.failure_monitors.append(
                self._create_stall_monitor(self.task.task)
            )
        else:
            self.task = Attempt(
                name=f"{self.name}/attempt",
                task=self.task,
                failure_monitors=[self._create_stall_monitor(self.task)],
            )
        super().expand(context)

    def _create_stall_monitor(self, monitored_node: StatechartNode) -> Stalled:
        """
        :param monitored_node: The node whose progress is measured.
        :return: A monitor that fires once nothing under `monitored_node` has approached
            its goal for :attr:`timeout`.
        """
        return Stalled(
            name=f"{self.name}/progress",
            monitored_node=monitored_node,
            timeout=self.timeout,
            minimum_convergence_rate=self.minimum_convergence_rate,
        )
