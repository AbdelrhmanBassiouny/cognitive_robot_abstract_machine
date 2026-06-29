from __future__ import annotations

from krrood.entity_query_language.dialogue.speech_act import (
    Acknowledge,
    Ask,
    Explain,
    Inform,
    Warn,
)
from krrood.entity_query_language.query.query import Entity
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    VerbalizationFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import Spacing
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    PhraseRule,
    RuleContext,
)
from krrood.entity_query_language.verbalization.vocabulary.words import PunctuationWord

_QUESTION_MARK = PunctuationWord("?", spacing=Spacing.LEFT)
"""Sentence-final question mark, glued to the preceding word."""

_PERIOD = PunctuationWord(".", spacing=Spacing.LEFT)
"""Sentence-final period, glued to the preceding word."""


def _proposition_body(expression, context: RuleContext) -> VerbalizationFragment:
    """Verbalize the body of a proposition, unwrapping a query to its selected relation."""
    if isinstance(expression, Entity):
        expression = expression.selected_variable
    return context.child(expression)


class AskRule(PhraseRule):
    """``Ask`` → the question followed by a question mark."""

    construct = Ask
    name = "ask"
    enters_query_scope = True

    def build(self, node: Ask, context: RuleContext) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[context.child(node.question), _QUESTION_MARK.as_fragment()]
        )


class InformRule(PhraseRule):
    """``Inform`` → the asserted relation as a statement."""

    construct = Inform
    name = "inform"
    enters_query_scope = True

    def build(self, node: Inform, context: RuleContext) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                _proposition_body(node.answer.query, context),
                _PERIOD.as_fragment(),
            ]
        )


class ExplainRule(PhraseRule):
    """``Explain`` → *"Because <conditions joined by 'and'>."*"""

    construct = Explain
    name = "explain"
    enters_query_scope = True

    def build(self, node: Explain, context: RuleContext) -> VerbalizationFragment:
        causes = node.answer.cause_set.causes
        parts: list[VerbalizationFragment] = [WordFragment(text="Because")]
        if not causes:
            parts.append(WordFragment(text="no condition was recorded"))
        for index, cause in enumerate(causes):
            if index > 0:
                parts.append(WordFragment(text="and"))
            parts.append(context.child(cause.condition))
        parts.append(_PERIOD.as_fragment())
        return PhraseFragment(parts=parts)


class WarnRule(PhraseRule):
    """``Warn`` → *"Warning: <relation>."*"""

    construct = Warn
    name = "warn"
    enters_query_scope = True

    def build(self, node: Warn, context: RuleContext) -> VerbalizationFragment:
        return PhraseFragment(
            parts=[
                WordFragment(text="Warning:"),
                _proposition_body(node.proposition, context),
                _PERIOD.as_fragment(),
            ]
        )


class AcknowledgeRule(PhraseRule):
    """``Acknowledge`` → a fixed acknowledgement."""

    construct = Acknowledge
    name = "acknowledge"

    def build(self, node: Acknowledge, context: RuleContext) -> VerbalizationFragment:
        return WordFragment(text="Understood.")
