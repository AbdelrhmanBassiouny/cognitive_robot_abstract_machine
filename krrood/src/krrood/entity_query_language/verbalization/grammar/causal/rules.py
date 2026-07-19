from __future__ import annotations

from krrood.entity_query_language.rdr.why import WhyAnswer, WhyQuery
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


class WhyQueryRule(PhraseRule):
    """
    Why-query → the causal explanation of its resolved answer.

    The ask-surface counterpart of :class:`CausalExplanationRule`: a
    :class:`~krrood.entity_query_language.rdr.why.WhyQuery` is a non-foldable root the verbalizer
    routes here, and this rule resolves the query's answer and hands it to the same
    :class:`~…grammar.causal.assembler.CausalAssembler`, so a query verbalizes identically to the
    answer it stands for. Its construct is disjoint from ``WhyAnswer``'s, so the two rules never
    compete in ``select``.
    """

    construct = WhyQuery

    def build(self, node: WhyQuery, context: RuleContext) -> VerbalizationFragment:
        """:return: the causal-explanation block built from the query's resolved answer."""
        return CausalAssembler(context).assemble(node.answer)
