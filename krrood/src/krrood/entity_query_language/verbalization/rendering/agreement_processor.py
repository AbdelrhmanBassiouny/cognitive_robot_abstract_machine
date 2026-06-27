from __future__ import annotations

from dataclasses import replace
from typing_extensions import Optional

from krrood.entity_query_language.verbalization.fragments.base import (
    Clause,
    Fragment,
    map_structural_children,
    NounPhrase,
    PhraseFragment,
    PossessiveChain,
    RoleFragment,
)
from krrood.entity_query_language.verbalization.fragments.features import Number
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.rendering.passes import RealizationPass
from krrood.entity_query_language.verbalization.vocabulary.english import Pronouns

FINITE_ROLES = (SemanticRole.OPERATOR, SemanticRole.VERB)
"""The clause roles a finite predicate agrees through — the copula / comparison operator and a
lexical verb."""


def agree_finite(part: Fragment, number: Number) -> Fragment:
    """:return: *part* re-tagged with *number* when it is a clause's finite slot — an ``OPERATOR`` or
    ``VERB`` leaf, or a phrase led by one (the factored *"is greater than"*) — else *part* unchanged.

    Only the grammatical number is set; the morphology pass inflects it (the copula *"is"* → *"are"*,
    a lexical verb *"works"* → *"work"*). A non-copula operator (*"contains"*) is tagged too but the
    morphology pass leaves it be, so this never has to single the finite word out by its text.
    """
    if isinstance(part, RoleFragment) and part.role in FINITE_ROLES:
        return replace(part, number=number)
    leads_with_finite = (
        isinstance(part, PhraseFragment)
        and part.parts
        and isinstance(part.parts[0], RoleFragment)
        and part.parts[0].role in FINITE_ROLES
    )
    if leads_with_finite:
        return replace(
            part, parts=[replace(part.parts[0], number=number), *part.parts[1:]]
        )
    return part


class AgreementProcessor(RealizationPass):
    """Make every clause's finite verb / copula agree in number with its subject (SimpleNLG-style).

    A clause is built stating its predicate in the affirmative singular; this pass — run after
    coreference (so the subject is finalised) and before morphology (which inflects) — copies a
    PLURAL subject's number onto the clause's finite slot(s), turning *"all elements is close"* into
    *"all elements are close"*. The number DECISION stays upstream (the subject noun's number is set
    when the clause is built); this pass derives only the AGREEMENT, so a finite slot is never tagged
    plural at build time.

    A singular subject, a subject with no number, or a possessive-chain subject — agreed by the
    coreference pass, which alone holds the discourse number for *"their batteries are …"* — leaves
    the clause's finite slot untouched.

    >>> from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    ...     All, clause, Copula, Adjective, Noun)
    >>> from krrood.entity_query_language.verbalization.rendering.realization import realize_subtree
    >>> realize_subtree(clause(All(), Noun("element"), Copula(), Adjective("close")))
    'all elements are close'
    """

    def process(self, fragment: Fragment) -> Fragment:
        """:return: *fragment* with every clause's finite slot agreed to its subject's number."""
        return self._walk(fragment)

    def _walk(self, fragment: Fragment) -> Fragment:
        if isinstance(fragment, Clause):
            return self._agree_clause(fragment)
        rebuilt = map_structural_children(fragment, self._walk)
        return rebuilt if rebuilt is not None else fragment

    def _agree_clause(self, clause: Clause) -> Fragment:
        number = self._subject_number(clause)
        rebuilt = replace(clause, parts=[self._walk(part) for part in clause.parts])
        if number is not Number.PLURAL:
            return rebuilt
        return replace(
            rebuilt, parts=[agree_finite(part, number) for part in rebuilt.parts]
        )

    @staticmethod
    def _subject_number(clause: Clause) -> Optional[Number]:
        """:return: the grammatical number of the clause's subject — the first subject-bearing
        constituent: a noun phrase (reading its own number, so a leading quantifier word such as
        *"all"* is skipped), or a nominative pronoun (*"they"* → plural, *"it"* → singular). Returns
        ``None`` when the subject is a possessive chain (the coreference pass agrees that case) or no
        subject-bearing constituent is present.
        """
        for part in clause.parts:
            if isinstance(part, NounPhrase):
                return part.number
            if isinstance(part, PossessiveChain):
                return None
            if isinstance(part, RoleFragment) and part.role is SemanticRole.VARIABLE:
                if part.text == Pronouns.THEY.text:
                    return Number.PLURAL
                if part.text == Pronouns.IT.text:
                    return Number.SINGULAR
        return None
