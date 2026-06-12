"""
EQL verbalizer — the internal fragment **builder**.

:class:`EQLVerbalizer` dispatches an EQL expression tree through the grammar
:func:`~krrood.entity_query_language.verbalization.engine.fold` and runs the realisation passes,
returning a :class:`~krrood.entity_query_language.verbalization.fragments.base.Fragment` tree.
It is used by the
:class:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline`, which is the
public entry point (and exposes the plain-text shortcut
:func:`~krrood.entity_query_language.verbalization.pipeline.verbalize_expression`).  Use this
class directly only when you need the fragment tree itself (e.g. fragment-level tests).
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.verbalization.context import VerbalizationContext
from krrood.entity_query_language.verbalization.engine import fold
from krrood.entity_query_language.verbalization.fragments.base import Fragment
from krrood.entity_query_language.verbalization.grammar.english import RULES
from krrood.entity_query_language.verbalization.rendering.realization import (
    realize_tree,
)


@dataclass
class EQLVerbalizer:
    """
    Builds a :class:`~krrood.entity_query_language.verbalization.fragments.base.Fragment` tree
    from an EQL expression — the fragment-producing core behind
    :class:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline`.

    Dispatches via the grammar :func:`~krrood.entity_query_language.verbalization.engine.fold`:
    a single catamorphism over the EQL tree that selects the most-specific
    :class:`~krrood.entity_query_language.verbalization.grammar.phrase_rule.PhraseRule`
    for each node (see :mod:`~krrood.entity_query_language.verbalization.grammar`).
    """

    def build(
        self,
        expression: SymbolicExpression,
        context: Optional[VerbalizationContext] = None,
    ) -> Fragment:
        """
        Translate *expression* into a :class:`~krrood.entity_query_language.verbalization.fragments.base.Fragment` tree
        via the grammar :func:`~krrood.entity_query_language.verbalization.engine.fold`, then run
        the realisation passes.

        A fresh context is created when *context* is ``None``; pass a shared context across calls
        for coreference (a Robot … the Robot).

        :param expression: Any EQL symbolic expression.
        :type expression: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        :param context: Shared verbalization state; created automatically when omitted.
        :type context: ~krrood.entity_query_language.verbalization.context.VerbalizationContext or None
        :return: Root of the fragment tree representing *expression* in natural language.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.Fragment
        """
        if context is None:
            context = VerbalizationContext.from_expression(expression)
        # Referents already introduced by prior builds on this (shared) context, so the same
        # expression verbalized twice reads "a Robot" then "the Robot".  Snapshot BEFORE the
        # fold, which records this build's own mentions in the same set.
        already_seen = set(context.referring.seen)
        fragment = fold(expression, context, RULES)
        return realize_tree(fragment, already_seen=already_seen)
