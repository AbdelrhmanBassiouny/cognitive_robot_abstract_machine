from __future__ import annotations

from typing import TYPE_CHECKING

from krrood.entity_query_language.core.base_expressions import Filter
from krrood.entity_query_language.query.operations import GroupedBy, OrderedBy
from krrood.entity_query_language.query.quantifiers import ResultQuantifier
from krrood.entity_query_language.query.query import Entity, SetOf
from krrood.entity_query_language.verbalization.fragments.base import PhraseFragment, VerbFragment
from krrood.entity_query_language.verbalization.rule_engine import VerbalizationRule
from krrood.entity_query_language.verbalization.vocabulary.english import Keywords, SortDirections

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext
    from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer


def _word(text: str) -> VerbFragment:
    from krrood.entity_query_language.verbalization.fragments.base import WordFragment
    return WordFragment(text=text)


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)


class EntityRule(VerbalizationRule):
    """
    Delegates :class:`~krrood.entity_query_language.query.query.Entity` expressions to
    :meth:`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer.verbalize_query`.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.query.query.Entity` expressions."""
        return isinstance(expr, Entity)

    @classmethod
    def transform(cls, expr: "Entity", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Delegate to :meth:`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer.verbalize_query`.

        :param expr: Entity expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer.
        :returns: Full query fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return delegate._entity.verbalize_query(expr, ctx)


class SetOfRule(VerbalizationRule):
    """
    Delegates :class:`~krrood.entity_query_language.query.query.SetOf` expressions to
    :meth:`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer.verbalize_set_of`.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.query.query.SetOf` expressions."""
        return isinstance(expr, SetOf)

    @classmethod
    def transform(cls, expr: "SetOf", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Delegate to :meth:`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer.verbalize_set_of`.

        :param expr: SetOf expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer.
        :returns: SetOf query fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return delegate._entity.verbalize_set_of(expr, ctx)


class ResultQuantifierRule(VerbalizationRule):
    """
    Transparent wrapper: delegates to the child expression.

    :class:`~krrood.entity_query_language.query.quantifiers.An`,
    :class:`~krrood.entity_query_language.query.quantifiers.The`, and other
    :class:`~krrood.entity_query_language.query.quantifiers.ResultQuantifier` subclasses
    carry selection metadata but add no natural-language content.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for any :class:`~krrood.entity_query_language.query.quantifiers.ResultQuantifier`."""
        return isinstance(expr, ResultQuantifier)

    @classmethod
    def transform(cls, expr: "ResultQuantifier", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Unwrap and delegate to the child expression.

        :param expr: ResultQuantifier wrapper.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer.
        :returns: Fragment for the unwrapped child.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return delegate.build(expr._child_, ctx)


class FilterRule(VerbalizationRule):
    """
    Transparent wrapper: delegates to the filter's condition expression.

    Both :class:`~krrood.entity_query_language.core.base_expressions.Where` and
    :class:`~krrood.entity_query_language.core.base_expressions.Having` (both ``Filter``
    subclasses) are handled by this rule.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for any :class:`~krrood.entity_query_language.core.base_expressions.Filter`."""
        return isinstance(expr, Filter)

    @classmethod
    def transform(cls, expr: "Filter", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Delegate to the condition expression.

        :param expr: Filter expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer.
        :returns: Fragment for the condition.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return delegate.build(expr.condition, ctx)


class GroupedByRule(VerbalizationRule):
    """
    Verbalizes :class:`~krrood.entity_query_language.query.operations.GroupedBy`
    as *"grouped by <key1>, <key2>, …"*.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.query.operations.GroupedBy`."""
        return isinstance(expr, GroupedBy)

    @classmethod
    def transform(cls, expr: "GroupedBy", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Build *"grouped by <key1>, <key2>, …"*, or *"grouped"* when no keys.

        :param expr: GroupedBy expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for key expression rendering.
        :returns: Grouped-by phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        if expr.variables_to_group_by:
            group_frags = [delegate.build(v, ctx) for v in expr.variables_to_group_by]
            return _phrase(Keywords.GROUPED_BY.as_fragment(), PhraseFragment(parts=group_frags, separator=", "))
        return Keywords.GROUPED.as_fragment()


class OrderedByRule(VerbalizationRule):
    """
    Verbalizes :class:`~krrood.entity_query_language.query.operations.OrderedBy`
    as *"ordered by <variable> (ascending|descending)"*.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.query.operations.OrderedBy`."""
        return isinstance(expr, OrderedBy)

    @classmethod
    def transform(cls, expr: "OrderedBy", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Build *"ordered by <variable> (ascending|descending)"*.

        :param expr: OrderedBy expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for variable rendering.
        :returns: Ordered-by phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        direction_frag = (
            SortDirections.DESCENDING.as_fragment()
            if expr.descending
            else SortDirections.ASCENDING.as_fragment()
        )
        ordered_frag = delegate.build(expr.variable, ctx)
        paren_frag = PhraseFragment(parts=[_word("("), direction_frag, _word(")")], separator="")
        return _phrase(Keywords.ORDERED_BY.as_fragment(), ordered_frag, paren_frag)
