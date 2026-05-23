"""
Observer that reads RDR conclusions out of an EQL evaluation.

Classification in the EQL-native RDR is plain EQL evaluation of the rule-tree query.
This module provides the aspect that listens to that evaluation and extracts the
inferred conclusion for the underspecified attribute, without the rule tree (or the
core evaluation methods) knowing anything about RDR.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, List, Optional

from krrood.entity_query_language.core.base_expressions import (
    OperationResult,
    SymbolicExpression,
)
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable
from krrood.entity_query_language.evaluation import (
    EvaluationContext,
    EvaluationObserver,
    EvaluationTracker,
    SatisfiedConditionTracker,
    set_evaluation_context,
)


@dataclass
class FiredConclusion:
    """A single conclusion observed during evaluation of the rule tree."""

    value: Any
    """The inferred value bound to the conclusion variable (e.g. ``Species.mammal``)."""
    conditions_root: SymbolicExpression
    """The conditions-root expression at which the conclusion was processed."""
    result: OperationResult
    """The full result, carrying ``bindings`` and ``satisfied_condition_ids``."""


class ConclusionObserver(EvaluationObserver):
    """Collects the conclusion bound to a target variable during EQL evaluation.

    Hooks :meth:`on_conclusions_processed`, which fires at the conditions root once
    conclusions (``Add`` nodes) have updated the bindings and the result is true. The
    inferred value is whatever the target variable is bound to at that point.
    """

    def __init__(self, conclusion_variable: CanBehaveLikeAVariable) -> None:
        self.conclusion_variable = conclusion_variable
        self.conclusion_id = conclusion_variable._id_
        self.fired: List[FiredConclusion] = []

    def reset(self) -> None:
        """Clear any captured conclusions, ready for a fresh evaluation."""
        self.fired = []

    def on_conclusions_processed(
        self, expression: SymbolicExpression, result: OperationResult
    ) -> None:
        if self.conclusion_id in result.bindings:
            self.fired.append(
                FiredConclusion(
                    value=result.bindings[self.conclusion_id],
                    conditions_root=expression,
                    result=result,
                )
            )

    @property
    def conclusion(self) -> Optional[Any]:
        """The single inferred value, or ``None`` if no rule fired.

        Single-class RDR conclusions are mutually exclusive, so all captured
        conclusions for one case carry the same value; we return the last one.
        """
        return self.fired[-1].value if self.fired else None

    @property
    def distinct_conclusions(self) -> List[Any]:
        """The distinct inferred values observed (order-preserving)."""
        seen: List[Any] = []
        for f in self.fired:
            if f.value not in seen:
                seen.append(f.value)
        return seen


def classify_case(
    rule_tree_query: SymbolicExpression,
    case_variable: CanBehaveLikeAVariable,
    conclusion_variable: CanBehaveLikeAVariable,
    case: Any,
) -> ConclusionObserver:
    """
    Evaluate ``rule_tree_query`` for a single ``case`` and return the observer that
    captured the conclusion(s).

    The case is bound by re-targeting ``case_variable``'s domain to ``[case]`` so the
    shared rule-tree DAG is evaluated against exactly this case. A
    :class:`ConclusionObserver` is installed (alongside the default trackers, so
    ``satisfied_condition_ids`` is populated for later insertion-point logic).

    :param rule_tree_query: The root EQL query of the rule tree.
    :param case_variable: The shared variable the rule tree ranges over.
    :param conclusion_variable: The (underspecified) attribute the rules conclude.
    :param case: The single instance to classify.
    :return: The :class:`ConclusionObserver` holding the captured conclusion(s).
    """
    case_variable._update_domain_([case])
    observer = ConclusionObserver(conclusion_variable)
    set_evaluation_context(
        EvaluationContext(
            observers=[observer, EvaluationTracker(), SatisfiedConditionTracker()]
        )
    )
    try:
        list(rule_tree_query.evaluate())
    finally:
        set_evaluation_context(None)
    return observer
