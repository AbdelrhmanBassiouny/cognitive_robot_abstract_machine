from __future__ import division

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from typing_extensions import Optional

import krrood.symbolic_math.symbolic_math as sm
from krrood.symbolic_math.symbolic_math import (
    sum,
    trinary_logic_and,
    trinary_logic_not,
    trinary_logic_or,
)
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import (
    Goal,
    MotionStatechartNode,
    NodeArtifacts,
    TerminalNode,
)
from giskardpy.motion_statechart.monitors.progress_monitors import ProgressStalled


@dataclass(repr=False, eq=False)
class Sequence(Goal):
    """
    Takes a list of nodes and wires their start/end conditions such that they are
    executed in order.

    Its observation is the observation of the last node in the sequence.
    """

    nodes: List[MotionStatechartNode] = field(default_factory=list, init=True)

    def expand(self, context: MotionStatechartContext) -> None:
        last_node: Optional[MotionStatechartNode] = None
        for i, node in enumerate(self.nodes):
            self.add_node(node)
            if last_node is not None:
                node.start_condition = last_node.observation_variable
            # A node that ends the motion has nothing left to transition to.
            if not isinstance(node, TerminalNode):
                node.end_condition = node.observation_variable
            last_node = node

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        return NodeArtifacts(observation=self.nodes[-1].observation_variable)


@dataclass(repr=False, eq=False)
class Parallel(Goal):
    """
    Takes a list of nodes and executes them in parallel.

    This nodes' observation state turns True when up to `minimum_success` nodes are
    True.
    """

    nodes: List[MotionStatechartNode] = field(default_factory=list, init=True)
    minimum_success: Optional[int] = field(default=None, kw_only=True)
    """
    Defines the minimum number of nodes that must be True for the goal to be achieved.

    Defaults to None, which means that all nodes must be True.
    """

    def expand(self, context: MotionStatechartContext) -> None:
        for node in self.nodes:
            self.add_node(node)

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        true_observation_variables = [
            x.observation_variable == True for x in self.nodes
        ]
        minimum_success = (
            self.minimum_success
            if self.minimum_success is not None
            else len(self.nodes)
        )
        return NodeArtifacts(
            observation=minimum_success <= sum(*true_observation_variables)
        )


# %% repeating a task


@dataclass(repr=False, eq=False)
class RepeatUntil(Goal, ABC):
    """
    Runs a task again from the start whenever an attempt at it fails.

    Its observation turns True once the task succeeds and False once :attr:`monitor` calls
    the retrying off, so a caller can tell "eventually worked" from "gave up".

    Subclasses decide what a failed attempt is by implementing
    :meth:`create_failure_monitor`.
    """

    task: MotionStatechartNode = field(kw_only=True)
    """
    The node to run, and to run again after every failed attempt.
    """

    monitor: MotionStatechartNode = field(kw_only=True)
    """
    Stops the retrying once it observes True, which makes this goal observe False.
    """

    _attempt: Optional[Sequence] = field(default=None, init=False, repr=False)
    """
    Wraps :attr:`task`, so that one run of it can be reset as a unit.
    """

    _failure_monitor: Optional[MotionStatechartNode] = field(
        default=None, init=False, repr=False
    )
    """
    Detects that the current attempt failed, created by :meth:`create_failure_monitor`.
    """

    @property
    def attempt(self) -> Sequence:
        """
        :return: The goal wrapping the task, one run of which is one attempt.
        """
        return self._attempt

    @property
    def failure_monitor(self) -> MotionStatechartNode:
        """
        :return: The node whose observation decides that an attempt failed.
        """
        return self._failure_monitor

    @abstractmethod
    def create_failure_monitor(self, attempt: Sequence) -> MotionStatechartNode:
        """
        :param attempt: The goal wrapping the task, one run of which is one attempt.
        :return: A node whose True observation means the attempt failed and the task
            should be run again.
        """

    def expand(self, context: MotionStatechartContext) -> None:
        """
        Wire the retry loop.

        The failure monitor resets the attempt and itself with the same observation. A
        node that has been reset observes Unknown, so the reset lasts a single control
        cycle instead of holding the attempt at the start line, and the monitor is armed
        again for the next attempt.
        """
        self._attempt = Sequence(nodes=[self.task], name=f"{self.name}/attempt")
        self.add_node(self._attempt)
        self._failure_monitor = self.create_failure_monitor(self._attempt)
        self.add_nodes([self._failure_monitor, self.monitor])

        # Each observation is compared against True, so that an undecided Unknown counts
        # as neither, and the results combine as plain booleans.
        attempt_succeeded = sm.Scalar(
            self._attempt.observation_variable == sm.Scalar.const_true()
        )
        attempt_failed = sm.Scalar(
            self._failure_monitor.observation_variable == sm.Scalar.const_true()
        )
        still_trying = trinary_logic_not(
            sm.Scalar(self.monitor.observation_variable == sm.Scalar.const_true())
        )

        # Starting is gated as well as ending, because a reset attempt is not started and
        # ending is not considered while it is not.
        self._attempt.start_condition = still_trying
        # A failure that arrives on the same control cycle as the success must not undo
        # it, and resetting takes precedence over ending.
        self._attempt.reset_condition = trinary_logic_and(
            attempt_failed, trinary_logic_not(attempt_succeeded), still_trying
        )
        self._attempt.end_condition = trinary_logic_or(
            self._attempt.observation_variable,
            self.monitor.observation_variable,
        )
        self._failure_monitor.reset_condition = trinary_logic_and(
            attempt_failed, still_trying
        )
        self._failure_monitor.end_condition = self.monitor.observation_variable

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        """
        Report success, giving up, or neither.

        The cases are compared against True rather than combined with trinary logic,
        because an undecided attempt is Unknown and would otherwise read as a success.
        """
        return NodeArtifacts(
            observation=sm.if_cases(
                cases=[
                    (
                        sm.Scalar(
                            self._attempt.observation_variable == sm.Scalar.const_true()
                        ),
                        sm.Scalar.const_true(),
                    ),
                    (
                        sm.Scalar(
                            self.monitor.observation_variable == sm.Scalar.const_true()
                        ),
                        sm.Scalar.const_false(),
                    ),
                ],
                else_result=sm.Scalar.const_trinary_unknown(),
            )
        )


@dataclass(repr=False, eq=False)
class RepeatOnStall(RepeatUntil):
    """
    Runs a task again from the start whenever it stops approaching its goal.

    .. note:: The task must contain at least one
        :class:`~giskardpy.motion_statechart.graph_node.ConvergingTask`, because progress
        is measured from a task's error. Watching anything else raises
        :class:`~giskardpy.motion_statechart.exceptions.NoConvergingTaskError` while the
        motion statechart is compiled.
    """

    timeout: float = field(default=5.0, kw_only=True)
    """
    Seconds of simulated time without progress after which an attempt counts as failed.
    """

    minimum_convergence_rate: float = field(default=0.05, kw_only=True)
    """
    Rate below which a task counts as not approaching its goal, as a fraction of that
    task's own threshold per second.
    """

    def create_failure_monitor(self, attempt: Sequence) -> MotionStatechartNode:
        return ProgressStalled(
            name=f"{self.name}/stalled",
            monitored_node=attempt,
            timeout=self.timeout,
            minimum_convergence_rate=self.minimum_convergence_rate,
        )
