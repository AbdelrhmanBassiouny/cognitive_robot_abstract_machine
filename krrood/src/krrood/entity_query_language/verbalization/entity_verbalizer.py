"""
EntityVerbalizer — Entity, SetOf, and query-body clause rendering.

Handles the full query form ("Find X such that …"), the inline-noun form
(constraint-deferring), and the standalone-noun form used when an Entity is
the selected variable of an outer query.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from krrood.entity_query_language.core.variable import InstantiatedVariable, Variable
from krrood.entity_query_language.query.quantifiers import An, ResultQuantifier, The
from krrood.entity_query_language.query.query import Entity, Query, SetOf
from krrood.entity_query_language.verbalization.chain_utils import chain_root, verbalize_plural
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    oxford_and,
    PhraseFragment,
    RoleFragment,
    VerbFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    Conjunctions,
    Copulas,
    FallbackNouns,
    Keywords,
    SortDirections,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext


def _word(text: str) -> WordFragment:
    return WordFragment(text=text)


def _role(text, role, ref=None):
    return RoleFragment(text=text, role=role, source_ref=ref)


def _phrase(*parts, sep=" "):
    return PhraseFragment(parts=list(parts), separator=sep)


class EntityVerbalizer:
    """Verbalizes Entity and SetOf query expressions."""

    def __init__(self, delegate) -> None:
        self._d = delegate

    # ── Public entry points ────────────────────────────────────────────────────

    def verbalize_query(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        """Full query form: 'Find X such that …'"""
        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))

        expr.build()

        if self._d._rule.can_handle(expr):
            return self._d._rule.verbalize(expr, ctx)

        is_the = (
            expr._quantifier_builder_ is not None
            and expr._quantifier_builder_.type is The
        )
        var = expr.selected_variable

        if isinstance(var, Entity):
            selected = self.as_noun(var, ctx)
        elif var is None:
            selected_type = FallbackNouns.ENTITY.text
            ctx.seen[expr._id_] = selected_type
            selected = FallbackNouns.ENTITY.plural_fragment()
        elif is_the:
            selected_type = var._type_.__name__ if getattr(var, "_type_", None) else FallbackNouns.ENTITY.text
            ctx.seen[var._id_] = selected_type
            ctx.seen[expr._id_] = selected_type
            selected = _phrase(Articles.THE_UNIQUE.as_fragment(), _role(selected_type, SemanticRole.VARIABLE))
        else:
            selected = self._d.build(var, ctx)
            selected_type = ctx.seen.get(getattr(var, "_id_", None), FallbackNouns.ENTITY.text)
            ctx.seen[expr._id_] = selected_type

        return self._verbalize_query_body_(expr, ctx, selected)

    def as_noun(self, expr: Entity, ctx: VerbalizationContext) -> VerbFragment:
        """Standalone-noun form: 'a Robot where …' (for nested Entity selectors)."""
        if expr._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))

        expr.build()
        is_the = (
            expr._quantifier_builder_ is not None
            and expr._quantifier_builder_.type is The
        )
        var = expr.selected_variable
        selected_type = var._type_.__name__ if var and getattr(var, "_type_", None) else FallbackNouns.ENTITY.text
        ctx.seen[expr._id_] = selected_type
        if var is not None:
            ctx.seen[var._id_] = selected_type

        if is_the:
            article_noun: VerbFragment = _phrase(
                Articles.THE_UNIQUE.as_fragment(), RoleFragment.for_variable(selected_type, var)
            )
        else:
            article_noun = _phrase(
                Articles.indefinite(selected_type),
                RoleFragment.for_variable(selected_type, var),
            )

        where_expr = expr._where_expression_
        if where_expr is not None:
            return _phrase(article_noun, Keywords.WHERE.as_fragment(), self._d.build(where_expr.condition, ctx))
        return article_noun

    def as_inline_noun(self, entity: Entity, ctx: VerbalizationContext) -> VerbFragment:
        """Inline-noun form used as chain root: defers where-condition to ctx constraints."""
        if entity._id_ in ctx.seen:
            return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[entity._id_], SemanticRole.VARIABLE))

        entity.build()
        var = entity.selected_variable
        var_type = getattr(var, "_type_", None)
        type_name = var_type.__name__ if var_type else FallbackNouns.ENTITY.text

        ctx.seen[entity._id_] = type_name
        ctx.seen[var._id_] = type_name

        where_expr = entity._where_expression_
        if where_expr is not None:
            ctx.defer_constraint(where_expr.condition)

        return _phrase(Articles.indefinite(type_name), RoleFragment.for_variable(type_name, var))

    def verbalize_set_of(self, expr: SetOf, ctx: VerbalizationContext) -> VerbFragment:
        expr.build()
        var_frags = [self._d.build(v, ctx) for v in expr._selected_variables_]
        vars_phrase = PhraseFragment(parts=var_frags, separator=", ")
        prefix = _phrase(
            Keywords.FIND_SETS_OF.as_fragment(),
            PhraseFragment(parts=[_word("("), vars_phrase, _word(")")], separator=""),
        )
        return self._verbalize_query_body_(expr, ctx, prefix)

    # ── Query body assembly ────────────────────────────────────────────────────

    def _verbalize_query_body_(
        self, expr, ctx: VerbalizationContext, selection: VerbFragment
    ) -> VerbFragment:
        header = _phrase(Keywords.FIND.as_fragment(), selection)
        clauses = [c for c in [
            self._where_clause(expr, ctx),
            self._grouped_by_clause(expr, ctx),
            self._having_clause(expr, ctx),
            self._ordered_by_clause(expr, ctx),
        ] if c is not None]
        return BlockFragment(header=header, items=clauses)

    def _where_clause(self, expr, ctx: VerbalizationContext) -> Optional[VerbFragment]:
        where_expr = expr._where_expression_
        if where_expr is None:
            return None
        return _phrase(Keywords.SUCH_THAT.as_fragment(), self._d.build(where_expr.condition, ctx))

    def _grouped_by_clause(self, expr, ctx: VerbalizationContext) -> Optional[VerbFragment]:
        grouped_expr = expr._grouped_by_expression_
        if grouped_expr is None or not grouped_expr.variables_to_group_by:
            return None
        group_key_root_ids = self._root_var_ids_(grouped_expr.variables_to_group_by)
        group_frags = [self._d.build(v, ctx) for v in grouped_expr.variables_to_group_by]
        groups_phrase = PhraseFragment(parts=group_frags, separator=", ")
        aggregated_frags = self._aggregated_noun_frags_(expr, group_key_root_ids, ctx)
        if aggregated_frags:
            aggregated_phrase = oxford_and(aggregated_frags, Conjunctions.AND.as_fragment())
            return _phrase(
                Conjunctions.AND.as_fragment(),
                Articles.THE.as_fragment(),
                aggregated_phrase,
                Copulas.ARE.as_fragment(),
                Keywords.GROUPED_BY.as_fragment(),
                groups_phrase,
            )
        return _phrase(Keywords.GROUPED_BY.as_fragment(), groups_phrase)

    def _having_clause(self, expr, ctx: VerbalizationContext) -> Optional[VerbFragment]:
        having_expr = expr._having_expression_
        if having_expr is None:
            return None
        ctx.compact_predicates = True
        having_frag = self._d.build(having_expr.condition, ctx)
        ctx.compact_predicates = False
        return _phrase(Keywords.HAVING.as_fragment(), having_frag)

    def _ordered_by_clause(self, expr, ctx: VerbalizationContext) -> Optional[VerbFragment]:
        ob = expr._ordered_by_builder_
        if ob is None:
            return None
        direction_frag = (
            SortDirections.DESCENDING.as_fragment()
            if ob.descending
            else SortDirections.ASCENDING.as_fragment()
        )
        ordered_frag = self._d.build(ob.variable, ctx)
        paren_frag = PhraseFragment(parts=[_word("("), direction_frag, _word(")")], separator="")
        return _phrase(Keywords.ORDERED_BY.as_fragment(), ordered_frag, paren_frag)

    # ── Grouping helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _root_var_ids_(exprs) -> set:
        ids: set = set()
        for e in exprs:
            root = chain_root(e)
            if isinstance(root, Variable):
                ids.add(root._id_)
        return ids

    @staticmethod
    def _aggregated_expressions_(query_expr, group_key_root_ids: set) -> list:
        selected_var = query_expr.selected_variable if isinstance(query_expr, Entity) else None
        if isinstance(selected_var, InstantiatedVariable):
            result = []
            for child in selected_var._child_vars_.values():
                root = chain_root(child)
                if not (isinstance(root, Variable) and root._id_ in group_key_root_ids):
                    result.append(child)
            return result
        if isinstance(query_expr, Query):
            return [v for v in query_expr._selected_variables_ if v._id_ not in group_key_root_ids]
        return []

    def _aggregated_noun_frags_(
        self, query_expr, group_key_root_ids: set, ctx: VerbalizationContext
    ) -> list[VerbFragment]:
        return [
            verbalize_plural(e, ctx, self._d.build)
            for e in self._aggregated_expressions_(query_expr, group_key_root_ids)
        ]
