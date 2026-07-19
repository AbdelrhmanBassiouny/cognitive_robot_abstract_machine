"""
The why-question core for the EQL-native RDR.

A *why* question asks why a case was given its conclusion. The answer names the rule that
fired, its condition expression, its place in the rule tree, the conditions that were
satisfied (with their bindings), and the corner case the rule was created for.

Everything here is *content selection* over the existing
:class:`~krrood.entity_query_language.rdr.observer.ClassificationTrace` (which now retains
the winning :class:`~krrood.entity_query_language.rdr.observer.FiredConclusion`): no new
capture machinery runs. :class:`RDRConclusionExplanation` presents that answer through the
same :class:`~krrood.entity_query_language.explanation.explanation.Explanation` abstraction
that EQL inference uses, so an RDR attribute conclusion and an EQL inference are explained
alike.

.. note::
    Contrastive why-questions (*why X rather than Y*) are reserved: :class:`WhyQuestion`
    carries a ``contrast`` field, but answering one is not implemented in this version.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, List, Optional, Tuple

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.explanation.explanation import (
    ConditionAndBindings,
    Explanation,
)
from krrood.entity_query_language.operators.core_logical_operators import (
    LogicalOperator,
)
from krrood.entity_query_language.rdr.observer import ClassificationTrace
from krrood.entity_query_language.rdr.rule_tree_view import (
    RuleCode,
    RuleKindWord,
    walk_rules,
)
from krrood.entity_query_language.rdr.serialization import rule_code_map
from krrood.entity_query_language.rules.conclusion import Add

CONTRAST_NOT_IMPLEMENTED = (
    "Contrastive why-questions (why X rather than Y) are reserved for a later version; "
    "they will be answered by contrasting the SufficientConditionSets of the two "
    "conclusions (see EQLSingleClassRDR.what_do_we_know_about)."
)
"""The pointer raised when a contrastive :class:`WhyQuestion` is answered."""


@dataclass(frozen=True)
class WhyQuestion:
    """A request to explain why ``case`` was given its conclusion."""

    case: Any
    """The case whose conclusion is being questioned."""
    contrast: Optional[Any] = None
    """The conclusion to contrast against (*why X rather than this*). Reserved: answering a
    contrastive question is not implemented in this version."""

    @property
    def is_contrastive(self) -> bool:
        """:return: Whether a contrast conclusion was supplied."""
        return self.contrast is not None


@dataclass(frozen=True)
class WhyAnswer:
    """Why a case was given its conclusion: the rule that fired and its justification."""

    conclusion: Any
    """The inferred conclusion value (e.g. ``Species.mammal``)."""
    condition: SymbolicExpression
    """The condition expression of the rule that fired (the firing anchor)."""
    add_node: Add
    """The ``Add`` conclusion node that produced :attr:`conclusion`."""
    rule_depth: int
    """The fired rule's refinement-nesting depth (``0`` = a top-level rule)."""
    rule_code: RuleCode
    """The fired rule's code — its kind letter and tree index (``R0`` / ``R1`` / ``A2``)."""
    satisfied_conditions: Tuple[ConditionAndBindings, ...]
    """The non-logical conditions satisfied during classification, each with its bindings."""
    corner_case: Optional[Any]
    """The corner case the fired rule was created for, or ``None`` if unrecorded."""

    @classmethod
    def from_trace(
        cls, trace: ClassificationTrace, corner_case: Optional[Any]
    ) -> WhyAnswer:
        """Select the answer content from a classification whose rule fired.

        :param trace: A trace whose :attr:`~ClassificationTrace.fired_conclusion` is set.
        :param corner_case: The corner case recorded for the firing rule, or ``None``.
        :return: The assembled :class:`WhyAnswer`.
        """
        fired = trace.fired_conclusion
        rule_depth = _depth_of(trace.rule_tree_root, trace.firing_anchor_id)
        rule_code = rule_code_map(trace.rule_tree_root).get(
            trace.firing_anchor_id, RuleCode(0, RuleKindWord.BASE)
        )
        return cls(
            conclusion=trace.conclusion,
            condition=trace.firing_anchor,
            add_node=fired.add_node,
            rule_depth=rule_depth,
            rule_code=rule_code,
            satisfied_conditions=_satisfied_conditions_of(trace),
            corner_case=corner_case,
        )


@dataclass(frozen=True)
class RDRConclusionExplanation(Explanation):
    """An :class:`Explanation` of an RDR attribute conclusion, backed by a :class:`WhyAnswer`.

    Sibling of
    :class:`~krrood.entity_query_language.explanation.explanation.InferenceExplanation`:
    both present their satisfied conditions through the shared abstraction, so a caller can
    explain an RDR conclusion and an EQL inference the same way.
    """

    why_answer: WhyAnswer
    """The why-answer whose satisfied conditions this explanation presents."""

    def get_satisfied_conditions_and_their_bindings(self) -> List[ConditionAndBindings]:
        """:return: The satisfied conditions justifying the conclusion, with their bindings."""
        return list(self.why_answer.satisfied_conditions)


def _depth_of(
    rule_tree_root: Optional[SymbolicExpression], firing_anchor_id: Any
) -> int:
    """Find the fired rule's refinement-nesting depth by matching its condition node in the tree.

    :param rule_tree_root: The root of the rule tree's condition DAG.
    :param firing_anchor_id: The ``_id_`` of the fired rule's condition node.
    :return: The depth of the fired rule (``0`` = a top-level rule).
    """
    for rule in walk_rules(rule_tree_root):
        if rule.condition._id_ == firing_anchor_id:
            return rule.depth
    return 0


def _satisfied_conditions_of(
    trace: ClassificationTrace,
) -> Tuple[ConditionAndBindings, ...]:
    """Resolve the satisfied condition ids to expressions paired with their bindings.

    Logical wrappers (``AND`` / ``OR`` / ``Not``) are dropped so only the leaf conditions
    that actually discriminate the case remain, mirroring
    :meth:`InferenceExplanation.get_satisfied_conditions_and_their_bindings`.

    :param trace: A trace whose :attr:`~ClassificationTrace.fired_conclusion` is set.
    :return: The satisfied leaf conditions, each with the full evaluation bindings.
    """
    result = trace.fired_conclusion.result
    if not result.satisfied_condition_ids:
        return ()
    root = trace.rule_tree_root._root_
    bindings = result.all_bindings
    conditions = [
        ConditionAndBindings(expression, bindings)
        for condition_id in result.satisfied_condition_ids
        if not isinstance(
            (expression := root._get_expression_by_id_(condition_id)), LogicalOperator
        )
    ]
    return tuple(conditions)
