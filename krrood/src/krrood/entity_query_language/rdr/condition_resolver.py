"""
Auto-condition resolution for EQL-RDR using backward inference.

When a rule is applied with the wrong conclusion and the expert would normally be asked for
differentiating conditions, a :class:`ConditionResolver` can attempt to derive the
condition automatically from the rule tree's backward-inference knowledge — so the expert
is only consulted when no automatic resolution is possible.

The default built-in strategy, composed as a :class:`ChainConditionResolver`:

* :class:`TargetSufficientConditionsBasedResolver` — find a condition already known for the target
  conclusion that is True for the new case and False for the corner case.
* :class:`CornerCaseKnowledgeResolver` — search non-active paths to the wrong conclusion
  for a positive condition that is True for the new case and False for the corner case.

All strategies are gated on ``corner_case is not None`` (refinement branch only).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

from typing_extensions import TYPE_CHECKING, List, Optional, Type

from krrood.entity_query_language.rdr.backward_inference import (
    ConclusionSufficientConditionSets,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.rdr.backward_inference import (
        SufficientConditionSet,
    )
    from krrood.entity_query_language.rdr.interface import CaseContext


class ResolutionMode(StrEnum):
    """Controls how an auto-resolved condition is applied when fitting a case.

    See :meth:`~krrood.entity_query_language.rdr.single_class.EQLSingleClassRDR.fit_case`.
    :attr:`AUTOMATIC` preserves the original behaviour (no expert prompt); :attr:`HINT`
    shows the suggestion to the expert who may accept or overwrite it.
    """

    AUTOMATIC = "automatic"
    """Auto-resolved condition is inserted directly without consulting the expert."""
    HINT = "hint"
    """Auto-resolved condition is shown to the expert as a pre-seeded suggestion."""


@dataclass(frozen=True)
class ResolvedCondition:
    """An automatically derived condition expression and its provenance."""

    expression: SymbolicExpression
    """The EQL condition expression to insert as the new rule's condition."""
    resolver_type: Type[ConditionResolver]
    """The concrete resolver class that produced this condition."""


class ConditionResolver(ABC):
    """Strategy for automatically deriving a differentiating condition from the rule tree.

    Implementations receive the full context needed to attempt resolution. Returning
    ``None`` signals that this resolver cannot find a condition; the caller will try
    the next resolver or fall back to the expert.
    """

    @abstractmethod
    def resolve(
        self,
        context: CaseContext,
        target_knowledge: ConclusionSufficientConditionSets,
        current_knowledge: ConclusionSufficientConditionSets,
    ) -> Optional[ResolvedCondition]:
        """Attempt to auto-derive a differentiating condition.

        :param context: The facts of the case being fit — the case itself, the RDR's
            shared EQL variable, both conclusions, the firing rule's corner case, and
            the classification trace identifying the path that fired.
        :param target_knowledge: Backward-inference knowledge for the target conclusion.
        :param current_knowledge: Backward-inference knowledge for the current conclusion.
        :return: A :class:`ResolvedCondition`, or ``None`` if resolution is not possible.
        """


class TargetSufficientConditionsBasedResolver(ConditionResolver):
    """Primary strategy resolver: use backward inference on the target conclusion.

    Searches the sufficient condition sets known for ``target`` and returns the first
    guard that is True for the new case and False for the corner case — guaranteeing
    it discriminates between them.
    """

    def resolve(
        self,
        context: CaseContext,
        target_knowledge: ConclusionSufficientConditionSets,
        current_knowledge: ConclusionSufficientConditionSets,
    ) -> Optional[ResolvedCondition]:
        for sufficient_condition_set in target_knowledge.sufficient_condition_sets:
            for guard in sufficient_condition_set.conditions:
                if guard.holds_for(
                    context.case_variable, context.case_instance
                ) and not guard.holds_for(context.case_variable, context.corner_case):
                    return ResolvedCondition(guard.as_expression, type(self))
        return None


class CornerCaseKnowledgeResolver(ConditionResolver):
    """Fallback resolver: search non-active paths to the wrong conclusion for a positive condition.

    For each sufficient condition set of the wrong (current) conclusion that is **not** the
    active path (the path that caused the misclassification), searches for a guard that:

    * holds for the new case — so the new exception rule applies for it, and
    * does **not** hold for the corner case — so the original rule is left undisturbed.

    The matching guard is returned without negation, producing a stable positive condition
    grounded in a different characterisation of the wrong conclusion.
    """

    def _active_path(
        self,
        context: CaseContext,
        current_knowledge: ConclusionSufficientConditionSets,
    ) -> Optional[SufficientConditionSet]:
        """:return: The sufficient condition set in which the trace's firing anchor
        appears as a positive (non-negated) guard, or ``None`` if none does.

        An absent trace or anchor yields ``None`` so every path is treated as
        non-active.
        """
        if context.trace is None:
            return None
        firing_anchor = context.trace.firing_anchor
        if firing_anchor is None:
            return None
        return next(
            (
                sufficient_condition_set
                for sufficient_condition_set in current_knowledge.sufficient_condition_sets
                if any(
                    guard.original_expression is firing_anchor and not guard.negated
                    for guard in sufficient_condition_set.conditions
                )
            ),
            None,
        )

    def resolve(
        self,
        context: CaseContext,
        target_knowledge: ConclusionSufficientConditionSets,
        current_knowledge: ConclusionSufficientConditionSets,
    ) -> Optional[ResolvedCondition]:
        """Search non-active paths for a guard that holds for the case but not its corner case.

        The active path, identified via the trace's firing anchor, is skipped.

        :return: A :class:`ResolvedCondition`, or ``None`` if no discriminating guard is found.
        """
        active = self._active_path(context, current_knowledge)
        for sufficient_condition_set in current_knowledge.sufficient_condition_sets:
            if sufficient_condition_set is active:
                continue
            for guard in sufficient_condition_set.conditions:
                if guard.holds_for(
                    context.case_variable, context.case_instance
                ) and not guard.holds_for(context.case_variable, context.corner_case):
                    return ResolvedCondition(guard.as_expression, type(self))
        return None


@dataclass
class ChainConditionResolver(ConditionResolver):
    """A Chain-of-Responsibility that tries each resolver in order, returning the first match."""

    resolvers: List[ConditionResolver] = field(default_factory=list)
    """Ordered list of :class:`ConditionResolver` strategies to try, in priority order."""

    def resolve(
        self,
        context: CaseContext,
        target_knowledge: ConclusionSufficientConditionSets,
        current_knowledge: ConclusionSufficientConditionSets,
    ) -> Optional[ResolvedCondition]:
        """Try each resolver in :attr:`resolvers` in order, returning the first non-``None`` result.

        :return: The first :class:`ResolvedCondition` produced by a resolver, or ``None``
            if every resolver returns ``None``.
        """
        for resolver in self.resolvers:
            result = resolver.resolve(context, target_knowledge, current_knowledge)
            if result is not None:
                return result
        return None

    @classmethod
    def backward_inference_default(cls) -> ChainConditionResolver:
        """Return the standard chain: :class:`TargetSufficientConditionsBasedResolver` then
        :class:`CornerCaseKnowledgeResolver`, in priority order.
        """
        return cls(
            [TargetSufficientConditionsBasedResolver(), CornerCaseKnowledgeResolver()]
        )
