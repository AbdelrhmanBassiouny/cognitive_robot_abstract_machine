from __future__ import annotations

from krrood.entity_query_language.operators.conditionals import CaseWhen
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    ConditionalPhrases,
    Punctuation,
)


class CaseWhenRule(PhraseRule):
    """*"<then> if <condition>"*, or with a fallback branch, *"<then> if <condition>,
    otherwise <else>"*.

    >>> robot = variable(Robot, [])
    >>> verbalize_expression(case_when(robot.battery > 50, 1, 0))
    '1 if the battery of a Robot is greater than 50, otherwise 0'
    """

    construct = CaseWhen

    def build(self, node: CaseWhen, context: RuleContext) -> VerbalizationFragment:
        """:return: the *"<then> if <condition>"* phrase, with a trailing *", otherwise <else>"*
        when the case has a fallback branch.

        >>> robot = variable(Robot, [])
        >>> verbalize_expression(case_when(robot.battery > 50, 1))
        '1 if the battery of a Robot is greater than 50'
        """
        parts = [
            context.child(node.then_value, as_value=True),
            ConditionalPhrases.IF.as_fragment(),
            context.child(node.condition),
        ]
        if node.else_value is not None:
            parts += [
                Punctuation.COMMA.as_fragment(),
                ConditionalPhrases.OTHERWISE.as_fragment(),
                context.child(node.else_value, as_value=True),
            ]
        return PhraseFragment(parts=parts)
