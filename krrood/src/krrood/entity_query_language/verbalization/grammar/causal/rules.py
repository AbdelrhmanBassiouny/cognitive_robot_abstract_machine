from __future__ import annotations

from krrood.entity_query_language.rdr.why import WhyAnswer
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.grammar.causal.assembler import (
    CausalAssembler,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)


class CausalExplanationRule(PhraseRule):
    """
    Why-answer → *"<conclusion> because <conditions>, by the <kind> rule"* block.

    Auto-registered by the RULES walker. A why-answer is not a foldable EQL node, so it never
    reaches this rule through ordinary recursion; instead the verbalizer routes a top-level
    :class:`~krrood.entity_query_language.rdr.why.WhyAnswer` here (beside the ``Match`` special case),
    the one non-foldable-root precedent. Keeping the dispatch declarative — a rule on the construct
    rather than a hard-coded assembler call — lets ``select`` pick it exactly as it picks any grammar
    rule.
    """

    construct = WhyAnswer

    def build(self, node: WhyAnswer, context: RuleContext) -> VerbalizationFragment:
        """:return: the causal-explanation block built by the causal assembler."""
        return CausalAssembler(context).assemble(node)
