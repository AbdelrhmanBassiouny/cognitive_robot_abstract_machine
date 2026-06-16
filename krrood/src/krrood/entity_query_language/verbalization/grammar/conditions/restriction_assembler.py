from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import List, Optional

from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.verbalization.fragments.base import (
    oxford_comma,
    PhraseFragment,
    Fragment,
)
from krrood.entity_query_language.verbalization.grammar.conditions.forms import (
    Placed,
    Placement,
    Slot,
    place,
)
from krrood.entity_query_language.verbalization.grammar.framework.phrase_rule import (
    RuleContext,
)
from krrood.entity_query_language.verbalization.grammar.query.planner import (
    RestrictionPlan,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Conjunctions,
    Keywords,
)


@dataclass(frozen=True)
class RestrictionFragments:
    """The rendered pieces of a subject restriction, for the caller to place.

    Only two pieces, because they go to two different sentence positions: the *modifiers* attach to
    the selection noun, the *residual* becomes a separate clause. The finer superlative-vs-appositive
    split is internal — callers always place those together — so it is not exposed."""

    modifiers: List[Fragment] = field(default_factory=list)
    """The noun-attaching modifiers, in order — superlative selection phrases (*"with the maximum
    amount"*) then the appositive *"whose <grouped>"* — placed right after the selection noun."""

    residual: Optional[Fragment] = None
    """The residual condition for a separate *"such that …"* / *"where …"* clause; the caller picks
    the keyword and position. ``None`` when the WHERE folds entirely into modifiers."""


@dataclass
class RestrictionAssembler:
    """
    Render a subject's WHERE partition into its surface pieces: superlative selection modifiers
    (*"with the maximum <leaf>"*), the appositive *"whose <grouped>"* modifier, and the residual
    *"such that …"* / *"where …"* condition.

    Each folded conjunct is placed by the shared :func:`~...conditions.forms.place` — the one
    authority on a condition's surface form and slot — so this assembler only buckets the results
    by slot into the two output pieces. A restriction yields several pieces, not a single fragment,
    so it is realisation-only but not an ``Assembler`` subclass.

    Reference: Reiter & Dale (2000) — content structuring (the WHERE partition is the plan).
    """

    context: RuleContext
    """The per-node context (recursion entry and microplanning services)."""

    def render(
        self, restriction: RestrictionPlan, subject: Variable
    ) -> RestrictionFragments:
        """
        Place each folded conjunct via the form registry, then bucket by slot: superlatives and the
        shared *"whose …"* envelope become noun modifiers; standalone conjuncts join into the
        residual clause.

        :param restriction: The subject's folded WHERE conjuncts.
        :param subject: The variable the restriction is on.
        :return: The rendered restriction pieces.
        """
        placed = [
            place(Placement(item=item, subject=subject), self.context)
            for item in restriction.folded
        ]
        superlatives = self._of_slot(placed, Slot.SELECTION_MODIFIER)
        grouped = self._of_slot(placed, Slot.WHOSE)
        standalone = self._of_slot(placed, Slot.STANDALONE)

        whose = (
            PhraseFragment(
                parts=[
                    Keywords.WHOSE.as_fragment(),
                    oxford_comma(grouped, Conjunctions.AND.as_fragment()),
                ]
            )
            if grouped
            else None
        )
        modifiers = superlatives + ([whose] if whose is not None else [])
        return RestrictionFragments(
            modifiers=modifiers, residual=self._join(standalone)
        )

    @staticmethod
    def _of_slot(placed: List[Placed], slot: Slot) -> List[Fragment]:
        """:return: The rendered fragments occupying *slot*, in order."""
        return [item.fragment for item in placed if item.slot is slot]

    @staticmethod
    def _join(fragments: List[Fragment]) -> Optional[Fragment]:
        """:return: The standalone conjuncts joined into one residual condition, or ``None``."""
        if not fragments:
            return None
        if len(fragments) == 1:
            return fragments[0]
        return oxford_comma(fragments, Conjunctions.AND.as_fragment())
