from __future__ import division

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import Goal, MotionStatechartNode, NodeArtifacts
from krrood.symbolic_math.symbolic_math import trinary_logic_not, trinary_logic_or


@dataclass(repr=False, eq=False)
class MonitoredGoal(Goal, ABC):
    """
    Runs a monitored node next to the monitor observing it.

    The two are siblings, which is what lets the monitor's observation drive the
    monitored node's life cycle: a transition condition may only reference the owning
    node or a sibling of it. Neither node is chained to the other, so the monitor
    observes from the moment this goal starts.
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
    Holds the monitored node for as long as the monitor observes True, and lets it
    continue once the monitor turns False again.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.pause_condition = self.monitor.observation_variable


@dataclass(repr=False, eq=False)
class PausedUntilTrue(MonitoredGoal):
    """
    Holds the monitored node until the monitor observes True, and lets it continue from
    then on.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.pause_condition = trinary_logic_or(
            self.monitored_node.pause_condition,
            trinary_logic_not(self.monitor.observation_variable),
        )


@dataclass(repr=False, eq=False)
class StoppedWhenTrue(MonitoredGoal):
    """
    Ends the monitored node as soon as the monitor observes True.

    Its observation turns True once the monitored node finished *or* the monitor stopped
    it, so a stopped subtree still lets the surrounding motion advance and terminate.
    """

    def wire_monitor(self) -> None:
        self.monitored_node.end_condition = trinary_logic_or(self.monitored_node.end_condition, self.monitor.observation_variable)

    def build_artifacts(self, context: MotionStatechartContext) -> NodeArtifacts:
        return NodeArtifacts(
            observation=trinary_logic_or(
                self.monitored_node.observation_variable,
                self.monitor.observation_variable,
            )
        )
