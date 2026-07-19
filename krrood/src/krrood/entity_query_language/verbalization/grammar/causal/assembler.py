from __future__ import annotations

from typing_extensions import List

from krrood.entity_query_language.rdr.why import WhyAnswer
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    Clause,
    NounPhrase,
    PhraseFragment,
    RoleFragment,
    VerbalizationFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import Definiteness
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.grammar.causal.planner import (
    CausalPlanner,
    CausalStructure,
)
from krrood.entity_query_language.verbalization.grammar.framework.assembler import (
    Assembler,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    CoordinatingConjunctions,
    Copulas,
    Prepositions,
    SubordinatingConjunctions,
)
from krrood.entity_query_language.verbalization.vocabulary.words import (
    GrammaticalNumber,
)


class CausalAssembler(Assembler[WhyAnswer, CausalStructure]):
    """
    Realise a why-answer as *"<conclusion> because <conditions>, by the <kind> rule"*.

    Modelled on
    :class:`~krrood.entity_query_language.verbalization.grammar.inference.assembler.InferenceAssembler`'s
    two-block skeleton: a conclusion clause, a *"because"*-headed block coordinating the satisfied
    conditions, and a rule-identity clause. The conclusion subject and every condition are recursed
    through :meth:`~…RuleContext.child`, so the existing comparator / chain / coreference machinery
    renders them; this assembler only decides the causal structure and threads the concrete instance
    in for the case variable.

    Reference: :cite:t:`gatt2009simplenlg` — surface realisation.
    """

    planner = CausalPlanner

    def realize(self, node: WhyAnswer, plan: CausalStructure) -> VerbalizationFragment:
        """
        :param node: The why-answer being verbalised.
        :param plan: The conclusion / reasons / rule-identity decomposition.
        :return: The whole *"<conclusion> because <conditions>, by the <kind> rule"* explanation,
            sourced at the conclusion subject so the coreference pass scopes the case as the
            discourse subject.
        """
        self._bind_case_instance(plan)
        return BlockFragment(
            header=None,
            items=[
                self._conclusion_clause(plan),
                self._because_block(plan),
                self._rule_identity_clause(plan),
            ],
            source=plan.conclusion_subject,
        )

    def _bind_case_instance(self, plan: CausalStructure) -> None:
        """
        Register the classified case as a definite instance phrase for its variable, so
        the conclusion and conditions read *"the Animal"* (the concrete case) rather
        than *"an Animal"* (the bare variable).

        A no-op when the subject has no variable root.
        """
        if plan.case_variable_id is None:
            return
        self.context.scope.binding_overrides[plan.case_variable_id] = NounPhrase(
            head=RoleFragment(text=plan.case_type_name, role=SemanticRole.VARIABLE),
            definiteness=Definiteness.DEFINITE,
            referent_id=plan.case_variable_id,
        )

    def _conclusion_clause(self, plan: CausalStructure) -> VerbalizationFragment:
        """:return: *"the <attribute> of the <case> is <value>"* — the conclusion the rule reached."""
        return Clause(
            parts=[
                self.context.child(plan.conclusion_subject),
                Copulas.for_number(GrammaticalNumber.SINGULAR),
                RoleFragment.for_literal(plan.conclusion_value),
            ]
        )

    def _because_block(self, plan: CausalStructure) -> VerbalizationFragment:
        """:return: The *"because"* block coordinating the satisfied conditions (*"because a, b, and
        c"*); *"because true"* when no condition discriminated the case."""
        reasons: List[VerbalizationFragment] = [
            self.context.child(reason) for reason in plan.reasons
        ]
        return BlockFragment(
            header=SubordinatingConjunctions.BECAUSE.as_fragment(),
            items=reasons,
            conjunction=CoordinatingConjunctions.AND.as_fragment(),
        )

    def _rule_identity_clause(self, plan: CausalStructure) -> VerbalizationFragment:
        """:return: *"by the <kind> rule <code>"* — the identity of the rule that fired (*"by the
        refinement rule R1"*). The code is a role-tagged token, the seam a source-link resolver turns
        into a link to the rule's definition."""
        return PhraseFragment(
            parts=[
                Prepositions.BY.as_fragment(),
                Articles.THE.as_fragment(),
                WordFragment(text=plan.rule_code.kind.value),
                WordFragment(text="rule"),
                RoleFragment(
                    text=plan.rule_code.as_string, role=SemanticRole.RULE_REFERENCE
                ),
            ]
        )
