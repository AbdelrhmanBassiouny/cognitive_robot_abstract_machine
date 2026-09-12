"""
When a plan node records itself as having started.

A plan is built long before it runs and its later nodes run long after its first, so
what a node keeps as its start has to be the moment it started running; anything that
reads a plan back against a clock -- a timeline of what the robot was doing -- depends
on it.
"""

from __future__ import annotations

import time
from datetime import datetime

from coraplex.datastructures.dataclasses import Context
from coraplex.language import CodeNode
from coraplex.plans.factories import code, sequential
from semantic_digital_twin.robots.minimal_robot import MinimalRobot

# %% the plan every test here performs

FIRST_NODE_RUNS_FOR = 0.05
"""
Seconds the first node of the plan runs, so the second one starts measurably later.
"""


def two_nodes_in_a_row(cylinder_bot_world) -> tuple[CodeNode, CodeNode]:
    """
    A performed sequence of two nodes, the first of which takes a while.

    :param cylinder_bot_world: The world the plan runs in.
    """
    context = Context(
        cylinder_bot_world,
        cylinder_bot_world.get_semantic_annotations_by_type(MinimalRobot)[0],
    )
    plan = sequential(
        [
            code(lambda: time.sleep(FIRST_NODE_RUNS_FOR), context=context),
            code(lambda: None, context=context),
        ],
        context,
    ).plan
    first, second = [node for node in plan.nodes if isinstance(node, CodeNode)]
    return plan, first, second


# %% when a node starts


def test_a_node_starts_when_it_is_performed_rather_than_when_it_is_built(
    cylinder_bot_world,
) -> None:
    plan, first, _ = two_nodes_in_a_row(cylinder_bot_world)
    built_at = datetime.now()

    plan.perform()

    assert first.start_time >= built_at


def test_the_second_node_of_a_sequence_starts_once_the_first_has_ended(
    cylinder_bot_world,
) -> None:
    plan, first, second = two_nodes_in_a_row(cylinder_bot_world)

    plan.perform()

    assert second.start_time >= first.end_time
