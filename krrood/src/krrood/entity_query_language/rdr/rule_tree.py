"""
Live growth of an EQL rule-tree DAG.

These helpers splice a new rule (a condition plus its ``Add`` conclusion) into an
existing rule tree at an explicit anchor, without relying on the ``with`` context
stack. They are the mechanism an RDR uses to add a refinement or alternative after
observing a misclassification.

Conditions and conclusion values are live EQL expression objects, never strings.
"""

from __future__ import annotations

from typing_extensions import Any

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable
from krrood.entity_query_language.factories import add
from krrood.entity_query_language.rules.conclusion_selector import (
    Alternative,
    Refinement,
)


def _insert_rule(
    selector,
    anchor: SymbolicExpression,
    condition: SymbolicExpression,
    conclusion_variable: CanBehaveLikeAVariable,
    conclusion_value: Any,
) -> SymbolicExpression:
    new_condition = selector.insert_at(anchor, condition)
    with new_condition:
        add(conclusion_variable, conclusion_value)
    return new_condition


def insert_refinement(
    anchor: SymbolicExpression,
    condition: SymbolicExpression,
    conclusion_variable: CanBehaveLikeAVariable,
    conclusion_value: Any,
) -> SymbolicExpression:
    """
    Add a refinement (except-if) of the rule at ``anchor``: when ``condition`` also
    holds, ``conclusion_value`` overrides the anchor rule's conclusion.

    :param anchor: The conditions node of the rule being refined.
    :param condition: The (live EQL) condition under which the refinement fires.
    :param conclusion_variable: The attribute the conclusion sets (e.g. ``animal.species``).
    :param conclusion_value: The overriding conclusion value.
    :return: The newly created refinement condition node.
    """
    return _insert_rule(
        Refinement, anchor, condition, conclusion_variable, conclusion_value
    )


def insert_alternative(
    anchor: SymbolicExpression,
    condition: SymbolicExpression,
    conclusion_variable: CanBehaveLikeAVariable,
    conclusion_value: Any,
) -> SymbolicExpression:
    """
    Add an alternative (else-if) to the rule at ``anchor``: when the anchor rule does
    not fire but ``condition`` holds, conclude ``conclusion_value``.

    :param anchor: The conditions node the alternative attaches beside.
    :param condition: The (live EQL) condition under which the alternative fires.
    :param conclusion_variable: The attribute the conclusion sets (e.g. ``animal.species``).
    :param conclusion_value: The alternative conclusion value.
    :return: The newly created alternative condition node.
    """
    return _insert_rule(
        Alternative, anchor, condition, conclusion_variable, conclusion_value
    )
