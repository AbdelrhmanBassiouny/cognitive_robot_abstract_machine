"""
Aggregation value-subquery **assembler** — realise an aggregation used as a *value*
(*"the maximum amount"*, or *"the sum of amounts among BankTransactions whose …"*).

This is one of the query family's standalone surface forms, extracted from ``QueryAssembler``:
it is keyed on the plan's :attr:`QueryPlan.aggregation_data` and composes the aggregate noun
with an optional *"among <plural source> [whose/such that] [having]"* scope.  It reuses the
shared :class:`RestrictionAssembler` (source filter) and :class:`HavingAssembler`.

Reference: Reiter & Dale (2000) — aggregation; Gatt & Reiter (2009), SimpleNLG — realisation.
"""

from __future__ import annotations

from typing_extensions import List

from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.verbalization.fragments.base import (
    NounPhrase,
    PhraseFragment,
    RoleFragment,
    SubjectScope,
    Fragment,
)
from krrood.entity_query_language.verbalization.fragments.features import (
    Definiteness,
    Number,
)
from krrood.entity_query_language.verbalization.grammar.aggregation_kinds import (
    AGGREGATION_KIND,
)
from krrood.entity_query_language.verbalization.grammar.assembly.base import Assembler
from krrood.entity_query_language.verbalization.grammar.assembly.clauses import (
    HavingAssembler,
)
from krrood.entity_query_language.verbalization.grammar.assembly.restrictions import (
    RestrictionAssembler,
)
from krrood.entity_query_language.verbalization.grammar.planning.query import (
    QueryPlan,
    QueryPlanner,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    FallbackNouns,
    Keywords,
    Prepositions,
)
from krrood.entity_query_language.verbalization.vocabulary.words import ChildForm


class AggregationValueAssembler(Assembler[Query, QueryPlan]):
    """Realise an aggregation value-subquery from its :class:`QueryPlan`."""

    planner = QueryPlanner

    def realize(self, node, plan: QueryPlan) -> Fragment:
        """*"the <aggregation> <leaf>"*, optionally scoped *"among <source> …"* — runs inside
        the query scope pushed by ``NestedEntityRule.enters_query_scope``."""
        aggregation_data = plan.aggregation_data
        if aggregation_data.leaf is None:
            return self.ctx.child(aggregation_data.aggregator)

        aggregation_kind = AGGREGATION_KIND[type(aggregation_data.aggregator)]
        plural_leaf = aggregation_kind.value.child_form == ChildForm.PLURAL
        leaf_frag = RoleFragment.for_attribute(
            aggregation_data.leaf._owner_class_,
            aggregation_data.leaf._attribute_name_,
            number=Number.of(plural_leaf),
        )

        aggregate = NounPhrase(
            head=aggregation_kind.as_fragment(),
            definiteness=Definiteness.DEFINITE,
            modifiers=[leaf_frag],
        )

        if not aggregation_data.is_constrained:
            return aggregate
        return self._scope(node, plan, aggregate)

    def _scope(self, node, plan: QueryPlan, aggregate) -> Fragment:
        """*"<aggregate> among <plural source> [whose …] [such that … their …] [having …]"*.

        The plural source population is the scope's discourse subject (a plural
        ``SubjectScope``), so chains rooted at it pronominalise to *"their …"* instead of the
        ambiguous singular re-mention *"the <Type>"* (which would collide with an outer
        same-type subject)."""
        source = plan.aggregation_data.source
        source_frag = (
            self.ctx.child(source, number=Number.PLURAL)
            if source is not None
            else FallbackNouns.ENTITY.plural_fragment()
        )
        parts: List[Fragment] = [
            aggregate,
            Prepositions.AMONG.as_fragment(),
            source_frag,
        ]

        if plan.subject_restriction is not None:
            r = RestrictionAssembler(self.ctx).render(
                plan.subject_restriction, plan.subject
            )
            parts.extend(r.superlatives)
            if r.whose is not None:
                parts.append(r.whose)
            if r.residual is not None:
                parts += [Keywords.SUCH_THAT.as_fragment(), r.residual]

        having = HavingAssembler(self.ctx).clause(node)
        if having is not None:
            parts.append(having)

        scope_phrase = PhraseFragment(parts=parts)
        if source is None:
            return scope_phrase
        return SubjectScope(
            subject_id=source._id_,
            child=scope_phrase,
            subject_number=Number.PLURAL,
        )
