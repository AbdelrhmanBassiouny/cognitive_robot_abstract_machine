from __future__ import annotations

from krrood.entity_query_language.questions.why import Why
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    RoleFragment,
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)


class WhyQuestionRule(PhraseRule):
    """``Why`` → *"why <explained relation>"*.

    The explained relation is the body of the child query, so the question surfaces the proposition
    asked about (*"why a MontessoriObject is in the square hole"*) rather than the retrieval framing.
    """

    construct = Why
    name = "why-question"
    enters_query_scope = True

    def build(self, node: Why, context: RuleContext) -> VerbalizationFragment:
        explained = (
            node.explained_proposition
            if node.explained_proposition is not None
            else node._child_
        )
        return PhraseFragment(
            parts=[RoleFragment.for_operator("why"), context.child(explained)]
        )
