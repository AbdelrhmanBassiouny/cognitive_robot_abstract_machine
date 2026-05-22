from __future__ import annotations

from typing import TYPE_CHECKING

from krrood.entity_query_language.core.mapped_variable import Attribute, MappedVariable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.operators.core_logical_operators import AND, OR, Not, LogicalOperator
from krrood.entity_query_language.verbalization.fragments.base import join_with, oxford_and, PhraseFragment, RoleFragment, VerbFragment
from krrood.entity_query_language.verbalization.rule_engine import VerbalizationRule
from krrood.entity_query_language.verbalization.vocabulary.english import Conjunctions, Logicals, Operators

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext
    from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer


def _word(text: str) -> VerbFragment:
    from krrood.entity_query_language.verbalization.fragments.base import WordFragment
    return WordFragment(text=text)


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)




def _is_bool_attr_chain(expr) -> bool:
    if not isinstance(expr, MappedVariable):
        return False
    from krrood.entity_query_language.verbalization.chain_utils import walk_chain
    chain, _ = walk_chain(expr)
    return bool(chain) and isinstance(chain[-1], Attribute) and chain[-1]._type_ is bool


class LogicalRule(VerbalizationRule):
    """
    Abstract base rule: catches any
    :class:`~krrood.entity_query_language.operators.core_logical_operators.LogicalOperator`.

    Concrete subclasses (:class:`AndRule`, :class:`OrRule`, :class:`NotRule`)
    handle specific operator types and take priority over this class due to MRO-depth
    sorting in :class:`~krrood.entity_query_language.verbalization.rule_engine.RuleEngine`.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for any :class:`~krrood.entity_query_language.operators.core_logical_operators.LogicalOperator`."""
        return isinstance(expr, LogicalOperator)


class AndRule(LogicalRule):
    """
    Verbalizes conjunctions (``AND(a, b, c)``) as *"a, b, and c"* using Oxford-comma style.

    Flattens nested AND chains before joining so that ``AND(AND(a,b),c)``
    produces *"a, b, and c"* rather than *"(a and b) and c"*.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.operators.core_logical_operators.AND` expressions."""
        return isinstance(expr, AND)

    @classmethod
    def transform(cls, expr: "AND", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Flatten the AND chain and join with Oxford-comma *"and"*.

        :param expr: Root AND expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Oxford-comma joined fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        parts = [delegate.build(c, ctx) for c in ctx.flatten_same_type(expr, AND)]
        if len(parts) == 1:
            return parts[0]
        return oxford_and(parts, Conjunctions.AND.as_fragment())


class OrRule(LogicalRule):
    """
    Verbalizes disjunctions as *"either a, b, or c"* using Oxford-comma style.

    Flattens nested OR chains before joining.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.operators.core_logical_operators.OR` expressions."""
        return isinstance(expr, OR)

    @classmethod
    def transform(cls, expr: "OR", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Flatten the OR chain and produce *"either a, b, or c"*.

        :param expr: Root OR expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Disjunction phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        parts = [delegate.build(c, ctx) for c in ctx.flatten_same_type(expr, OR)]
        if len(parts) == 1:
            return parts[0]
        head_with_comma = PhraseFragment(
            parts=[join_with(parts[:-1], _word(", ")), _word(",")], separator=""
        )
        return _phrase(Logicals.EITHER.as_fragment(), head_with_comma, Conjunctions.OR.as_fragment(), parts[-1])


class NotRule(LogicalRule):
    """
    Generic negation rule: wraps the child in *"not (<child>)"*.

    :class:`NotComparatorRule` and :class:`NotBoolAttrRule` take priority when
    they match (they are deeper in the MRO hierarchy).
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.operators.core_logical_operators.Not` expressions."""
        return isinstance(expr, Not)

    @classmethod
    def transform(cls, expr: "Not", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Build *"not (<child>)"*.

        :param expr: Not expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Negation phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        child_frag = delegate.build(expr._child_, ctx)
        return _phrase(
            Logicals.NOT.as_fragment(),
            PhraseFragment(parts=[_word("("), child_frag, _word(")")], separator=""),
        )


class NotComparatorRule(NotRule):
    """
    Negates a Comparator inline: *"a is not greater than b"* instead of *"not (a is greater than b)"*.

    Applies when the Not child is a
    :class:`~krrood.entity_query_language.operators.comparator.Comparator`.
    Uses :meth:`~krrood.entity_query_language.verbalization.vocabulary.english.Operators.from_callable`
    with ``negated=True`` to select the negated operator phrase.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` when the Not child is a Comparator."""
        return isinstance(expr, Not) and isinstance(expr._child_, Comparator)

    @classmethod
    def transform(cls, expr: "Not", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Build *"<left> <negated_op> <right>"*.

        :param expr: Not-wrapping-Comparator expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Negated comparator phrase.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        child = expr._child_
        left = delegate.build(child.left, ctx)
        right = delegate.build(child.right, ctx)
        is_temporal = delegate._chain.is_temporal(child.left) or delegate._chain.is_temporal(child.right)
        try:
            op_frag = Operators.from_callable(child.operation).select(
                negated=True, compact=ctx.compact_predicates, temporal=is_temporal
            ).as_fragment()
        except KeyError:
            op_frag = RoleFragment.for_operator(f"not {child._name_}")
        return _phrase(left, op_frag, right)


class NotBoolAttrRule(NotRule):
    """
    Negates a boolean attribute chain: *"<nav> is not <attr>"*.

    Applies when the Not child is a
    :class:`~krrood.entity_query_language.core.mapped_variable.MappedVariable`
    chain whose terminal node is a ``bool``-typed
    :class:`~krrood.entity_query_language.core.mapped_variable.Attribute`.
    Delegates to :meth:`~krrood.entity_query_language.verbalization.chain_verbalizer.ChainVerbalizer.verbalize_mapped_negated`.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` when the Not child is a bool-typed Attribute chain."""
        return isinstance(expr, Not) and _is_bool_attr_chain(expr._child_)

    @classmethod
    def transform(cls, expr: "Not", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Delegate to :meth:`~krrood.entity_query_language.verbalization.chain_verbalizer.ChainVerbalizer.verbalize_mapped_negated`.

        :param expr: Not-wrapping-bool-Attribute expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Predicative *"is not <attr>"* fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return delegate._chain.verbalize_mapped_negated(expr._child_, ctx)
