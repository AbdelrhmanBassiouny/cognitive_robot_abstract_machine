"""
Subject restriction systems — recognising a subject's ``WHERE`` conjunct as a
post-nominal *"whose <attr> is …"* modifier (vs. a residual *"such that …"* clause),
and resolving **which** variable a selection restricts.

Both decisions are **declarative**: small rule hierarchies that share the
:class:`~krrood.entity_query_language.verbalization.grammar.selection.SpecificityRule`
base — self-registering alternatives selected by specificity, the same primitive family
as :class:`~krrood.entity_query_language.verbalization.grammar.phrase_rule.PhraseRule`
— so there is no bespoke dispatch loop.  Matching is **pure analysis** (used by
:class:`~krrood.entity_query_language.verbalization.grammar.planning.query.QueryPlanner`);
each rule's :meth:`render` is the realisation half (used by
:class:`~krrood.entity_query_language.verbalization.grammar.assembly.query.QueryAssembler`).

Reference: Dale & Reiter (1995) — referring expressions / post-nominal modification.
"""

from __future__ import annotations

from abc import abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING
from typing_extensions import ClassVar, Optional, Type

from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.operators.aggregators import Aggregator
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.verbalization.fragments.base import Fragment
from krrood.entity_query_language.verbalization.grammar.conditions.recognition import (
    references,
    single_hop_attr,
    superlative_aggregation,
)
from krrood.entity_query_language.verbalization.grammar.conditions.verbalizer import (
    ConditionVerbalizer,
)
from krrood.entity_query_language.verbalization.grammar.phrase_rule import Ctx
from krrood.entity_query_language.verbalization.grammar.selection import SpecificityRule
from krrood.entity_query_language.verbalization.microplanning.coordination import (
    RangeFold,
)
from krrood.entity_query_language.verbalization.subquery import aggregation_source_root

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.context import VerbalizationContext


# ── restriction rules (folded conjunct → fragment + its placement) ───────────


class Placement(Enum):
    """**Where** a matched restriction's fragment attaches in the query — the single, extensible
    taxonomy of restriction surface slots.

    A rule declares its placement and the :class:`RestrictionAssembler` groups by it, so a new
    fold that targets an *existing* slot is one rule class (no other change); only a genuinely new
    syntactic slot adds an enum member (and a field on ``RestrictionFragments``).

    :cvar SELECTION_MODIFIER: A post-nominal PP on the selection — *"<noun> with the maximum amount"*.
    :cvar WHOSE_GROUP: A bare predicate gathered under one shared *"whose …, and …"* envelope.
    """

    SELECTION_MODIFIER = auto()
    WHOSE_GROUP = auto()


class RestrictionRule(SpecificityRule):
    """
    Recognise a folded conjunct as a subject restriction and render its fragment, declaring
    **where** that fragment attaches via :attr:`placement`.  A conjunct matched by no rule is
    residual and stays in a *"such that …"* clause.

    Self-registering alternative (see :class:`SpecificityRule`); ranked by ``priority``.
    """

    placement: ClassVar[Placement]
    """The slot this rule's :meth:`render` output occupies (see :class:`Placement`)."""

    @classmethod
    @abstractmethod
    def applies(cls, item, subject_variable, context: "VerbalizationContext") -> bool:
        """Return ``True`` when *item* is a restriction on *subject_variable* this rule renders."""

    @classmethod
    @abstractmethod
    def render(cls, item, subject_variable, ctx: Ctx) -> Fragment:
        """Render *item* as the fragment for its :attr:`placement` (recurses via ``ctx.child``)."""


class RangeRestrictionRule(RestrictionRule):
    """A :class:`RangeFold` on a single-hop subject attribute → *"<attr> is between lo and hi"*."""

    placement = Placement.WHOSE_GROUP

    @classmethod
    def applies(cls, item, subject_variable, context: "VerbalizationContext") -> bool:
        return (
            isinstance(item, RangeFold)
            and single_hop_attr(item.chain_expression, subject_variable) is not None
        )

    @classmethod
    def render(cls, item, subject_variable, ctx: Ctx) -> Fragment:
        return ConditionVerbalizer(ctx).range_modifier(item, subject_variable)


class AttributePredicateRestrictionRule(RestrictionRule):
    """
    A single-hop, non-boolean subject-attribute :class:`Comparator` whose RHS does not
    reference the subject → *"<attr> is greater than 100"* / *"<attr> is equal to <calc>"*.
    """

    placement = Placement.WHOSE_GROUP

    @classmethod
    def applies(cls, item, subject_variable, context: "VerbalizationContext") -> bool:
        if not isinstance(item, Comparator):
            return False
        attr = single_hop_attr(item.left, subject_variable)
        if attr is None or attr._type_ is bool:
            return False
        return not references(item.right, subject_variable)

    @classmethod
    def render(cls, item, subject_variable, ctx: Ctx) -> Fragment:
        return ConditionVerbalizer(ctx).attribute_modifier(item, subject_variable)


class SuperlativeRestrictionRule(RestrictionRule):
    """
    ``subject.<chain> == max/min(over all <same-type>.<same chain>)`` → the superlative selection
    modifier *"with the maximum/minimum <leaf>"* (see :func:`superlative_aggregation`).  Higher
    ``priority`` than :class:`AttributePredicateRestrictionRule` so a single-hop superlative folds
    to the superlative rather than *"<attr> is equal to <calc>"*.
    """

    placement = Placement.SELECTION_MODIFIER
    priority = 1

    @classmethod
    def applies(cls, item, subject_variable, context: "VerbalizationContext") -> bool:
        return superlative_aggregation(item, subject_variable) is not None

    @classmethod
    def render(cls, item, subject_variable, ctx: Ctx) -> Fragment:
        return ConditionVerbalizer(ctx).superlative_modifier(item, subject_variable)


def match_restriction(
    item, subject_variable, context: "VerbalizationContext"
) -> Optional[Type[RestrictionRule]]:
    """The most-specific applicable :class:`RestrictionRule` for *item*, or ``None`` (residual).

    Pure analysis — no fragment is built; the planner uses this to partition conjuncts.
    """
    return RestrictionRule.most_applicable(item, subject_variable, context)


# ── restriction-subject rules (which variable does the WHERE restrict?) ──────


class RestrictionSubjectRule(SpecificityRule):
    """
    Resolve **which variable** a query's selection restricts, so the selection's ``WHERE``
    can fold into a post-nominal *"whose …"* modifier on it.  A selection matched by no
    rule has no groupable subject — its ``WHERE`` stays a full *"such that …"* clause.

    Self-registering alternative (see :class:`SpecificityRule`); ranked by ``priority``.
    """

    @classmethod
    @abstractmethod
    def applies(
        cls, expression, selected_variable, context: "VerbalizationContext"
    ) -> bool:
        """Return ``True`` when this rule can name the restriction subject of *expression*."""

    @classmethod
    @abstractmethod
    def subject(cls, expression, selected_variable, context: "VerbalizationContext"):
        """Return the :class:`Variable` the ``WHERE`` restricts."""


class SelectedVariableSubjectRule(RestrictionSubjectRule):
    """The selection is a plain :class:`Variable` → it is its own subject."""

    @classmethod
    def applies(
        cls, expression, selected_variable, context: "VerbalizationContext"
    ) -> bool:
        return isinstance(selected_variable, Variable)

    @classmethod
    def subject(cls, expression, selected_variable, context: "VerbalizationContext"):
        return selected_variable


class AggregationSourceSubjectRule(RestrictionSubjectRule):
    """
    The selection aggregates over a single source variable's chain (e.g.
    ``max(t.amount_details.amount)``); the ``WHERE`` restricts that aggregated entity,
    whose noun ends the selection so a *"whose …"* modifier attaches grammatically.
    """

    @classmethod
    def applies(
        cls, expression, selected_variable, context: "VerbalizationContext"
    ) -> bool:
        return (
            isinstance(selected_variable, Aggregator)
            and aggregation_source_root(expression) is not None
        )

    @classmethod
    def subject(cls, expression, selected_variable, context: VerbalizationContext):
        return aggregation_source_root(expression)


def restriction_subject(
    expression, selected_variable, context: VerbalizationContext
) -> Optional[Variable]:
    """The variable a selection's ``WHERE`` restricts (most-specific rule wins), or ``None``."""
    chosen = RestrictionSubjectRule.most_applicable(
        expression, selected_variable, context
    )
    return (
        chosen.subject(expression, selected_variable, context)
        if chosen is not None
        else None
    )
