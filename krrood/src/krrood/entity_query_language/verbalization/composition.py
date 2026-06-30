"""Reusable verbalization shapes for composed plans / speech acts.

These are pure fragment combinators: they take the *already-built* child fragments and join them into
the coordinated surface of a composition (sequential, parallel, ordered-fallback, try-all). They are
free functions so both krrood's :class:`~krrood.entity_query_language.performatives.Composition` and
coraplex's executable plan nodes verbalize through the same shapes without duplicating the logic.
"""

from __future__ import annotations

from dataclasses import replace

from typing_extensions import List, Optional

from krrood.entity_query_language.verbalization import morphology
from krrood.entity_query_language.verbalization.fragments.base import (
    BlockFragment,
    PhraseFragment,
    RoleFragment,
    VerbalizationFragment,
    WordFragment,
    oxford_comma,
)
from krrood.entity_query_language.verbalization.fragments.features import Separator
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Adverbs,
    Conjunctions,
    SubordinatingConjunctions,
)
from krrood.entity_query_language.verbalization.vocabulary.words import VocabEnum


def _as_participle(fragment: VerbalizationFragment) -> VerbalizationFragment:
    """:return: *fragment* with its leading verb / directive opener as a present participle
    (*"monitor whether …"* → *"monitoring whether …"*), so a concurrent act reads as a *"while …-ing"*
    clause. A fragment with no leading verb (a bare assertion) is returned unchanged."""
    if isinstance(fragment, RoleFragment) and fragment.role in (
        SemanticRole.VERB,
        SemanticRole.KEYWORD,
    ):
        return replace(fragment, text=morphology.present_participle(fragment.text))
    if isinstance(fragment, BlockFragment) and fragment.header is not None:
        return replace(fragment, header=_as_participle(fragment.header))
    if isinstance(fragment, PhraseFragment) and fragment.parts:
        return replace(
            fragment, parts=[_as_participle(fragment.parts[0]), *fragment.parts[1:]]
        )
    return fragment


def interleave(
    child_fragments: List[VerbalizationFragment],
    connective: VocabEnum,
    lead: Optional[VerbalizationFragment] = None,
) -> VerbalizationFragment:
    """Join children, placing *connective* before every child after the first.

    :param child_fragments: The already-built fragments to join.
    :param connective: The adverb inserted between steps (e.g. ``Adverbs.THEN``).
    :param lead: An optional already-built opening fragment placed before the first child (e.g. the
        *"try"* verb).
    :return: A fragment reading *"[lead] A, <connective> B, <connective> C"*.
    """
    head, *rest = child_fragments
    parts: List[VerbalizationFragment] = []
    if lead is not None:
        parts.extend([lead, WordFragment(text=Separator.SPACE)])
    parts.append(head)
    for fragment in rest:
        parts.append(WordFragment(text=f"{Separator.COMMA}{connective.text} "))
        parts.append(fragment)
    return PhraseFragment(parts=parts, separator=Separator.NONE)


def coordinate(
    child_fragments: List[VerbalizationFragment],
    conjunction: VocabEnum,
    lead: Optional[VerbalizationFragment] = None,
    tail: Optional[VerbalizationFragment] = None,
) -> VerbalizationFragment:
    """Join children as an Oxford-comma coordination, reusing the And/Or coordination.

    :param child_fragments: The already-built fragments to join.
    :param conjunction: ``Conjunctions.AND`` (parallel) or ``Conjunctions.OR`` (try-all).
    :param lead: An optional already-built opening fragment (e.g. the *"try"* verb).
    :param tail: An optional already-built closing fragment (e.g. ``Adverbs.SIMULTANEOUSLY``).
    :return: A fragment reading *"[lead] A, B, <conjunction> C [tail]"*.
    """
    joined = oxford_comma(child_fragments, conjunction.as_fragment())
    parts: List[VerbalizationFragment] = []
    if lead is not None:
        parts.append(lead)
    parts.append(joined)
    if tail is not None:
        parts.append(tail)
    return PhraseFragment(parts=parts, separator=Separator.SPACE)


def concurrent(
    child_fragments: List[VerbalizationFragment],
) -> VerbalizationFragment:
    """Join children as concurrent clauses: the first as the main clause, the rest as *"while
    simultaneously …-ing"* participial clauses.

    :param child_fragments: The already-built fragments to join.
    :return: A fragment reading *"A, while simultaneously B-ing and C-ing"* (or just *"A"* for a single
        child).
    """
    head, *rest = child_fragments
    if not rest:
        return head
    joined = oxford_comma(
        [_as_participle(fragment) for fragment in rest],
        Conjunctions.AND.as_fragment(),
    )
    connective = WordFragment(
        text=f"{Separator.COMMA}{SubordinatingConjunctions.WHILE.text} "
        f"{Adverbs.SIMULTANEOUSLY.text} "
    )
    return PhraseFragment(parts=[head, connective, joined], separator=Separator.NONE)
