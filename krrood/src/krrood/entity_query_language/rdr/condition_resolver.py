"""
Auto-condition resolution for EQL-RDR using backward inference.

When a rule is applied with the wrong conclusion and the expert would normally be asked for
differentiating conditions, a :class:`ConditionResolver` can attempt to derive the
condition automatically by walking the rule tree backwards — so the expert is only
consulted when no automatic resolution is possible.

A resolver is handed the RDR and reads whatever it needs from it, so the engine neither
computes condition sets a resolver may not want nor decides which situations a resolver
can handle.

The default built-in strategy, composed as a :class:`ChainConditionResolver`:

* :class:`TargetSufficientConditionsBasedResolver` — find a condition already known for the target
  conclusion that is True for the new case and False for the corner case.
* :class:`CornerCaseKnowledgeResolver` — search non-active paths to the wrong conclusion
  for a positive condition that is True for the new case and False for the corner case.

All strategies are gated on ``corner_case is not None`` (refinement branch only), which
:meth:`ConditionResolver.resolve` applies once for the whole family.
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
    from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR


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

    def resolve(
        self,
        rdr: EQLSingleClassRDR,
        context: CaseContext,
    ) -> Optional[ResolvedCondition]:
        """Attempt to auto-derive a differentiating condition.

        Only a case that a wrong rule fired for can be discriminated against anything,
        so a context carrying no corner case or no current conclusion is refused here
        for every resolver in the family.

        :param rdr: The RDR being fitted, read for whatever the strategy needs.
        :param context: The facts of the case being fit — the case itself, the RDR's
            shared EQL variable, both conclusions, the firing rule's corner case, and
            the classification trace identifying the path that fired.
        :return: A :class:`ResolvedCondition`, or ``None`` if resolution is not possible.
        """
        if context.corner_case is None or not context.has_current_conclusion:
            return None
        return self._resolve_against_corner_case(rdr, context)

    @abstractmethod
    def _resolve_against_corner_case(
        self,
        rdr: EQLSingleClassRDR,
        context: CaseContext,
    ) -> Optional[ResolvedCondition]:
        """Derive a condition separating the case from the corner case a wrong rule was
        written for.

        Called only once :meth:`resolve` has established that both are present.

        :param rdr: The RDR being fitted, read for whatever the strategy needs.
        :param context: The facts of the case being fit.
        :return: A :class:`ResolvedCondition`, or ``None`` if this strategy cannot find one.
        """


class TargetSufficientConditionsBasedResolver(ConditionResolver):
    """Primary strategy resolver: use backward inference on the target conclusion.

    Searches the sufficient condition sets known for ``target`` and returns the first
    guard that is True for the new case and False for the corner case — guaranteeing
    it discriminates between them.
    """

    def _resolve_against_corner_case(
        self,
        rdr: EQLSingleClassRDR,
        context: CaseContext,
    ) -> Optional[ResolvedCondition]:
        target_conditions = rdr.sufficient_conditions_for(context.target_conclusion)
        for sufficient_condition_set in target_conditions.sufficient_condition_sets:
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
        current_conditions: ConclusionSufficientConditionSets,
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
                for sufficient_condition_set in current_conditions.sufficient_condition_sets
                if any(
                    guard.original_expression is firing_anchor and not guard.negated
                    for guard in sufficient_condition_set.conditions
                )
            ),
            None,
        )

    def _resolve_against_corner_case(
        self,
        rdr: EQLSingleClassRDR,
        context: CaseContext,
    ) -> Optional[ResolvedCondition]:
        """Search non-active paths for a guard that holds for the case but not its corner case.

        The active path, identified via the trace's firing anchor, is skipped.

        :param rdr: The RDR being fitted, read for the current conclusion's condition sets.
        :param context: The facts of the case being fit.
        :return: A :class:`ResolvedCondition`, or ``None`` if no discriminating guard is found.
        """
        current_conditions = rdr.sufficient_conditions_for(context.current_conclusion)
        active = self._active_path(context, current_conditions)
        for sufficient_condition_set in current_conditions.sufficient_condition_sets:
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

    def _resolve_against_corner_case(
        self,
        rdr: EQLSingleClassRDR,
        context: CaseContext,
    ) -> Optional[ResolvedCondition]:
        """Try each resolver in :attr:`resolvers` in order, returning the first non-``None`` result.

        :param rdr: The RDR being fitted, passed on to each strategy.
        :param context: The facts of the case being fit.
        :return: The first :class:`ResolvedCondition` produced by a resolver, or ``None``
            if every resolver returns ``None``.
        """
        for resolver in self.resolvers:
            result = resolver.resolve(rdr, context)
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
