from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, Any, List, Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.expression_structure import chain_root
from krrood.entity_query_language.query.aggregation_structure import (
    unwrap_result_quantifiers,
)
from krrood.entity_query_language.rdr.why import WhyAnswer
from krrood.entity_query_language.verbalization.grammar.framework.planner import Planner
from krrood.entity_query_language.verbalization.vocabulary.english import FallbackNouns

if TYPE_CHECKING:
    from krrood.entity_query_language.rdr.rule_tree_view import RuleCode


@dataclass(frozen=True)
class CausalStructure:
    """
    Decomposition of a :class:`~krrood.entity_query_language.rdr.why.WhyAnswer` into the three
    spans of a causal explanation (the plan).
    """

    conclusion_subject: SymbolicExpression
    """The attribute the fired rule concluded on (e.g. ``Animal.species``); the subject of the
    conclusion clause."""

    conclusion_value: Any
    """The value the fired rule concluded (e.g. ``Species.mammal``); the predicate of the conclusion
    clause."""

    reasons: List[SymbolicExpression]
    """The satisfied leaf conditions that justify the conclusion — the *"because"* coordinands."""

    rule_code: RuleCode
    """The fired rule's code — its kind word (``refinement`` / ``alternative`` / ``base``) names the
    rule and its :attr:`~…RuleCode.as_string` (``R1`` / ``A2`` / ``R0``) identifies it; the
    rule-identity clause reads both."""

    case_variable_id: Optional[uuid.UUID] = None
    """The ``_id_`` of the classified case's variable, so the assembler can substitute the concrete
    instance for it via a binding override; ``None`` when the subject has no variable root."""

    case_type_name: str = FallbackNouns.ENTITY.text
    """The type name of the classified case (e.g. ``"Animal"``), read as the head of the definite
    instance phrase that replaces the case variable."""


@dataclass
class CausalPlanner(Planner[WhyAnswer, CausalStructure]):
    """
    Decompose a :class:`~krrood.entity_query_language.rdr.why.WhyAnswer` into a
    :class:`CausalStructure`: the conclusion the rule reached, the satisfied conditions that justify
    it, and the identity of the rule that fired.

    Content selection only — it reads the answer's already-selected fields and never re-runs the
    classification.

    Reference: :cite:t:`reiter2000building` — content/structure determination (microplanning).
    """

    def plan(self) -> CausalStructure:
        """:return: The conclusion / reasons / rule-identity decomposition of the answer."""
        answer = self.node
        subject = answer.add_node.left
        case_variable = self._case_variable(subject)
        return CausalStructure(
            conclusion_subject=subject,
            conclusion_value=answer.conclusion,
            reasons=[condition.condition for condition in answer.satisfied_conditions],
            rule_code=answer.rule_code,
            case_variable_id=case_variable._id_ if case_variable is not None else None,
            case_type_name=FallbackNouns.ENTITY.name_of(case_variable),
        )

    @staticmethod
    def _case_variable(subject: SymbolicExpression) -> Optional[SymbolicExpression]:
        """:return: The variable at the root of the conclusion subject's chain — the classified case
        — or ``None`` when the subject is not rooted in a variable."""
        root = unwrap_result_quantifiers(chain_root(subject))
        return root if isinstance(root, SymbolicExpression) else None
