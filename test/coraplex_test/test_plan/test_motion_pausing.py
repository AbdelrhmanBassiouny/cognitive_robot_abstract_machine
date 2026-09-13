"""
Whose pause a paused motion is.

A plan pauses its own motions to steer the chart that runs them, and the tick loop holds
off ticking for as long as one of them is paused. A chart pauses tasks of its own accord
too, through a monitor the plan attached to them -- but that pause is lifted by the very
ticking the loop would stop, so it must never reach the plan's motions.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from coraplex.datastructures.dataclasses import Context
from coraplex.exceptions import MotionDidNotFinish
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import pause_until
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from giskardpy.motion_statechart.data_types import LifeCycleValues
from giskardpy.motion_statechart.nodes_for_testing.nodes_for_testing import (
    ConstFalseNode,
)
from semantic_digital_twin.datastructures.definitions import TorsoState

from .test_graph_parsing import parse_and_compile

TICKS_A_HELD_MOTION_MAY_SPEND = 20
"""
The control cycles the run below gives its one motion.

Small enough to spend them in a test, since a motion held by a monitor that never lifts
spends every one of them.
"""

# %% a pause the chart holds


def test_a_task_the_chart_holds_paused_does_not_pause_its_motion(
    immutable_model_world, rclpy_node
):
    """
    A motion whose task the chart is holding keeps the status it had, so the tick loop
    does not read the chart's pause as the plan's.
    """
    world, view, context = immutable_model_world
    plan = pause_until(
        [MoveTorsoAction(TorsoState.HIGH)],
        monitor=ConstFalseNode(name="never"),
        context=context,
    )
    executable = parse_and_compile(plan, world, context)
    [(motion, task)] = executable.motion_mappings.items()
    executable.motion_state_chart.life_cycle_state[task] = LifeCycleValues.PAUSED
    ticked_at = datetime.now()

    executable.keep_the_motions_in_step(started_at=ticked_at, ended_at=ticked_at)

    assert motion.status is LifeCycleValues.NOT_STARTED
    assert not executable.is_paused


def test_a_monitor_that_never_lifts_its_pause_spends_the_motions_control_cycles(
    immutable_model_world,
):
    """
    Holding the children until a monitor that never turns True ends the run the way
    :class:`~coraplex.language.PauseUntilMonitor` says it does, rather than leaving the
    tick loop waiting on a pause only ticking could lift.
    """
    world, view, _ = immutable_model_world
    plan = pause_until(
        [MoveTorsoAction(TorsoState.HIGH)],
        monitor=ConstFalseNode(name="never"),
        context=Context(world, view, ticks_per_motion=TICKS_A_HELD_MOTION_MAY_SPEND),
    ).plan

    with pytest.raises(MotionDidNotFinish):
        with simulated_robot:
            plan.perform()
