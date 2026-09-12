"""
When a motion node records itself as having run.

A plan's motions are not performed one by one: the whole plan is compiled into one
motion statechart and ticked until it ends. What a motion node then knows of its own run
is read off its task in that chart, so that a plan read back afterwards says when each
of its motions ran rather than only when the plan was built.
"""

from __future__ import annotations

from dataclasses import dataclass

from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import simulated_robot
from coraplex.plans.factories import sequential
from coraplex.plans.plan_node import MotionNode
from coraplex.robot_plans.motions.base import BaseMotion
from giskardpy.motion_statechart.data_types import LifeCycleValues
from giskardpy.motion_statechart.graph_node import Task
from giskardpy.motion_statechart.nodes_for_testing.nodes_for_testing import TestGoal
from semantic_digital_twin.robots.minimal_robot import MinimalRobot

# %% a motion that takes a few ticks and moves nothing


@dataclass
class TicksAwhile(BaseMotion):
    """
    A motion whose chart is reached a few ticks after it starts, which is all a test of
    when a motion ran needs of one.
    """

    @property
    def _motion_chart(self) -> Task:
        return TestGoal(name=type(self).__name__)


# %% the plan every test here performs


def two_motions_in_a_row(cylinder_bot_world) -> tuple[MotionNode, MotionNode]:
    """
    Two motions performed one after the other, as one plan.

    :param cylinder_bot_world: The world the plan runs in.
    """
    context = Context(
        cylinder_bot_world,
        cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0],
    )
    plan = sequential([TicksAwhile(), TicksAwhile()], context).plan
    with simulated_robot:
        plan.perform()
    first, second = [node for node in plan.nodes if isinstance(node, MotionNode)]
    return first, second


# %% what a motion knows of its own run


def test_a_motion_that_ran_says_it_succeeded(cylinder_bot_world) -> None:
    first, second = two_motions_in_a_row(cylinder_bot_world)

    assert (first.status, second.status) == (
        LifeCycleValues.SUCCEEDED,
        LifeCycleValues.SUCCEEDED,
    )


def test_a_motion_ends_after_it_started(cylinder_bot_world) -> None:
    first, _ = two_motions_in_a_row(cylinder_bot_world)

    assert first.end_time > first.start_time


def test_the_second_motion_of_a_sequence_starts_once_the_first_has_ended(
    cylinder_bot_world,
) -> None:
    first, second = two_motions_in_a_row(cylinder_bot_world)

    assert second.start_time >= first.end_time
