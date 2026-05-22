from __future__ import annotations

from typing import TYPE_CHECKING

from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.verbalization.fragments.base import PhraseFragment, RoleFragment, VerbFragment
from krrood.entity_query_language.verbalization.rule_engine import VerbalizationRule
from krrood.entity_query_language.verbalization.vocabulary.english import Operators

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext
    from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)


class ComparatorRule(VerbalizationRule):
    """
    Verbalizes :class:`~krrood.entity_query_language.operators.comparator.Comparator`
    expressions as *"<left> <operator> <right>"*.

    Selects the correct operator phrase via
    :meth:`~krrood.entity_query_language.verbalization.vocabulary.english.Operators.from_callable`
    using the ``compact`` and ``temporal`` flags from the context.

    Falls back to ``expr._name_`` as a plain operator fragment when the
    callable is not registered in
    :class:`~krrood.entity_query_language.verbalization.vocabulary.english.Operators`.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.operators.comparator.Comparator` expressions."""
        return isinstance(expr, Comparator)

    @classmethod
    def transform(cls, expr: "Comparator", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Build *"<left> <operator> <right>"*.

        :param expr: Comparator expression.
        :param ctx: Shared verbalization state (``compact_predicates`` used for HAVING clauses).
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Comparison phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        left = delegate.build(expr.left, ctx)
        right = delegate.build(expr.right, ctx)
        is_temporal = delegate._chain.is_temporal(expr.left) or delegate._chain.is_temporal(expr.right)
        try:
            op_frag = Operators.from_callable(expr.operation).select(
                compact=ctx.compact_predicates, temporal=is_temporal
            ).as_fragment()
        except KeyError:
            op_frag = RoleFragment.for_operator(expr._name_)
        return _phrase(left, op_frag, right)
