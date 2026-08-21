from __future__ import annotations

from typing import Callable

from typing_extensions import List, assert_never, Optional, TYPE_CHECKING, Type, TypeVar

from giskardpy.motion_statechart.graph_node import MotionStatechartNode
from krrood.entity_query_language.query.match import Match
from coraplex.datastructures.dataclasses import Context
from coraplex.plans.plan import Plan

if TYPE_CHECKING:
    from coraplex.language import (
        SequentialNode,
        LanguageNode,
        ParallelNode,
        TryInOrderNode,
        TryAllNode,
        CancelMonitor,
        PauseMonitor,
        RepeatNode,
        CodeNode,
    )
    from coraplex.plans.plan_node import ActionLike, PlanNode


def execute_single(
    action_like: ActionLike,
    context: Optional[Context] = None,
) -> PlanNode:

    node = make_node(action_like)
    plan = Plan(context=context)
    plan.add_node(node)
    return node


def sequential(
    children: List[ActionLike],
    context: Optional[Context] = None,
) -> SequentialNode:
    from coraplex.language import SequentialNode

    return _make_plan_from_type_and_children(SequentialNode(), children, context)


def parallel(
    children: List[ActionLike],
    context: Optional[Context] = None,
) -> ParallelNode:
    from coraplex.language import ParallelNode

    return _make_plan_from_type_and_children(ParallelNode(), children, context)


def try_in_order(
    children: List[ActionLike],
    context: Optional[Context] = None,
) -> TryInOrderNode:
    from coraplex.language import TryInOrderNode

    return _make_plan_from_type_and_children(TryInOrderNode(), children, context)


def try_all(
    children: List[ActionLike],
    context: Optional[Context] = None,
) -> TryAllNode:
    from coraplex.language import TryAllNode

    return _make_plan_from_type_and_children(TryAllNode(), children, context)


def pause_while(
    children: List[ActionLike],
    monitor: MotionStatechartNode,
    context: Optional[Context] = None,
) -> PauseMonitor:
    """
    Hold `children` for as long as `monitor` observes True.

    :param monitor: The motion state chart node observed while the children run.
    """
    from coraplex.language import PauseMonitor

    return _make_plan_from_type_and_children(
        PauseMonitor(monitor=monitor), children, context
    )


def pause_until(
    children: List[ActionLike],
    monitor: MotionStatechartNode,
    context: Optional[Context] = None,
) -> PauseUntilMonitor:
    """
    Hold `children` until `monitor` observes True.

    :param monitor: The motion state chart node observed while the children run.
    """
    from coraplex.language import PauseUntilMonitor

    return _make_plan_from_type_and_children(
        PauseUntilMonitor(monitor=monitor), children, context
    )


def cancel_when(
    children: List[ActionLike],
    monitor: MotionStatechartNode,
    context: Optional[Context] = None,
) -> CancelMonitor:
    """
    Stop `children` once `monitor` observes True; the plan continues afterwards.

    :param monitor: The motion state chart node observed while the children run.
    """
    from coraplex.language import CancelMonitor

    return _make_plan_from_type_and_children(
        CancelMonitor(monitor=monitor), children, context
    )


def repeat(
    children: List[ActionLike],
    maximum_repetitions: int,
    context: Optional[Context] = None,
    **repeat_arguments,
) -> RepeatNode:
    """
    Attempt `children` until they succeed, at most `maximum_repetitions` times.

    :param maximum_repetitions: How many attempts before the repeating is given up on.
    :param repeat_arguments: Passed to :class:`~coraplex.language.RepeatNode`, for
        instance a `repeat_template` or a `failure_monitor`.
    """
    from coraplex.language import RepeatNode

    root = RepeatNode(maximum_repetitions=maximum_repetitions, **repeat_arguments)
    return _make_plan_from_type_and_children(root, children, context)


def code(function: Callable, context: Optional[Context] = None) -> CodeNode:
    from coraplex.language import CodeNode

    root = CodeNode(code=function)
    return execute_single(root, context=context)


T = TypeVar("T")


def _make_plan_from_type_and_children(
    root: T, children: List[ActionLike], context: Optional[Context]
) -> T:
    from coraplex.language import LanguageNode

    plan = Plan(context=context)
    plan.add_node(root)

    for action_like in children:
        child = make_node(action_like)
        if child.plan:
            root.mount_subplan(child)
        else:
            root.add_child(child)
    plan.simplify()
    return root


def make_node(action_like: ActionLike) -> PlanNode:
    from coraplex.plans.plan_node import (
        PlanNode,
        UnderspecifiedNode,
        ActionNode,
        MotionNode,
    )
    from coraplex.robot_plans.actions.base import ActionDescription
    from coraplex.robot_plans import BaseMotion

    if isinstance(action_like, PlanNode):
        return action_like
    elif isinstance(action_like, Match):
        underspecified_action = UnderspecifiedNode(underspecified_action=action_like)
        return underspecified_action
    elif isinstance(action_like, ActionDescription):
        return ActionNode(designator=action_like)
    elif isinstance(action_like, BaseMotion):
        return MotionNode(designator=action_like)
    else:
        assert_never(action_like)
