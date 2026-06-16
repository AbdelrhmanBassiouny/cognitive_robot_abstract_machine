from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum, auto

from typing_extensions import ClassVar, Union

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.verbalization.fragments.base import Fragment
from krrood.entity_query_language.verbalization.grammar.conditions.assembler import (
    ConditionAssembler,
)
from krrood.entity_query_language.verbalization.grammar.conditions.recognition import (
    references,
    single_hop_attribute,
    superlative_aggregation,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    RuleContext,
)
from krrood.entity_query_language.verbalization.grammar.framework.specificity import (
    SpecificityRule,
)
from krrood.entity_query_language.verbalization.microplanning.coordination import (
    RangeFold,
)


class Slot(Enum):
    """Where a condition's rendered form attaches in a sentence — the surface-slot taxonomy a
    caller maps to an actual position (a noun modifier vs. a standalone clause)."""

    SELECTION_MODIFIER = auto()
    """A post-nominal prepositional phrase on the selection — *"<noun> with the maximum amount"*."""
    WHOSE = auto()
    """A bare predicate gathered under a shared *"whose …, and …"* envelope on the subject noun."""
    STANDALONE = auto()
    """Not attachable to the subject noun — said as its own clause (*"such that …"* / *"where …"*)."""


@dataclass(frozen=True)
class Placement:
    """The request a :class:`ConditionForm` reads: one condition to say relative to a subject."""

    item: Union[SymbolicExpression, RangeFold]
    """The folded ``WHERE`` conjunct (a raw expression or a range fold)."""

    subject: Variable
    """The variable the condition may attach to."""


@dataclass(frozen=True)
class Placed:
    """A rendered condition together with the slot it occupies, for the caller to position."""

    slot: Slot
    """The surface slot the fragment occupies."""

    fragment: Fragment
    """The rendered condition."""


class ConditionForm(SpecificityRule):
    """
    One surface form a condition can take next to a subject noun — recognise it, render it, and
    declare its :class:`Slot`. The single, *total* registry of these forms is the one authority on
    *how a condition is said relative to a subject*: every position-aware caller (a query's subject
    restriction) asks it via :func:`place` and never picks a form itself.

    The registry is total because :class:`StandaloneForm` is the unguarded base every specific form
    refines, so :meth:`~SpecificityRule.most_applicable` always returns a form (the more-derived
    specific form when it applies, else the standalone fallback) — no ``None``, no residual special
    case. Adding a form is a new subclass; nothing else changes (open/closed).

    Reference: Dale & Reiter (1995) — referring expressions / post-nominal modification;
    production-rule selection (the most-specific guarded alternative wins).
    """

    slot: ClassVar[Slot]
    """The surface slot this form's output occupies."""

    @classmethod
    @abstractmethod
    def applies(cls, request: Placement) -> bool:
        """
        :param request: The condition and the subject it may attach to.
        :return: ``True`` when this form renders *request*.
        """

    @classmethod
    @abstractmethod
    def render(cls, request: Placement, context: RuleContext) -> Fragment:
        """
        :param request: The condition and its subject.
        :param context: The per-node context (recursion and services).
        :return: *request* rendered in this form.
        """


class StandaloneForm(ConditionForm):
    """The unguarded fallback: a condition that does not fold onto the subject noun is said as its
    own clause, via the normal recursion. Being the base every specific form refines, it makes the
    registry total — it applies to anything, and a more-specific form outranks it when one fits.
    """

    slot = Slot.STANDALONE

    @classmethod
    def applies(cls, request: Placement) -> bool:
        return True

    @classmethod
    def render(cls, request: Placement, context: RuleContext) -> Fragment:
        return context.child(request.item)


class SuperlativeForm(StandaloneForm):
    """``subject.<chain> == max/min(over all <same-type>.<same chain>)`` → the superlative selection
    modifier *"with the maximum/minimum <leaf>"*.

    >>> t1 = variable(BankTransaction, domain=None)
    >>> t2 = variable(BankTransaction, domain=None)
    >>> verbalize_expression(
    ...     the(entity(t1).where(
    ...         t1.amount_details.amount == an(entity(max(t2.amount_details.amount)))
    ...     ))
    ... )
    'Find the unique BankTransaction with the maximum amount'
    """

    slot = Slot.SELECTION_MODIFIER

    @classmethod
    def applies(cls, request: Placement) -> bool:
        return superlative_aggregation(request.item, request.subject) is not None

    @classmethod
    def render(cls, request: Placement, context: RuleContext) -> Fragment:
        return ConditionAssembler(context).superlative_modifier(
            request.item, request.subject
        )


class WhoseRangeForm(StandaloneForm):
    """A range fold on a single-hop subject attribute → *"<attribute> is between low and high"*.

    >>> employee = variable(Employee, [])
    >>> verbalize_expression(
    ...     an(entity(employee).where(and_(employee.salary > 100, employee.salary < 200)))
    ... )
    'Find an Employee whose salary is between 100, and 200'
    """

    slot = Slot.WHOSE

    @classmethod
    def applies(cls, request: Placement) -> bool:
        return (
            isinstance(request.item, RangeFold)
            and single_hop_attribute(request.item.chain_expression, request.subject)
            is not None
        )

    @classmethod
    def render(cls, request: Placement, context: RuleContext) -> Fragment:
        return ConditionAssembler(context).range_modifier(request.item, request.subject)


class WhosePredicateForm(StandaloneForm):
    """A single-hop, non-boolean subject-attribute comparator whose right side does not reference the
    subject → *"<attribute> is greater than 100"* / *"<attribute> is equal to <calc>"*.

    >>> robot = variable(Robot, [])
    >>> verbalize_expression(an(entity(robot).where(robot.battery > 50)))
    'Find a Robot whose battery is greater than 50'
    """

    slot = Slot.WHOSE

    @classmethod
    def applies(cls, request: Placement) -> bool:
        item, subject = request.item, request.subject
        if not isinstance(item, Comparator):
            return False
        attribute = single_hop_attribute(item.left, subject)
        if attribute is None or attribute._type_ is bool:
            return False
        if superlative_aggregation(item, subject) is not None:
            return False  # a superlative comparator is SuperlativeForm's
        return not references(item.right, subject)

    @classmethod
    def render(cls, request: Placement, context: RuleContext) -> Fragment:
        return ConditionAssembler(context).attribute_modifier(
            request.item, request.subject
        )


def place(request: Placement, context: RuleContext) -> Placed:
    """
    Render a condition relative to its subject and report the slot it occupies — the single entry a
    position-aware caller uses. The form is chosen by the registry (most-specific applicable; the
    standalone fallback guarantees a match), so the caller never inspects the condition's shape.

    :param request: The condition and the subject it may attach to.
    :param context: The per-node context (recursion and services).
    :return: The rendered condition tagged with its surface slot.
    """
    form = ConditionForm.most_applicable(request)
    return Placed(slot=form.slot, fragment=form.render(request, context))
