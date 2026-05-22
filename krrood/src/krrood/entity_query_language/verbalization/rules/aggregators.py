from __future__ import annotations

from typing import TYPE_CHECKING

from krrood.entity_query_language.operators.aggregators import (
    Aggregator, Count, CountAll, Sum, Average, Max, Min, Mode, MultiMode,
)
from krrood.entity_query_language.verbalization.chain_utils import verbalize_plural
from krrood.entity_query_language.verbalization.fragments.base import PhraseFragment, VerbFragment
from krrood.entity_query_language.verbalization.rule_engine import VerbalizationRule
from krrood.entity_query_language.verbalization.utils import _str
from krrood.entity_query_language.verbalization.vocabulary.english import Aggregations, Articles

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext
    from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)


_AGGREGATION_KIND: dict[type, Aggregations] = {
    Count:      Aggregations.COUNT,
    Sum:        Aggregations.SUM,
    Average:    Aggregations.AVERAGE,
    Max:        Aggregations.MAX,
    Min:        Aggregations.MIN,
    Mode:       Aggregations.MODE,
    MultiMode:  Aggregations.MULTI_MODE,
}


class AggregatorRule(VerbalizationRule):
    """
    Verbalizes any :class:`~krrood.entity_query_language.operators.aggregators.Aggregator`
    subtype via the ``_AGGREGATION_KIND`` lookup table.

    Produces *"<agg_phrase> <plural_child>"* (e.g. *"sum of tasks"*).
    On second mention inserts *"the"* before the phrase for coreference consistency.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for any :class:`~krrood.entity_query_language.operators.aggregators.Aggregator`."""
        return isinstance(expr, Aggregator)

    @classmethod
    def transform(cls, expr: "Aggregator", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Build *"<aggregation> <plural_child>"*, or *"the <aggregation> <plural_child>"* on re-mention.

        :param expr: Aggregator expression.
        :param ctx: Shared verbalization state.
        :param delegate: Parent verbalizer for recursive calls.
        :returns: Aggregation phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        child_frag = verbalize_plural(expr._child_, ctx, delegate.build)
        agg_frag = _AGGREGATION_KIND[type(expr)].as_fragment()
        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), agg_frag, child_frag)
        ctx.seen[expr._id_] = _str(_phrase(agg_frag, child_frag))
        return _phrase(agg_frag, child_frag)


class CountAllRule(AggregatorRule):
    """
    Verbalizes :class:`~krrood.entity_query_language.operators.aggregators.CountAll`
    as *"count of all"* (no child expression).

    Takes priority over :class:`AggregatorRule` for ``CountAll`` instances.
    """

    @classmethod
    def applies(cls, expr, ctx: "VerbalizationContext") -> bool:
        """Return ``True`` for :class:`~krrood.entity_query_language.operators.aggregators.CountAll`."""
        return isinstance(expr, CountAll)

    @classmethod
    def transform(cls, expr: "CountAll", ctx: "VerbalizationContext", delegate: "EQLVerbalizer") -> VerbFragment:
        """
        Return the *"count of all"* aggregation fragment directly.

        :param expr: CountAll expression.
        :param ctx: Shared verbalization state (unused).
        :param delegate: Parent verbalizer (unused).
        :returns: ``Aggregations.COUNT_ALL.as_fragment()``.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return Aggregations.COUNT_ALL.as_fragment()
