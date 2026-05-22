"""
RuleVerbalizer — IF … THEN … rule structure rendering.

Handles Entity queries whose selected variable is an InstantiatedVariable
(inference / consequent), producing a structured block with antecedent
conditions and consequent bindings.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from krrood.entity_query_language.core.mapped_variable import Attribute, MappedVariable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.verbalization.chain_utils import build_path_parts, verbalize_plural, walk_chain
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    PhraseFragment,
    RoleFragment,
    VerbFragment,
    WordFragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.rule_analysis import (
    AggregationStatus,
    AntecedentInfo,
    ConsequentBinding,
    RuleAnalyzer,
    RuleStructure,
)
from krrood.entity_query_language.verbalization.utils import _ensure_plural, inflect_engine
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    Conjunctions,
    Copulas,
    ExistentialPhrase,
    FallbackNouns,
    GroupKeyPhrases,
    Keywords,
    Prepositions,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.query.query import Entity
    from krrood.entity_query_language.verbalization.context import VerbalizationContext


def _word(text: str) -> WordFragment:
    return WordFragment(text=text)


def _role(text, role, ref=None):
    return RoleFragment(text=text, role=role, source_ref=ref)


def _phrase(*parts, sep=" "):
    return PhraseFragment(parts=list(parts), separator=sep)


class RuleVerbalizer:
    """
    Verbalizes inference rules into ``IF … THEN …``
    :class:`~krrood.entity_query_language.verbalization.fragments.base.BlockFragment` trees.

    Handles :class:`~krrood.entity_query_language.query.query.Entity` queries whose
    selected variable is an
    :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`
    (i.e. queries that encode an inference rule).

    Delegates structural analysis to :class:`~krrood.entity_query_language.verbalization.rule_analysis.RuleAnalyzer`
    and sub-expression verbalization to the parent :class:`~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer`.

    :param delegate: The parent verbalizer used for recursive sub-expression calls.
    :type delegate: ~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer
    """

    _analyzer = RuleAnalyzer()

    def __init__(self, delegate) -> None:
        self._d = delegate

    def can_handle(self, entity: "Entity") -> bool:
        """
        Return ``True`` when *entity*'s selected variable is an
        :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`.

        :param entity: An :class:`~krrood.entity_query_language.query.query.Entity` expression.
        :type entity: ~krrood.entity_query_language.query.query.Entity
        :returns: ``True`` if this verbalizer can render *entity* as an IF/THEN rule.
        :rtype: bool
        """
        return self._analyzer.can_handle(entity)

    def verbalize(self, expr: "Entity", ctx: "VerbalizationContext") -> VerbFragment:
        """
        Build the ``IF … THEN …`` block fragment for *expr*.

        Calls :meth:`~krrood.entity_query_language.verbalization.rule_analysis.RuleAnalyzer.analyze`
        to decompose the query into antecedents and consequent bindings, then
        delegates to :meth:`_verbalize_rule_if_` and :meth:`_verbalize_rule_then_`.

        :param expr: An inference-rule Entity query.
        :type expr: ~krrood.entity_query_language.query.query.Entity
        :param ctx: Shared verbalization state.
        :type ctx: ~krrood.entity_query_language.verbalization.context.VerbalizationContext
        :returns: A two-item :class:`~krrood.entity_query_language.verbalization.fragments.base.BlockFragment`
            (IF block, THEN block).
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        structure = self._analyzer.analyze(expr)
        if_frag = self._verbalize_rule_if_(structure, ctx)
        then_frag = self._verbalize_rule_then_(structure, ctx)
        return BlockFragment(
            header=None,
            items=[
                BlockFragment(header=Keywords.IF.as_fragment(), items=if_frag),
                BlockFragment(header=Keywords.THEN.as_fragment(), items=then_frag),
            ],
        )

    # ── IF clause ─────────────────────────────────────────────────────────────

    def _verbalize_rule_if_(self, s: "RuleStructure", ctx: "VerbalizationContext") -> list[VerbFragment]:
        """
        Build the list of fragments for the IF clause.

        Secondary antecedents (those with no conditions) are registered in
        :attr:`~krrood.entity_query_language.verbalization.context.VerbalizationContext.seen`
        first so coreference works correctly inside the conditions of primary
        antecedents.

        :param s: Decomposed rule structure from :class:`~krrood.entity_query_language.verbalization.rule_analysis.RuleAnalyzer`.
        :param ctx: Shared verbalization state.
        :returns: List of fragment items for the IF block.
        :rtype: list
        """
        for ant in s.secondary_antecedents:
            self._register_antecedent_(ant, ctx)

        items: list[VerbFragment] = []
        for ant in s.primary_antecedents:
            intro = self._antecedent_intro_frag_(ant)
            self._register_antecedent_(ant, ctx)
            cond_frags = self._condition_frags_(ant.conditions, ant, ctx)
            items.append(BlockFragment(header=intro, items=cond_frags) if cond_frags else intro)

        for cond in s.unmatched_conditions:
            items.append(self._d.build(cond, ctx))

        return items or [Keywords.TRUE.as_fragment()]

    @staticmethod
    def _antecedent_intro_frag_(ant: "AntecedentInfo") -> VerbFragment:
        """
        Return the introductory phrase for an antecedent (e.g. *"there's a Robot"* or *"there are Robots"*).

        :param ant: Antecedent descriptor from :class:`~krrood.entity_query_language.verbalization.rule_analysis.RuleAnalyzer`.
        :returns: Existential-phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        if ant.aggregation_status == AggregationStatus.AGGREGATED:
            return ExistentialPhrase.THERE_ARE.build_phrase(ant.type_name)
        return ExistentialPhrase.THERE_IS_A.build_phrase(ant.type_name)

    def _register_antecedent_(self, ant: "AntecedentInfo", ctx: "VerbalizationContext") -> None:
        """
        Register *ant*'s variable (and its selected variable if it is an Entity)
        in :attr:`~krrood.entity_query_language.verbalization.context.VerbalizationContext.seen`
        so subsequent mentions produce *"the TypeName"*.

        :param ant: Antecedent to register.
        :param ctx: Shared verbalization state.
        """
        from krrood.entity_query_language.query.query import Entity as _Entity
        root = ant.root
        ctx.seen[root._id_] = ant.type_name
        if isinstance(root, _Entity):
            root.build()
            sel = root.selected_variable
            if sel is not None and hasattr(sel, "_id_"):
                ctx.seen[sel._id_] = ant.type_name

    def _condition_frags_(
        self, conditions: list, ant: "AntecedentInfo", ctx: "VerbalizationContext"
    ) -> list[VerbFragment]:
        """
        Verbalize each condition in *conditions*, preferring *"whose attr is …"*
        form when the condition is a simple attribute equality.

        :param conditions: List of EQL condition expressions.
        :param ant: Antecedent owning the conditions (used for plurality detection).
        :param ctx: Shared verbalization state.
        :returns: One fragment per condition.
        :rtype: list
        """
        return [
            self._try_whose_from_condition_(cond, ant, ctx) or self._d.build(cond, ctx)
            for cond in conditions
        ]

    def _try_whose_from_condition_(
        self, cond, ant: "AntecedentInfo", ctx: "VerbalizationContext"
    ) -> Optional[VerbFragment]:
        """
        Attempt to render *cond* as *"whose attr is value"* for simple attribute equalities.

        Returns ``None`` when the condition is not a simple ``attr == value`` form,
        signalling the caller to fall back to generic verbalization.

        :param cond: EQL condition expression.
        :param ant: Antecedent owning the condition.
        :param ctx: Shared verbalization state.
        :returns: A *"whose …"* fragment, or ``None``.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment or None
        """
        import operator
        if not isinstance(cond, Comparator) or cond.operation is not operator.eq:
            return None
        if not isinstance(cond.left, Attribute):
            return None
        attr_names = self._extract_attr_names_(cond.left)
        if not attr_names:
            return None
        aggregated = ant.aggregation_status == AggregationStatus.AGGREGATED
        attr_word = _ensure_plural(attr_names[-1]) if aggregated else attr_names[-1]
        right_frag = (
            verbalize_plural(cond.right, ctx, self._d.build)
            if aggregated
            else self._d.build(cond.right, ctx)
        )
        return _phrase(
            Keywords.WHOSE.as_fragment(),
            _role(attr_word, SemanticRole.ATTRIBUTE),
            Copulas.ARE.as_fragment() if aggregated else Copulas.IS.as_fragment(),
            right_frag,
        )

    @staticmethod
    def _extract_attr_names_(left: Attribute) -> list[str]:
        attr_names: list[str] = []
        current = left
        while isinstance(current, MappedVariable):
            if isinstance(current, Attribute):
                attr_names.append(current._attribute_name_)
            current = current._child_
        return attr_names

    # ── THEN clause ────────────────────────────────────────────────────────────

    def _verbalize_rule_then_(self, s: "RuleStructure", ctx: "VerbalizationContext") -> list[VerbFragment]:
        """
        Build the list of fragments for the THEN clause.

        Produces *"there's a TypeName"* as the header, followed by one
        *"whose field is …"* bullet per consequent binding.

        :param s: Decomposed rule structure.
        :param ctx: Shared verbalization state.
        :returns: List of fragment items for the THEN block.
        :rtype: list
        """
        type_name = s.consequent_type
        intro: VerbFragment = ExistentialPhrase.THERE_IS_A.build_phrase(type_name)
        binding_frags = [self._verbalize_binding_frag_(b, ctx) for b in s.consequent_bindings]
        if not binding_frags:
            return [intro]
        return [BlockFragment(header=intro, items=binding_frags)]

    def _verbalize_binding_frag_(
        self, binding: "ConsequentBinding", ctx: "VerbalizationContext"
    ) -> VerbFragment:
        """
        Build the *"whose field is value"* fragment for one consequent binding.

        Uses plural copula *"are"* and plural value when the field name is
        already plural (detected via ``inflect``).

        :param binding: One :class:`~krrood.entity_query_language.verbalization.rule_analysis.ConsequentBinding`.
        :param ctx: Shared verbalization state.
        :returns: A *"whose …"* phrase fragment.
        :rtype: ~krrood.entity_query_language.verbalization.fragments.base.VerbFragment
        """
        field_text = _ensure_plural(binding.field_name) if binding.is_plural_field else binding.field_name
        return _phrase(
            Keywords.WHOSE.as_fragment(),
            _role(field_text, SemanticRole.ATTRIBUTE),
            Copulas.ARE.as_fragment() if binding.is_plural_field else Copulas.IS.as_fragment(),
            self._binding_value_frag_(binding, ctx),
        )

    def _binding_value_frag_(
        self, binding: ConsequentBinding, ctx: VerbalizationContext
    ) -> VerbFragment:
        if binding.is_plural_field and binding.aggregation_status == AggregationStatus.AGGREGATED:
            return _phrase(Articles.THE.as_fragment(), verbalize_plural(binding.value_expr, ctx, self._d.build))
        if binding.is_plural_field:
            return verbalize_plural(binding.value_expr, ctx, self._d.build)
        if binding.aggregation_status == AggregationStatus.GROUP_KEY:
            return self._verbalize_group_key_value_(binding.value_expr, ctx)
        return self._d.build(binding.value_expr, ctx)

    def _verbalize_group_key_value_(self, expr, ctx: VerbalizationContext) -> VerbFragment:
        from krrood.entity_query_language.core.variable import Variable
        chain, current = walk_chain(expr)

        if not chain or not isinstance(current, Variable):
            return self._d.build(expr, ctx)

        root_type = current._type_.__name__ if getattr(current, "_type_", None) else FallbackNouns.ENTITY.text
        root_plural = inflect_engine.plural(root_type)
        ctx.seen[current._id_] = root_type

        parts = build_path_parts(chain)
        field = list(reversed(parts))[0][0] if parts else root_type
        return GroupKeyPhrases.COMMON_OF.build_phrase(field, root_plural)
