"""
Inference-rule **assembler** — realise a :class:`RuleStructure` (from
:class:`~krrood.entity_query_language.verbalization.grammar.planning.inference.InferencePlanner`)
into an ``IF … THEN …`` :class:`~krrood.entity_query_language.verbalization.fragments.base.BlockFragment`.

Realisation sub-steps are methods sharing ``self.ctx`` (recursion via ``self.ctx.child``,
coreference via ``self.ctx.refer``).  Every micro form-decision (existential number, copula
number, noun number) is delegated to a :class:`~krrood.entity_query_language.verbalization.grammar.choices.base.Choice`
system, so the assembler only *reads a feature → resolves a form → combines* — no inline
``if aggregated/is_plural`` branching.  This is the realisation half of the planner/assembler
split (see :class:`~krrood.entity_query_language.verbalization.grammar.assembly.base.Assembler`).

Reference: Gatt & Reiter (2009), SimpleNLG — surface realisation.
"""

from __future__ import annotations

from typing_extensions import List

from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.query.query import Entity
from krrood.entity_query_language.verbalization import morphology
from krrood.entity_query_language.verbalization.chain_utils import (
    build_path_parts,
    verbalize_plural,
    walk_chain,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    VerbFragment,
)
from krrood.entity_query_language.verbalization.fragments.factory import phrase
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.grammar.assembly.base import Assembler
from krrood.entity_query_language.verbalization.grammar.choices.copula import CopulaForm
from krrood.entity_query_language.verbalization.grammar.choices.existential import (
    ExistentialForm,
)
from krrood.entity_query_language.verbalization.grammar.choices.features import Number
from krrood.entity_query_language.verbalization.grammar.choices.noun import NounForm
from krrood.entity_query_language.verbalization.grammar.planning.inference import (
    AggregationStatus,
    AntecedentInfo,
    ConsequentBinding,
    PlannedCondition,
    RuleStructure,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    FallbackNouns,
    GroupKeyPhrases,
    Keywords,
)


class InferenceAssembler(Assembler[RuleStructure]):
    """Realise the IF/THEN block from a :class:`RuleStructure`."""

    def assemble(self, node, plan: RuleStructure) -> VerbFragment:
        return BlockFragment(
            header=None,
            items=[
                BlockFragment(
                    header=Keywords.IF.as_fragment(), items=self._if_items(plan)
                ),
                BlockFragment(
                    header=Keywords.THEN.as_fragment(), items=self._then_items(plan)
                ),
            ],
        )

    def _render_plural(self, expression, _context=None) -> VerbFragment:
        """``build_fn`` adapter for :func:`verbalize_plural` — recurses via the fold."""
        return self.ctx.child(expression)

    @staticmethod
    def _number(antecedent: AntecedentInfo) -> Number:
        """The grammatical number of an antecedent — plural iff aggregated."""
        return Number.of(antecedent.aggregation_status == AggregationStatus.AGGREGATED)

    # ── IF clause ───────────────────────────────────────────────────────────────

    def _if_items(self, s: RuleStructure) -> List[VerbFragment]:
        for antecedent in s.secondary_antecedents:
            self._register_antecedent(antecedent)

        items: List[VerbFragment] = []
        for antecedent in s.primary_antecedents:
            intro = self._antecedent_intro(antecedent)
            self._register_antecedent(antecedent)
            cond_frags = self._condition_frags(antecedent.conditions, antecedent)
            items.append(
                BlockFragment(header=intro, items=cond_frags) if cond_frags else intro
            )

        for condition in s.unmatched_conditions:
            items.append(self.ctx.child(condition))

        return items or [Keywords.TRUE.as_fragment()]

    def _antecedent_intro(self, antecedent: AntecedentInfo) -> VerbFragment:
        return ExistentialForm.resolve(
            number=self._number(antecedent), type_name=antecedent.type_name
        )

    def _register_antecedent(self, antecedent: AntecedentInfo) -> None:
        root = antecedent.root
        self.ctx.refer.seen[root._id_] = antecedent.type_name
        if isinstance(root, Entity):
            root.build()
            sel = root.selected_variable
            if sel is not None and hasattr(sel, "_id_"):
                self.ctx.refer.seen[sel._id_] = antecedent.type_name

    def _condition_frags(
        self, conditions: List[PlannedCondition], antecedent: AntecedentInfo
    ) -> List[VerbFragment]:
        return [self._condition_frag(pc, antecedent) for pc in conditions]

    def _condition_frag(
        self, pc: PlannedCondition, antecedent: AntecedentInfo
    ) -> VerbFragment:
        """Render one condition: a *"whose <attr> is …"* modifier when foldable, else recurse."""
        if pc.whose_attr is None:
            return self.ctx.child(pc.expression)
        number = self._number(antecedent)
        return phrase(
            Keywords.WHOSE.as_fragment(),
            NounForm.resolve(
                number=number,
                name=pc.whose_attr,
                semantic_role=SemanticRole.ATTRIBUTE,
            ),
            CopulaForm.resolve(number=number),
            self._value(pc.expression.right, number),
        )

    def _value(self, expression, number: Number) -> VerbFragment:
        """Render a value expression in the given number (plural folds the chain)."""
        if number is Number.PLURAL:
            return verbalize_plural(expression, self.ctx.context, self._render_plural)
        return self.ctx.child(expression)

    # ── THEN clause ───────────────────────────────────────────────────────────

    def _then_items(self, s: RuleStructure) -> List[VerbFragment]:
        intro: VerbFragment = ExistentialForm.resolve(
            number=Number.SINGULAR, type_name=s.consequent_type
        )
        binding_frags = [self._binding_frag(b) for b in s.consequent_bindings]
        if not binding_frags:
            return [intro]
        return [BlockFragment(header=intro, items=binding_frags)]

    def _binding_frag(self, binding: ConsequentBinding) -> VerbFragment:
        number = Number.of(binding.is_plural_field)
        return phrase(
            Keywords.WHOSE.as_fragment(),
            NounForm.resolve(
                number=number,
                name=binding.field_name,
                semantic_role=SemanticRole.ATTRIBUTE,
            ),
            CopulaForm.resolve(number=number),
            self._binding_value(binding),
        )

    def _binding_value(self, binding: ConsequentBinding) -> VerbFragment:
        if (
            binding.is_plural_field
            and binding.aggregation_status == AggregationStatus.AGGREGATED
        ):
            return phrase(
                Articles.THE.as_fragment(),
                verbalize_plural(
                    binding.value_expression, self.ctx.context, self._render_plural
                ),
            )
        if binding.is_plural_field:
            return verbalize_plural(
                binding.value_expression, self.ctx.context, self._render_plural
            )
        if binding.aggregation_status == AggregationStatus.GROUP_KEY:
            return self._group_key_value(binding.value_expression)
        return self.ctx.child(binding.value_expression)

    def _group_key_value(self, expression) -> VerbFragment:
        chain, current = walk_chain(expression)
        if not chain or not isinstance(current, Variable):
            return self.ctx.child(expression)
        root_type = (
            current._type_.__name__
            if getattr(current, "_type_", None)
            else FallbackNouns.ENTITY.text
        )
        root_plural = morphology.plural(root_type)
        self.ctx.refer.seen[current._id_] = root_type
        parts = build_path_parts(chain)
        field = list(reversed(parts))[0][0] if parts else root_type
        return GroupKeyPhrases.COMMON_OF.build_phrase(field, root_plural)
