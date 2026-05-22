from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from krrood.entity_query_language.core.variable import ExternallySetVariable, InstantiatedVariable, Literal, Variable
from krrood.entity_query_language.predicate import Verbalizable
from krrood.entity_query_language.verbalization.chain_utils import verbalize_plural
from krrood.entity_query_language.verbalization.context import ArticleSelection
from krrood.entity_query_language.verbalization.fragments.base import (
    oxford_and, PhraseFragment, RoleFragment, VerbFragment, WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.fragments.source_ref import SourceRef
from krrood.entity_query_language.verbalization.rule_engine import VerbalizationRule
from krrood.entity_query_language.verbalization.utils import inflect_engine
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles, Conjunctions, Copulas, Keywords, Prepositions,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext
    from krrood.entity_query_language.verbalization.verbalizer import EQLVerbalizer


def _word(text: str) -> WordFragment:
    return WordFragment(text=text)


def _phrase(*parts: VerbFragment, sep: str = " ") -> PhraseFragment:
    return PhraseFragment(parts=list(parts), separator=sep)


def _role(text: str, role: SemanticRole, source_ref=None) -> RoleFragment:
    return RoleFragment(text=text, role=role, source_ref=source_ref)


class VariableRule(VerbalizationRule):
    @classmethod
    def applies(cls, expr, ctx: VerbalizationContext) -> bool:
        return isinstance(expr, Variable)

    @classmethod
    def transform(cls, expr: Variable, ctx: VerbalizationContext, delegate: EQLVerbalizer) -> VerbFragment:
        article, label = ctx.noun_for_parts(expr)
        label_frag = RoleFragment.for_variable(label, expr)
        if article == ArticleSelection.NONE:
            return label_frag
        if article == ArticleSelection.DEFINITE:
            return _phrase(Articles.THE.as_fragment(), label_frag)
        return _phrase(Articles.indefinite(label), label_frag)


class LiteralRule(VariableRule):
    """Literal is a subclass of Variable; renders as a plain semantic-role fragment."""

    @classmethod
    def applies(cls, expr, ctx: VerbalizationContext) -> bool:
        return isinstance(expr, Literal)

    @classmethod
    def transform(cls, expr: Literal, ctx: VerbalizationContext, delegate: EQLVerbalizer) -> VerbFragment:
        return _role(ctx.type_name_of_value(expr._value_), SemanticRole.LITERAL)


class ExternallySetVariableRule(VerbalizationRule):
    """ExternallySetVariable is a sibling of Variable (both inherit CanHaveDomainSource)."""

    @classmethod
    def applies(cls, expr, ctx: VerbalizationContext) -> bool:
        return isinstance(expr, ExternallySetVariable)

    @classmethod
    def transform(cls, expr: ExternallySetVariable, ctx: VerbalizationContext, delegate: EQLVerbalizer) -> VerbFragment:
        type_name = expr._type_.__name__ if getattr(expr, "_type_", None) else "variable"
        return _phrase(Articles.indefinite(type_name), _role(type_name, SemanticRole.VARIABLE))


class InstantiatedVariableRule(VerbalizationRule):
    """InstantiatedVariable natural form: 'a TypeName where the field of the TypeName is …'"""

    @classmethod
    def applies(cls, expr, ctx: VerbalizationContext) -> bool:
        return isinstance(expr, InstantiatedVariable)

    @classmethod
    def transform(cls, expr: InstantiatedVariable, ctx: VerbalizationContext, delegate: EQLVerbalizer) -> VerbFragment:
        return _verbalize_instantiated_natural(expr, ctx, delegate)


class InstantiatedVerbalizableRule(InstantiatedVariableRule):
    """InstantiatedVariable whose type provides a _verbalization_template_(); uses it directly.

    Known limitation: the user-supplied format string cannot carry semantic roles,
    so the result is a plain WordFragment.
    """

    @classmethod
    def applies(cls, expr, ctx: VerbalizationContext) -> bool:
        return isinstance(expr, InstantiatedVariable) and _has_verbalization_template(expr)

    @classmethod
    def transform(cls, expr: InstantiatedVariable, ctx: VerbalizationContext, delegate: EQLVerbalizer) -> VerbFragment:
        template = expr._type_._verbalization_template_()
        kwargs = {name: delegate.verbalize(child, ctx) for name, child in expr._child_vars_.items()}
        return _word(template.format(**kwargs))


# ── Module-level helpers ───────────────────────────────────────────────────────

def _has_verbalization_template(expr: InstantiatedVariable) -> bool:
    try:
        if isinstance(expr._type_, type) and issubclass(expr._type_, Verbalizable):
            expr._type_._verbalization_template_()
            return True
    except NotImplementedError:
        pass
    return False


def _make_field_ref_frag(field_name: str, type_name: str, type_cls) -> VerbFragment:
    """Build a 'the <field> of the <Type>' fragment with proper semantic roles."""
    return PhraseFragment(parts=[
        Articles.THE.as_fragment(),
        RoleFragment(text=field_name, role=SemanticRole.ATTRIBUTE),
        Prepositions.OF.as_fragment(),
        Articles.THE.as_fragment(),
        RoleFragment(
            text=type_name,
            role=SemanticRole.VARIABLE,
            source_ref=SourceRef.for_type(type_cls) if isinstance(type_cls, type) else None,
        ),
    ], separator=" ")


def _copula_and_value(
    field_name: str,
    child_expr,
    ctx: VerbalizationContext,
    delegate: EQLVerbalizer,
) -> tuple[VerbFragment, VerbFragment]:
    """Return (copula_frag, value_frag) choosing singular/plural based on field name."""
    if inflect_engine.singular_noun(field_name):
        return Copulas.ARE.as_fragment(), verbalize_plural(child_expr, ctx, delegate.build)
    return Copulas.IS.as_fragment(), delegate.build(child_expr, ctx)


def _build_bindings(
    expr: InstantiatedVariable,
    ctx: VerbalizationContext,
    delegate: EQLVerbalizer,
) -> tuple[list[VerbFragment], dict[uuid.UUID, VerbFragment]]:
    """Build all binding fragments and collect overrides without registering them.

    Separating value-building from override-registration ensures no binding's value
    is rendered under a sibling binding's override.
    """
    type_name = getattr(expr._type_, "__name__", str(expr._type_))
    binding_frags: list[VerbFragment] = []
    pending_overrides: dict[uuid.UUID, VerbFragment] = {}
    for field_name, child_expr in expr._child_vars_.items():
        field_ref = _make_field_ref_frag(field_name, type_name, expr._type_)
        copula, value = _copula_and_value(field_name, child_expr, ctx, delegate)
        binding_frags.append(_phrase(field_ref, copula, value))
        pending_overrides[child_expr._id_] = field_ref
    return binding_frags, pending_overrides


def _assemble_instantiated_phrase(
    type_name: str,
    expr: InstantiatedVariable,
    binding_frags: list[VerbFragment],
    constraint_frags: list[VerbFragment],
) -> VerbFragment:
    result_parts: list[VerbFragment] = [
        _phrase(Articles.indefinite(type_name), RoleFragment.for_variable(type_name, expr))
    ]
    if binding_frags:
        joined = oxford_and(binding_frags, Conjunctions.AND.as_fragment())
        result_parts.append(PhraseFragment(
            parts=[_word(","), Keywords.WHERE.as_fragment(), joined], separator=" "
        ))
    if constraint_frags:
        joined_c = oxford_and(constraint_frags, Conjunctions.AND.as_fragment())
        result_parts.append(PhraseFragment(
            parts=[_word(","), Keywords.SUCH_THAT.as_fragment(), joined_c], separator=" "
        ))
    return PhraseFragment(parts=result_parts, separator="")


def _verbalize_instantiated_natural(
    expr: InstantiatedVariable,
    ctx: VerbalizationContext,
    delegate: EQLVerbalizer,
) -> VerbFragment:
    type_name = getattr(expr._type_, "__name__", str(expr._type_))
    if expr._id_ in ctx.seen:
        return _phrase(Articles.THE.as_fragment(), _role(ctx.seen[expr._id_], SemanticRole.VARIABLE))
    ctx.seen[expr._id_] = type_name

    ctx.push_constraint_frame()
    binding_frags, overrides = _build_bindings(expr, ctx, delegate)
    ctx.binding_overrides.update(overrides)
    deferred = ctx.pop_constraint_frame()
    constraint_frags = [delegate.build(e, ctx) for e in deferred]

    return _assemble_instantiated_phrase(type_name, expr, binding_frags, constraint_frags)
