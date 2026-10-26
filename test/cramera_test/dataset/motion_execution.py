"""
Plan and history fixtures for browser execution observers.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cramph.composites import Sequence
from cramph.context import StatechartContext
from cramph.data_types import LifeCycleValues
from cramph.node import StatechartNode
from cramph.nodes_for_testing import ConstTrueNode
from cramph.state_history import StateHistoryItem
from cramph.statechart import Statechart
from semantic_digital_twin.world import World

from cramera.live.bridge import Bridge
from cramera.live.visualization import StatechartPublishing

# %% motion execution fixture


@dataclass
class MotionExecution:
    """
    A plan and the statechart running it, observed by one statechart publishing.
    """

    plan: Sequence
    """
    The root of the plan.
    """

    motion: StatechartNode
    """
    The step the plan runs.
    """

    chart: Statechart
    """
    The statechart that records life cycle changes.
    """

    bridge: Bridge
    """
    The published plan and chart state.
    """

    publishing: StatechartPublishing
    """
    The publishing observing this plan's history.
    """

    def compile(self) -> None:
        """
        Tell the publishing the statechart is about to run, as a
        :class:`~cramera.live.visualization.LiveVisualization` does once its executor
        compiled it.
        """
        self.publishing.observe(self.chart)

    def record(self, state: LifeCycleValues) -> None:
        """
        Record one life cycle state of every node as a snapshot.

        :param state: The state assigned to every chart node.
        """
        self.chart.life_cycle_state.data[:] = state
        self.chart.state_history.append(
            StateHistoryItem(
                tick_count=len(self.chart.state_history),
                life_cycle_state=self.chart.life_cycle_state,
                observation_state=self.chart.observation_state,
            )
        )


@pytest.fixture()
def motion_execution() -> MotionExecution:
    """
    A plan of one step in a statechart, without anything ticking it.
    """
    motion = ConstTrueNode(name="Transport")
    plan = Sequence(nodes=[motion])
    chart = Statechart(context=StatechartContext(world=World()))
    chart.add_node(plan)
    bridge = Bridge()
    publishing = StatechartPublishing(bridge=bridge)
    return MotionExecution(plan, motion, chart, bridge, publishing)
