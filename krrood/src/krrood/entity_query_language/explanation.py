from __future__ import annotations

import inspect
import weakref
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, List, Optional, Type, Callable

from typing_extensions import TYPE_CHECKING


if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import (
        OperationResult, SymbolicExpression,
)
    from krrood.entity_query_language.query.query import Query


def filter_stack(
    stack: List[inspect.FrameInfo], internal_package: Optional[str] = None
) -> List[inspect.FrameInfo]:
    """
    Filter the stack to remove external libraries and optionally keep only a specific package.

    :param stack: The stack to filter.
    :param internal_package: The name of the package to focus on.
    :return: The filtered stack.
    """
    filtered = []
    for frame in stack:
        path = frame.filename
        # Exclude standard library/external packages
        if "site-packages" in path or "dist-packages" in path:
            continue

        # If a specific package is requested, filter further
        if internal_package and internal_package not in path:
            continue

        filtered.append(frame)
    return filtered


def monitored(cls: Type) -> Type:
    """
    Class decorator to automatically record the creation stack for EQL objects.

    :param cls: The class to monitor.
    :return: The monitored class.
    """
    # Inject the marker to indicate the class is monitored
    cls._is_monitored_ = True

    original_post_init = getattr(cls, "__post_init__", lambda self: None)

    @wraps(original_post_init)
    def new_post_init(self, *args, **kwargs):
        # Capture stack, skip the first few frames (decorator internal)
        raw_stack = inspect.stack()[1:]
        # Store the filtered stack on the instance
        self._creation_stack = filter_stack(raw_stack)
        original_post_init(self, *args, **kwargs)

    cls.__post_init__ = new_post_init
    return cls


@dataclass
class InferenceExplanation:
    """
    Explanation of how an instance was created through inference.
    """

    instance: Any
    """
    The instance that was created.
    """
    query_node: SymbolicExpression
    """
    The query node that was used to create the instance.
    """
    stack: List[inspect.FrameInfo]
    """
    The stack trace at the point of creation.
    """
    query_root: Optional[Query] = None
    """
    The root of the query that was used to create the instance.
    """
    satisfied_condition_ids: Optional[frozenset] = None
    """
    A frozenset of UUIDs of condition expressions that were satisfied (truth value = True)
    during the evaluation that produced this instance. None if no condition information is available.
    """
    operation_result: Optional[OperationResult] = None
    """
    The full :class:`OperationResult` from the evaluation iteration that produced this instance.
    Contains bindings, all_bindings, is_false, operand, previous_operation_result, and
    satisfied_condition_ids. None if no result information is available.
    """

    def condition_graph(self):
        """
        Build a QueryGraph of the full query tree with satisfaction data overlaid.

        Each ``QueryNode`` carries an ``is_satisfied`` flag grounded directly on
        the satisfied condition IDs.  Unsatisfied condition subtrees are also
        marked as *faded* for visualization purposes.

        :return: A :class:`QueryGraph` instance, or None if no conditions exist
            or no satisfaction data is available.
        """
        if self.query_root is None or not self.satisfied_condition_ids:
            return None
        from krrood.entity_query_language.query_graph import QueryGraph

        return QueryGraph(
            self.query_root,
            satisfied_condition_ids=self.satisfied_condition_ids,
        )

    def as_string(
            self, focus_package: Optional[str] = None
    ) -> str:
        """
        Convert an InferenceExplanation into a human-readable string.

        :param focus_package: Optional package name to filter the stack further.
        :return: A formatted string explaining the inference.
        """
        # Allow further filtering at explanation time
        display_stack = filter_stack(self.stack, internal_package=focus_package)

        formatted_stack = []
        for frame_info in display_stack:
            formatted_stack.append(
                f'  File "{frame_info.filename}", line {frame_info.lineno}, in {frame_info.function}\n'
                f'    {frame_info.code_context[0].strip() if frame_info.code_context else "???"}\n'
            )

        stack_str = "".join(formatted_stack[:10])  # Limit to 10 frames

        return (
            f"Instance {self.instance} was created by inference variable: {self.query_node}\n"
            f"Part of query: {self.query_root}\n"
            f"Call stack at definition:\n{stack_str}"
        )


# Dictionary to store inference explanations for instances.
# Uses weak references to allow instances to be garbage collected.
INFERENCE_RECORD: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def register_inference(
    instance: Any, variable_node: SymbolicExpression, result: Optional[OperationResult] = None
) -> None:
    """
    Register an instance created via inference into the internal records.

    :param instance: The instance to record.
    :param variable_node: The variable node that produced the instance.
    :param result: The OperationResult from the evaluation, carrying satisfied condition IDs.
    """
    # Robust check: Verify monitoring at the class level using type()
    if not getattr(type(variable_node), "_is_monitored_", False):
        return

    satisfied_ids = result.satisfied_condition_ids if result else None
    explanation = InferenceExplanation(
        instance=instance,
        query_node=variable_node,
        # Monitored instances are guaranteed to have _creation_stack via __post_init__
        stack=variable_node._creation_stack,
        # _root_ is guaranteed by the SymbolicExpression base class
        query_root=variable_node._root_,
        satisfied_condition_ids=satisfied_ids,
        operation_result=result,
    )
    try:
        INFERENCE_RECORD[instance] = explanation
    except TypeError:
        pass


def explain_inference(instance: Any) -> Optional[InferenceExplanation]:
    """
    Retrieve the explanation of how the given instance was created through inference.

    :param instance: The instance to explain.
    :return: An InferenceExplanation object if found, otherwise None.
    """
    try:
        return INFERENCE_RECORD.get(instance)
    except TypeError:
        return None
