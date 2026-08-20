from __future__ import division

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from typing_extensions import Optional

from krrood.symbolic_math.symbolic_math import trinary_logic_or, trinary_logic_not
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import (
    Goal,
    MotionStatechartNode,
    NodeArtifacts,
)


@dataclass(repr=False, eq=False)
class TryAll(Goal):
    """
    Takes a list of nodes and executes them in parallel.

    Its observation turns True as soon as any node is True and turns False only when all
    nodes are False, i.e. it only fails if every node fails.
    """

    nodes: List[MotionStatechartNode] = field(default_factory=list, init=True)
    """
    The child nodes executed in parallel.
    """

    def expand(self, context: MotionStatechartContext) -> None:
        """
        Add all child nodes to this goal so they run in parallel.
        """
        for node in self.nodes:
            self.add_node(node)

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        """
        Build an observation that is True as soon as any child node is True.
        """
        observations = [node.observation_variable for node in self.nodes]
        observation = (
            observations[0]
            if len(observations) == 1
            else trinary_logic_or(*observations)
        )
        return NodeArtifacts(observation=observation)


@dataclass(repr=False, eq=False)
class TryInOrder(Goal):
    """
    Takes a list of nodes and tries them one after another, short-circuiting on the
    first success.

    The next node only starts once the previous node failed; as soon as a node succeeds
    the remaining nodes are skipped. Its observation turns True if any node is True and
    turns False only when all nodes are False, i.e. it only fails if every node fails.
    """

    nodes: List[MotionStatechartNode] = field(default_factory=list, init=True)
    """
    The child nodes tried one after another, in order.
    """

    def expand(self, context: MotionStatechartContext) -> None:
        """
        Add the child nodes and wire them so each one starts only after the previous one
        failed, short-circuiting on the first success.
        """
        last_node: Optional[MotionStatechartNode] = None
        for node in self.nodes:
            self.add_node(node)
            if last_node is not None:
                # Start the next node only if the previous one failed (short-circuit on success).
                node.start_condition = trinary_logic_not(last_node.observation_variable)
            # End this node as soon as it is decided (True or False) so the chain can advance/finish.
            node.end_condition = trinary_logic_or(
                node.observation_variable, trinary_logic_not(node.observation_variable)
            )
            last_node = node

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        """
        Build an observation that is True as soon as any child node is True.
        """
        observations = [node.observation_variable for node in self.nodes]
        observation = (
            observations[0]
            if len(observations) == 1
            else trinary_logic_or(*observations)
        )
        return NodeArtifacts(observation=observation)


# %% monitored subtrees


@dataclass(repr=False, eq=False)
class MonitoredGoal(Goal, ABC):
    """
    Runs a monitored node next to the monitor observing it.

    The two are siblings, which is what lets the monitor's observation drive the monitored
    node's life cycle: a transition condition may only reference the owning node or a
    sibling of it. Neither node is chained to the other, so the monitor observes from the
    moment this goal starts.
    """

    monitor: MotionStatechartNode = field(kw_only=True)
    """
    The node whose observation controls the monitored node.
    """

    monitored_node: Optional[MotionStatechartNode] = field(default=None, kw_only=True)
    """
    The node placed under the monitor's control.
    """

    def expand(self, context: MotionStatechartContext) -> None:
        self.add_node(self.monitor)
        self.add_node(self.monitored_node)
        self.wire_monitor()

    @abstractmethod
    def wire_monitor(self) -> None:
        """
        Connect the monitor's observation to the monitored node's life cycle.
        """

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        return NodeArtifacts(observation=self.monitored_node.observation_variable)


@dataclass(repr=False, eq=False)
class PausedWhileTrue(MonitoredGoal):
    """
    Holds the monitored node for as long as the monitor observes True, and lets it continue
    once the monitor turns False again.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.pause_condition = self.monitor.observation_variable


@dataclass(repr=False, eq=False)
class StoppedWhenTrue(MonitoredGoal):
    """
    Ends the monitored node as soon as the monitor observes True.

    Its observation turns True once the monitored node finished *or* the monitor stopped
    it, so a stopped subtree still lets the surrounding motion advance and terminate.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.end_condition = self.monitor.observation_variable

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        return NodeArtifacts(
            observation=trinary_logic_or(
                self.monitored_node.observation_variable,
                self.monitor.observation_variable,
            )
        )
