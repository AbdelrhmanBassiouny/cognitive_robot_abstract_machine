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

    *Concord* is the syntactic agreement whereby a finite verb matches its subject's number — *"the
    dogs **are**"* vs *"the dog **is**"* (Quirk, Greenbaum, Leech & Svartvik 1985, *A Comprehensive
    Grammar of the English Language*, ch. 10). A clause is built stating its predicate in the
    affirmative singular; this pass — run after coreference (so the subject is finalised) and before
    morphology (which inflects) — copies a PLURAL concord number onto the clause's finite slot(s),
    turning *"all elements is close"* into *"all elements are close"*.

    The concord number is read uniformly from one feature per subject shape: a plain noun-phrase
    subject exposes it as its own :attr:`~…NounPhrase.number`; a pronoun (*"they"*) or a
    possessive-chain population (*"their batteries"*) cannot — a plural pronoun must not itself
    inflect to *"theys"* — so the coreference pass stamps the discovered number on the clause as its
    :attr:`~…PhraseFragment.concord_number`. Either way this pass only DERIVES the agreement;
    the number DECISION stays upstream, and morphology does the inflection.

    A singular or absent subject leaves the finite slot untouched.

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
        if isinstance(fragment, PhraseFragment):
            return self._agree_phrase(fragment)
        rebuilt = map_structural_children(fragment, self._walk)
        return rebuilt if rebuilt is not None else fragment

    def _agree_phrase(self, phrase: PhraseFragment) -> Fragment:
        concord = phrase.concord_number
        if concord is None and isinstance(phrase, Clause):
            concord = self._inferred_subject_number(phrase)
        rebuilt = replace(phrase, parts=[self._walk(part) for part in phrase.parts])
        if concord is not Number.PLURAL:
            return rebuilt
        return replace(
            rebuilt, parts=[agree_finite(part, concord) for part in rebuilt.parts]
        )

    @staticmethod
    def _inferred_subject_number(clause: Clause) -> Optional[Number]:
        """:return: the concord number of an un-stamped clause — read from the first noun phrase, so a
        leading quantifier word such as *"all"* is skipped. A pronoun or possessive-chain subject is
        never un-stamped (coreference records its
        :attr:`~…PhraseFragment.concord_number`), so only a plain head noun is inferred here.
        """
        for part in clause.parts:
            if isinstance(part, NounPhrase):
                return part.number
            if isinstance(part, PossessiveChain):
                return None
        return None
