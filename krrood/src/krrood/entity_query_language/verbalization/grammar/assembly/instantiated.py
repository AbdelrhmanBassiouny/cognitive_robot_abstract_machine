"""
InstantiatedVariable **assembler** — realise an :class:`InstantiatedPlan` into
*"a TypeName where the field of the TypeName is … such that …"*.

It owns the order-dependent **constraint-deferral dance** (push a frame → build every
binding value → register the field-reference overrides → pop the frame → render the
deferred constraints): the order matters because no binding's value may be rendered
under a sibling binding's override, and the deferred constraints reference the overrides
(verified order-dependent — it cannot be pre-planned).  The copula's number agreement is
delegated to the :class:`~krrood.entity_query_language.verbalization.grammar.choices.copula.CopulaForm`
system, so the assembler reads a feature → resolves a form → combines.

Reference: Gatt & Reiter (2009), SimpleNLG — surface realisation.
"""

from __future__ import annotations

from typing_extensions import Dict, List, Tuple

from krrood.entity_query_language.verbalization.chain_utils import verbalize_plural
from krrood.entity_query_language.verbalization.fragments.base import (
    oxford_and,
    PhraseFragment,
    RoleFragment,
    VerbFragment,
)
from krrood.entity_query_language.verbalization.fragments.factory import phrase, word
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.fragments.source_ref import SourceRef
from krrood.entity_query_language.verbalization.grammar.assembly.base import Assembler
from krrood.entity_query_language.verbalization.grammar.choices.copula import CopulaForm
from krrood.entity_query_language.verbalization.grammar.choices.features import Number
from krrood.entity_query_language.verbalization.grammar.planning.instantiated import (
    BindingPlan,
    InstantiatedPlan,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    Conjunctions,
    Keywords,
    Prepositions,
)


class InstantiatedAssembler(Assembler[InstantiatedPlan]):
    """Realise an InstantiatedVariable from its :class:`InstantiatedPlan`."""

    def assemble(self, node, plan: InstantiatedPlan) -> VerbFragment:
        seen = self.ctx.refer.seen_reference(node)
        if seen is not None:
            return seen
        self.ctx.refer.seen[node._id_] = plan.type_name

        self.ctx.scope.push_constraint_frame()
        binding_frags, overrides = self._bindings(plan, node._type_)
        self.ctx.scope.binding_overrides.update(overrides)
        deferred = self.ctx.scope.pop_constraint_frame()
        constraint_frags = [self.ctx.child(expression) for expression in deferred]

        return self._phrase(node, plan.type_name, binding_frags, constraint_frags)

    # ── bindings ───────────────────────────────────────────────────────────────

    def _bindings(
        self, plan: InstantiatedPlan, type_cls
    ) -> Tuple[List[VerbFragment], Dict]:
        """Build every binding fragment and collect overrides (registered together after)."""
        binding_frags: List[VerbFragment] = []
        overrides: Dict = {}
        for binding in plan.bindings:
            field_ref = self._field_ref(binding.field_name, plan.type_name, type_cls)
            binding_frags.append(
                phrase(field_ref, self._copula(binding), self._value(binding))
            )
            overrides[binding.value._id_] = field_ref
        return binding_frags, overrides

    def _field_ref(self, field_name: str, type_name: str, type_cls) -> VerbFragment:
        """*"the <field> of the <Type>"* with proper semantic roles + source link."""
        return PhraseFragment(
            parts=[
                Articles.THE.as_fragment(),
                RoleFragment(text=field_name, role=SemanticRole.ATTRIBUTE),
                Prepositions.OF.as_fragment(),
                Articles.THE.as_fragment(),
                RoleFragment(
                    text=type_name,
                    role=SemanticRole.VARIABLE,
                    source_ref=(
                        SourceRef.for_type(type_cls)
                        if isinstance(type_cls, type)
                        else None
                    ),
                ),
            ]
        )

    def _copula(self, binding: BindingPlan) -> VerbFragment:
        return CopulaForm.resolve(number=Number.of(binding.is_plural))

    def _value(self, binding: BindingPlan) -> VerbFragment:
        if binding.is_plural:
            return verbalize_plural(
                binding.value, self.ctx.context, self._render_plural
            )
        return self.ctx.child(binding.value)

    def _render_plural(self, expression, _context=None) -> VerbFragment:
        """``build_fn`` adapter for :func:`verbalize_plural` — recurses via the fold."""
        return self.ctx.child(expression)

    # ── phrase assembly ──────────────────────────────────────────────────────────

    def _phrase(
        self,
        node,
        type_name: str,
        binding_frags: List[VerbFragment],
        constraint_frags: List[VerbFragment],
    ) -> VerbFragment:
        result_parts: List[VerbFragment] = [
            phrase(
                Articles.indefinite(type_name),
                RoleFragment.for_variable(type_name, node),
            )
        ]
        if binding_frags:
            joined = oxford_and(binding_frags, Conjunctions.AND.as_fragment())
            result_parts.append(
                PhraseFragment(parts=[word(","), Keywords.WHERE.as_fragment(), joined])
            )
        if constraint_frags:
            joined_c = oxford_and(constraint_frags, Conjunctions.AND.as_fragment())
            result_parts.append(
                PhraseFragment(
                    parts=[word(","), Keywords.SUCH_THAT.as_fragment(), joined_c]
                )
            )
        return PhraseFragment(parts=result_parts, separator="")
