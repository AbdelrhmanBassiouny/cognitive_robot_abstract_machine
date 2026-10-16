"""
Building and running coraplex plans in tests: the context extensions a test robot's
plans read, and the simulated executor running them.
"""

from __future__ import annotations

from dataclasses import replace

from typing_extensions import List

from coraplex.plans.context_extensions import RobotAccess, StatementGrounding
from coraplex.plans.executors import (
    PlanExecutor,
    RealRobotPlanExecutor,
    SimulatedPlanExecutor,
)
from cramph.context import ContextExtension, StatechartContext
from cramph.executor import SimulationPacer
from cramph.node import StatechartNode
from cramph.statechart import Statechart
from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.world import World
from .sampling import SAMPLING_SEED


def robot_extensions(robot: AbstractRobot) -> List[ContextExtension]:
    """
    :param robot: The robot performing the plans.
    :return: The context extensions a plan of `robot` reads, sampling with
        :data:`SAMPLING_SEED`.
    """
    return [RobotAccess(robot), StatementGrounding(sampling_seed=SAMPLING_SEED)]


def with_grounding(
    extensions: List[ContextExtension], **changes
) -> List[ContextExtension]:
    """
    :param extensions: The context extensions of a plan.
    :param changes: The fields of its
        :class:`~coraplex.plans.context_extensions.StatementGrounding` to change.
    :return: `extensions`, its grounding replaced by one with `changes` applied.
    """
    return [
        (
            replace(extension, **changes)
            if isinstance(extension, StatementGrounding)
            else extension
        )
        for extension in extensions
    ]


def simulated_executor(
    extensions: List[ContextExtension], **options
) -> SimulatedPlanExecutor:
    """
    :param extensions: The context extensions of the plan, holding a
        :class:`~coraplex.plans.context_extensions.RobotAccess`.
    :param options: Further arguments of the executor.
    :return: An executor simulating plans in the world of the robot in `extensions`.
    """
    return SimulatedPlanExecutor(
        world_of(extensions), context_extensions=extensions, **options
    )


def robot_executor(
    extensions: List[ContextExtension], **options
) -> RealRobotPlanExecutor:
    """
    :param extensions: The context extensions of the plan, holding a
        :class:`~coraplex.plans.context_extensions.RobotAccess`.
    :param options: Further arguments of the executor.
    :return: An executor sending plans to the real robot in `extensions`.
    """
    return RealRobotPlanExecutor(
        world_of(extensions), context_extensions=extensions, **options
    )


def robot_of(extensions: List[ContextExtension]) -> AbstractRobot:
    """
    :param extensions: The context extensions of a plan, holding a
        :class:`~coraplex.plans.context_extensions.RobotAccess`.
    :return: The robot in `extensions`.
    """
    return next(
        extension.robot
        for extension in extensions
        if isinstance(extension, RobotAccess)
    )


def world_of(extensions: List[ContextExtension]) -> World:
    """
    :param extensions: The context extensions of a plan, holding a
        :class:`~coraplex.plans.context_extensions.RobotAccess`.
    :return: The world of the robot in `extensions`.
    """
    return robot_of(extensions)._world


def context_of(extensions: List[ContextExtension]) -> StatechartContext:
    """
    :param extensions: The context extensions of a plan, holding a
        :class:`~coraplex.plans.context_extensions.RobotAccess`.
    :return: A context holding `extensions`, over the world of their robot, for building
        the parts of a plan that read the context before the plan joins a statechart.
    """
    context = StatechartContext(world=world_of(extensions))
    for extension in extensions:
        context.add_extension(extension)
    return context


def statechart_of(executor: PlanExecutor, *plan_nodes: StatechartNode) -> Statechart:
    """
    :param executor: The executor the statechart is built for.
    :param plan_nodes: The top-level nodes of the plan.
    :return: A statechart in the context of `executor`, holding `plan_nodes`.
    """
    statechart = Statechart(context=executor.context)
    for plan_node in plan_nodes:
        statechart.add_node(plan_node)
    return statechart


def expand(plan: StatechartNode, extensions: List[ContextExtension]) -> StatechartNode:
    """
    Expand `plan` in a statechart of its own, without running it, so a test can read the
    nodes its steps expand into.

    :param plan: The plan to expand.
    :param extensions: The context extensions the plan is expanded with.
    :return: The plan, expanded.
    """
    statechart_of(simulated_executor(extensions), plan)
    return plan


def run_plan(
    plan: StatechartNode, extensions: List[ContextExtension], **options
) -> SimulatedPlanExecutor:
    """
    Run `plan` simulated until it succeeded.

    :param plan: The plan to run.
    :param extensions: The context extensions of the plan.
    :param options: Further arguments of the executor.
    :return: The executor that ran the plan.
    """
    executor = simulated_executor(extensions, **options)
    executor.compile(statechart_of(executor, plan))
    executor.statechart.draw('/tmp/muh.pdf')
    executor.execute()
    return executor
