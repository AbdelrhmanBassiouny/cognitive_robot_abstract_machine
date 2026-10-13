from __future__ import annotations

from dataclasses import dataclass

import pytest

from cramph.context import StatechartContext
from cramph.data_types import LifeCycleValues
from cramph.exceptions import (
    ConflictingTickDurationError,
    NodesMissingContextExtensionsError,
)
from cramph.executor import StatechartExecutor, TickingExecutorExtension
from cramph.nodes_for_testing import ConstTrueNode
from cramph.statechart import Statechart
from giskardpy.motion_control import MotionControl
from giskardpy.motion_statechart.context import MotionControlContext
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.monitors.monitors import LocalMinimumReached
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPosition
from semantic_digital_twin.spatial_types import Point3
from semantic_digital_twin.world import World

# %% context


def test_motion_control_ticks_at_the_control_rate():
    motion_control = MotionControl()
    context = StatechartContext(world=World())

    motion_control.extend_context(context)

    assert (
        context.require_tick_duration()
        == motion_control.qp_controller_config.control_time_step.total_seconds()
    )


def test_motion_control_hands_its_controller_configuration_to_the_nodes():
    motion_control = MotionControl()
    context = StatechartContext(world=World())

    motion_control.extend_context(context)

    assert (
        context.require_extension(MotionControlContext).qp_controller_config
        is motion_control.qp_controller_config
    )


def test_motion_control_rejects_a_context_ticking_at_another_rate():
    motion_control = MotionControl()
    context = StatechartContext(
        world=World(),
        tick_duration=motion_control.qp_controller_config.control_time_step.total_seconds()
        * 2,
    )

    with pytest.raises(ConflictingTickDurationError):
        motion_control.extend_context(context)


def test_a_node_reading_the_controller_configuration_needs_motion_control():
    statechart = Statechart(context=StatechartContext(world=World()))
    statechart.add_node(node := LocalMinimumReached())

    with pytest.raises(NodesMissingContextExtensionsError) as raised:
        statechart.compile()

    assert raised.value.nodes_by_missing_extension == {MotionControlContext: [node]}


# %% sharing a statechart with other modules


@dataclass
class ExtensionCountingTicks(TickingExecutorExtension):
    """
    An executor extension of another module, counting the ticks it was called after.
    """

    ticks: int = 0
    """
    How many ticks this extension was called after.
    """

    def after_tick(self, executor: StatechartExecutor) -> None:
        self.ticks += 1


def test_motion_nodes_and_nodes_of_other_modules_run_in_one_statechart(
    cylinder_bot_world: World,
):
    root = cylinder_bot_world.root
    tip = cylinder_bot_world.get_kinematic_structure_entity_by_name("bot")
    goal = CartesianPosition(
        root_link=root,
        tip_link=tip,
        goal_point=Point3(x=0.1, reference_frame=root),
    )
    other_node = ConstTrueNode()
    tick_counter = ExtensionCountingTicks()
    executor = StatechartExecutor(
        context=StatechartContext(world=cylinder_bot_world),
        extensions=[MotionControl(), tick_counter],
    )
    statechart = Statechart(context=executor.context)
    statechart.add_nodes(
        [goal, other_node, EndMotion.when_all_true([goal, other_node])]
    )

    executor.compile(statechart)
    executor.tick_until_end()

    assert statechart.is_ended()
    assert goal.life_cycle_state == LifeCycleValues.RUNNING
    assert other_node.life_cycle_state == LifeCycleValues.RUNNING
    assert tick_counter.ticks == executor.tick_count
    assert executor.require_extension(MotionControl).qp_controller is not None
