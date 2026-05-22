"""
ChainVerbalizer — all MappedVariable chain rendering logic.

Handles Attribute, Index, Call, and FlatVariable expressions, plus the
boolean-predicate and possessive path forms they produce.
"""
from __future__ import annotations

import datetime as _dt
from typing import Callable, Optional, TYPE_CHECKING

from krrood.entity_query_language.core.mapped_variable import Attribute, Call, FlatVariable, Index, MappedVariable
from krrood.entity_query_language.verbalization.chain_utils import build_path_parts, walk_chain
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    RoleFragment,
    VerbFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.fragments.source_ref import SourceRef
from krrood.entity_query_language.verbalization.utils import _ordinal
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    Copulas,
    Prepositions,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext


def _word(text: str):
    from krrood.entity_query_language.verbalization.fragments.base import WordFragment
    return WordFragment(text=text)


def _role(text, role, ref=None):
    return RoleFragment(text=text, role=role, source_ref=ref)


def _phrase(*parts, sep=" "):
    return PhraseFragment(parts=list(parts), separator=sep)


class ChainVerbalizer:
    """
    Verbalizes :class:`~krrood.entity_query_language.core.mapped_variable.MappedVariable`
    chains into possessive or predicative
    :class:`~krrood.entity_query_language.verbalization.fragments.base.VerbFragment` trees.

    Handles four chain node types:

    * :class:`~krrood.entity_query_language.core.mapped_variable.Attribute` — produces *"the attr of the Root"*.
    * :class:`~krrood.entity_query_language.core.mapped_variable.Index` — subscript access, e.g. *"the first"*.
    * :class:`~krrood.entity_query_language.core.mapped_variable.Call` — callable invocation *"()"*.
    * :class:`~krrood.entity_query_language.core.mapped_variable.FlatVariable` — transparent unwrapper.

    Boolean terminal attributes use a predicative form: *"<nav> is [not] <attr>"*.

    :param delegate: The parent verbalizer for recursive sub-expression calls.
    :type delegate: ~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer
    :param entity_inline_fn: Callable that verbalizes an Entity as an inline noun
        and defers its WHERE condition (bound to
        :meth:`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer.as_inline_noun`).
    :type entity_inline_fn: Callable
    """

    def __init__(self, delegate, entity_inline_fn: Callable) -> None:
        self._d = delegate
        self._entity_inline = entity_inline_fn

    # ── Dispatch entry points ──────────────────────────────────────────────────

    def verbalize_mapped(self, expr: MappedVariable, ctx: "VerbalizationContext") -> VerbFragment:
        """
        Verbalize a :class:`~krrood.entity_query_language.core.mapped_variable.MappedVariable`
        chain in affirmative form.

        For boolean terminal attributes produces *"<nav> is <attr>"*; for all
        others produces the possessive *"the attr of the Root"* path.

        :param expr: Root node of a MappedVariable chain.
        :type expr: ~krrood.entity_query_language.core.mapped_variable.MappedVariable
        :param ctx: Shared verbalization state.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :returns: Fragment for the chain.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return self._verbalize_mapped_chain_(expr, ctx)

    def verbalize_mapped_negated(self, expr: MappedVariable, ctx: "VerbalizationContext") -> VerbFragment:
        """
        Verbalize a :class:`~krrood.entity_query_language.core.mapped_variable.MappedVariable`
        chain in negated form.

        Used by :class:`~krrood.entity_query_language.verbalization.rules.logical.NotBoolAttrRule`
        to produce *"<nav> is not <attr>"* for boolean attributes.

        :param expr: Root node of a MappedVariable chain.
        :type expr: ~krrood.entity_query_language.core.mapped_variable.MappedVariable
        :param ctx: Shared verbalization state.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :returns: Negated fragment for the chain.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return self._verbalize_mapped_chain_(expr, ctx, negated=True)

    def verbalize_flat(self, expr: FlatVariable, ctx: "VerbalizationContext") -> VerbFragment:
        """
        Verbalize a :class:`~krrood.entity_query_language.core.mapped_variable.FlatVariable`
        by delegating to its child expression.

        :class:`~krrood.entity_query_language.core.mapped_variable.FlatVariable` is a
        transparent wrapper added during SetOf expansion; verbalization simply
        unwraps it.

        :param expr: The FlatVariable expression.
        :type expr: ~krrood.entity_query_language.core.mapped_variable.FlatVariable
        :param ctx: Shared verbalization state.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :returns: Fragment for the child expression.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        return self._d.build(expr._child_, ctx)

    # ── Internal chain logic ───────────────────────────────────────────────────

    def _verbalize_mapped_chain_(
        self, expr: MappedVariable, ctx: VerbalizationContext, negated: bool = False
    ) -> VerbFragment:
        chain, leaf = walk_chain(expr)
        terminal = chain[-1]
        if isinstance(terminal, Attribute) and terminal._type_ is bool:
            return self._verbalize_bool_attribute_chain_(chain, leaf, ctx, negated)
        root_frag = self._verbalize_chain_root_(leaf, ctx)
        return self._render_path_(build_path_parts(chain), root_frag)

    def _render_path_(
        self, parts: list[tuple[str, Optional[SourceRef]]], root_frag: VerbFragment
    ) -> VerbFragment:
        if not parts:
            return root_frag
        reversed_parts = list(reversed(parts))
        first_name, first_ref = reversed_parts[0]
        frag_parts: list[VerbFragment] = [
            Articles.THE.as_fragment(),
            _role(first_name, SemanticRole.ATTRIBUTE, first_ref),
        ]
        for attr_name, attr_ref in reversed_parts[1:]:
            frag_parts.extend([
                Prepositions.OF_THE.as_fragment(),
                _role(attr_name, SemanticRole.ATTRIBUTE, attr_ref),
            ])
        frag_parts.extend([Prepositions.OF.as_fragment(), root_frag])
        return PhraseFragment(parts=frag_parts, separator=" ")

    def _verbalize_chain_root_(self, leaf, ctx: VerbalizationContext) -> VerbFragment:
        """Noun phrase for the root of an attribute chain; unwraps ResultQuantifier wrappers."""
        from krrood.entity_query_language.query.quantifiers import ResultQuantifier
        from krrood.entity_query_language.query.query import Entity
        inner = leaf
        while isinstance(inner, ResultQuantifier):
            inner = inner._child_
        if isinstance(inner, Entity):
            return self._entity_inline(inner, ctx)
        return self._d.build(leaf, ctx)

    def _verbalize_navigation_chain_(
        self, nav_chain: list, root_frag: VerbFragment
    ) -> VerbFragment:
        """Fragment for the navigation path up to (but not including) the terminal attribute."""
        if not nav_chain:
            return root_frag
        if isinstance(nav_chain[-1], Index) and isinstance(nav_chain[-1]._key_, int):
            ordinal = _ordinal(nav_chain[-1]._key_)
            pre_frag = self._render_path_(build_path_parts(nav_chain[:-1]), root_frag)
            return _phrase(Articles.THE.as_fragment(), _word(ordinal), Prepositions.OF.as_fragment(), pre_frag)
        return self._render_path_(build_path_parts(nav_chain), root_frag)

    def _verbalize_bool_attribute_chain_(
        self, chain: list, leaf, ctx: VerbalizationContext, negated: bool
    ) -> VerbFragment:
        """Produces '<nav-path> is [not] <attr>' for boolean terminal attributes."""
        root_frag = self._verbalize_chain_root_(leaf, ctx)
        nav_frag = self._verbalize_navigation_chain_(chain[:-1], root_frag)
        copula = Copulas.IS_NOT.as_fragment() if negated else Copulas.IS.as_fragment()
        terminal = chain[-1]
        attr_name = terminal._attribute_name_
        owner = terminal._owner_class_
        return _phrase(nav_frag, copula, RoleFragment.for_attribute(attr_name, owner, attr_name))

    # ── Temporal helper (used by Comparator and Not) ───────────────────────────

    def is_temporal(self, expr) -> bool:
        """
        Return ``True`` when *expr* represents a
        :class:`datetime.datetime` value or variable.

        Used by comparator rules to select temporal operator phrases
        (*"is before"*, *"is after"*, etc.) instead of relational ones.

        :param expr: Any EQL expression.
        :returns: ``True`` when the expression is datetime-typed.
        :rtype: bool
        """
        from krrood.entity_query_language.core.variable import Literal, Variable
        if isinstance(expr, Literal):
            return isinstance(expr._value_, _dt.datetime)
        if isinstance(expr, Variable):
            return getattr(expr, "_type_", None) is _dt.datetime
        if isinstance(expr, MappedVariable):
            chain, _ = walk_chain(expr)
            return bool(chain) and getattr(chain[-1], "_type_", None) is _dt.datetime
        return False
