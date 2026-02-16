from __future__ import annotations

from typing_extensions import Union, TYPE_CHECKING

from .conclusion_selector import ExceptIf, Alternative, Next
from .enums import RDREdge
from .symbolic import (
    SymbolicExpression,
    chained_logic,
    AND,
    LogicalOperator,
)

if TYPE_CHECKING:
    from .entity import ConditionType


def refinement(*conditions: ConditionType) -> SymbolicExpression:
    """
    Add a refinement branch (ExceptIf node with its right the new conditions and its left the base/parent rule/query)
     to the current condition tree.

    Each provided condition is chained with AND, and the resulting branch is
    connected via ExceptIf to the current node, representing a refinement/specialization path.

    :param conditions: The refinement conditions. They are chained with AND.
    :returns: The newly created branch node for further chaining.
    """
    new_branch = chained_logic(AND, *conditions)
    current_node = SymbolicExpression._current_parent_in_context_stack_()
    prev_parent = current_node._parent_
    new_conditions_root = ExceptIf(current_node, new_branch)
    prev_parent._replace_child_(current_node, new_conditions_root)
    return new_branch


def alternative(*conditions: ConditionType) -> SymbolicExpression:
    """
    Add an alternative branch (logical ElseIf) to the current condition tree.

    Each provided condition is chained with AND, and the resulting branch is
    connected via ElseIf to the current node, representing an alternative path.

    :param conditions: Conditions to chain with AND and attach as an alternative.
    :returns: The newly created branch node for further chaining.
    """
    return alternative_or_next(RDREdge.Alternative, *conditions)


def next_rule(*conditions: ConditionType) -> SymbolicExpression:
    """
    Add a consequent rule that gets always executed after the current rule.

    Each provided condition is chained with AND, and the resulting branch is
    connected via Next to the current node, representing the next path.

    :param conditions: Conditions to chain with AND and attach as an alternative.
    :returns: The newly created branch node for further chaining.
    """
    return alternative_or_next(RDREdge.Next, *conditions)


def alternative_or_next(
    condition_edge_type: Union[RDREdge.Alternative, RDREdge.Next],
    *conditions: ConditionType,
) -> SymbolicExpression:
    """
    Add an alternative/next branch to the current condition tree.

    Each provided condition is chained with AND, and the resulting branch is
    connected via ElseIf/Next to the current node, representing an alternative/next path.

    :param condition_edge_type: The type of the branch, either alternative or next.
    :param conditions: Conditions to chain with AND and attach as an alternative.
    :returns: The newly created branch node for further chaining.
    """
    new_condition = chained_logic(AND, *conditions)

    current_conditions_root = get_current_conditions_root_for_alternative_or_next()

    prev_parent = current_conditions_root._parent_

    new_conditions_root = construct_new_conditions_root_for_alternative_or_next(
        condition_edge_type, current_conditions_root, new_condition
    )

    if new_conditions_root is not current_conditions_root:
        prev_parent._replace_child_(current_conditions_root, new_conditions_root)

    return new_condition


def get_current_conditions_root_for_alternative_or_next() -> ConditionType:
    """
    :return: the current conditions root to use for creating a new condition connected via alternative or next edge.
    """
    current_node = SymbolicExpression._current_parent_in_context_stack_()
    if isinstance(current_node._parent_, (Alternative, Next)):
        current_node = current_node._parent_
    elif (
        isinstance(current_node._parent_, ExceptIf)
        and current_node is current_node._parent_.left
    ):
        current_node = current_node._parent_
    return current_node


def construct_new_conditions_root_for_alternative_or_next(
    condition_edge_type: Union[RDREdge.Next, RDREdge.Alternative],
    current_conditions_root: SymbolicExpression,
    new_condition: LogicalOperator,
) -> Union[Next, Alternative]:
    """
    Constructs a new conditions root for alternative or next condition edge types.

    :param condition_edge_type: The type of the edge connecting the current node to the new branch.
    :param current_conditions_root: The current conditions root in the expression tree.
    :param new_condition: The new condition to be added to the rule tree.
    """
    match condition_edge_type:
        case RDREdge.Alternative:
            new_conditions_root = Alternative(current_conditions_root, new_condition)
        case RDREdge.Next:
            match current_conditions_root:
                case Next():
                    current_conditions_root.add_child(new_condition)
                    new_conditions_root = current_conditions_root
                case _:
                    new_conditions_root = Next((current_conditions_root, new_condition))
        case _:
            raise ValueError(
                f"Invalid edge type: {condition_edge_type}, expected one of: {RDREdge.Alternative}, {RDREdge.Next}"
            )
    return new_conditions_root
