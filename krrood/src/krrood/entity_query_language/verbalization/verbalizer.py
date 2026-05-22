from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.verbalization.chain_verbalizer import ChainVerbalizer
from krrood.entity_query_language.verbalization.context import VerbalizationContext
from krrood.entity_query_language.verbalization.entity_verbalizer import EntityVerbalizer
from krrood.entity_query_language.verbalization.fragments.base import VerbFragment
from krrood.entity_query_language.verbalization.rule_engine import RuleEngine
from krrood.entity_query_language.verbalization.rule_verbalizer import RuleVerbalizer
from krrood.entity_query_language.verbalization.rules.registry import ALL_RULES
from krrood.entity_query_language.verbalization.utils import _str


@dataclass
class EQLVerbalizer:
    """
    Coordinator that maps an EQL expression tree to a :class:`~krrood.entity_query_language.verbalization.fragments.base.VerbFragment` tree.

    Dispatches via a :class:`~krrood.entity_query_language.verbalization.rule_engine.RuleEngine` of
    :class:`~krrood.entity_query_language.verbalization.rule_engine.VerbalizationRule` classes.
    Each rule declares its guard in :meth:`~krrood.entity_query_language.verbalization.rule_engine.VerbalizationRule.applies`
    and its rendering in :meth:`~krrood.entity_query_language.verbalization.rule_engine.VerbalizationRule.transform`.
    More-specific subclasses are tried before their parents (MRO-depth priority).

    For simple plain-text output use :func:`verbalize_expression`.
    For coloured / formatted output build a
    :class:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline`.

    :ivar _chain: Delegate for :class:`~krrood.entity_query_language.core.mapped_variable.MappedVariable` chains.
    :ivar _entity: Delegate for :class:`~krrood.entity_query_language.query.query.Entity` and
        :class:`~krrood.entity_query_language.query.query.SetOf` expressions.
    :ivar _rule: Delegate for inference-rule (IF/THEN) verbalization.
    :ivar _engine: Rule dispatcher; sorts rules by MRO depth before first call.
    """

    _chain: ChainVerbalizer = field(init=False, repr=False)
    _entity: EntityVerbalizer = field(init=False, repr=False)
    _rule: RuleVerbalizer = field(init=False, repr=False)
    _engine: RuleEngine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rule = RuleVerbalizer(delegate=self)
        self._entity = EntityVerbalizer(delegate=self)
        self._chain = ChainVerbalizer(
            delegate=self,
            entity_inline_fn=self._entity.as_inline_noun,
        )
        self._engine = RuleEngine(ALL_RULES)

    def build(
        self,
        expr: SymbolicExpression,
        ctx: Optional[VerbalizationContext] = None,
    ) -> VerbFragment:
        """
        Translate *expr* into a :class:`~krrood.entity_query_language.verbalization.fragments.base.VerbFragment` tree.

        A fresh :class:`~krrood.entity_query_language.verbalization.context.VerbalizationContext`
        (with a pre-built disambiguation map) is created when *ctx* is ``None``.

        :param expr: Any EQL symbolic expression.
        :type expr: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        :param ctx: Shared verbalization state; created automatically when omitted.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext or None
        :returns: Root of the fragment tree representing *expr* in natural language.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        if ctx is None:
            ctx = VerbalizationContext.from_expression(expr)
        return self._engine.build(expr, ctx, self)

    def verbalize(
        self,
        expr: SymbolicExpression,
        ctx: Optional[VerbalizationContext] = None,
    ) -> str:
        """
        Translate *expr* into a plain-text English string.

        Equivalent to ``_str(self.build(expr, ctx))`` — no colour markup.
        Prefer :class:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline`
        when colour or hierarchical layout is needed.

        :param expr: Any EQL symbolic expression.
        :type expr: ~krrood.entity_query_language.core.base_expressions.SymbolicExpression
        :param ctx: Shared verbalization state; created automatically when omitted.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext or None
        :returns: Plain-text natural-language representation of *expr*.
        :rtype: str
        """
        return _str(self.build(expr, ctx))


_default_verbalizer = EQLVerbalizer()


def verbalize_expression(expr) -> str:
    """
    Verbalize any EQL expression into a human-readable English phrase (plain text).

    This is the simplest entry point: it uses a module-level singleton
    :class:`EQLVerbalizer` with no colour markup.  Call
    :class:`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline`
    directly for coloured or hierarchical output.

    :param expr: Any EQL expression or :class:`~krrood.entity_query_language.query.query.Query`.
    :returns: Plain-text natural-language string.
    :rtype: str
    """
    from krrood.entity_query_language.query.query import Query
    if isinstance(expr, Query):
        expr.build()
    return _default_verbalizer.verbalize(expr)
