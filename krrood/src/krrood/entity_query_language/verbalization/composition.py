"""
Verbalization shapes for plan compositions -- how a control structure reads as a sentence.

A composition (sequential / parallel / try) joins its children's fragments with a fixed shape: *"A, then
B"*, *"A, while simultaneously B-ing"*, *"try A, otherwise B"*, *"try A, B, or C simultaneously"*. These
shapes are pure fragment operations over already-realized child fragments, factored out of any one act so
the framework that owns plan execution (coraplex) can verbalize its plan nodes through the very same
engine -- no second verbalizer, no string glue.
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
    Conjunctions,
    PlanConnectives,
)
from krrood.entity_query_language.verbalization.vocabulary.words import VocabEnum


def sequential_shape(children: List[VerbalizationFragment]) -> VerbalizationFragment:
    """:return: the children as a temporal sequence -- *"A, then B, then C"*."""
    return _interleave(children, PlanConnectives.THEN)


def parallel_shape(children: List[VerbalizationFragment]) -> VerbalizationFragment:
    """:return: the children as concurrent acts -- the first as the main clause, the rest as *"while
    simultaneously …-ing"* clauses (*"navigate to X, while simultaneously monitoring whether …"*)."""
    head, *rest = children
    if not rest:
        return head
    concurrent = oxford_comma(
        [_as_participle(fragment) for fragment in rest],
        Conjunctions.AND.as_fragment(),
    )
    connective = WordFragment(
        text=f"{Separator.COMMA}{PlanConnectives.WHILE.text} "
        f"{PlanConnectives.SIMULTANEOUSLY.text} "
    )
    return PhraseFragment(parts=[head, connective, concurrent], separator=Separator.NONE)


def try_in_order_shape(children: List[VerbalizationFragment]) -> VerbalizationFragment:
    """:return: the children as an ordered fallback -- *"try A, otherwise B"*."""
    return _interleave(children, PlanConnectives.OTHERWISE, lead=PlanConnectives.TRY)


def try_all_shape(children: List[VerbalizationFragment]) -> VerbalizationFragment:
    """:return: the children as a concurrent disjunction -- *"try A, B, or C simultaneously"*."""
    return _coordinate(
        children,
        Conjunctions.OR,
        lead=PlanConnectives.TRY,
        tail=PlanConnectives.SIMULTANEOUSLY,
    )


def _interleave(
    children: List[VerbalizationFragment],
    connective: VocabEnum,
    lead: Optional[VocabEnum] = None,
) -> VerbalizationFragment:
    """Join the children, placing *connective* before every child after the first."""
    head, *rest = children
    parts: List[VerbalizationFragment] = []
    if lead is not None:
        parts.extend([lead.as_fragment(), WordFragment(text=Separator.SPACE)])
    parts.append(head)
    for fragment in rest:
        parts.append(WordFragment(text=f"{Separator.COMMA}{connective.text} "))
        parts.append(fragment)
    return PhraseFragment(parts=parts, separator=Separator.NONE)


def _coordinate(
    children: List[VerbalizationFragment],
    conjunction: VocabEnum,
    lead: Optional[VocabEnum] = None,
    tail: Optional[VocabEnum] = None,
) -> VerbalizationFragment:
    """Join the children as an Oxford-comma coordination, reusing the And/Or coordination."""
    joined = oxford_comma(children, conjunction.as_fragment())
    parts: List[VerbalizationFragment] = []
    if lead is not None:
        parts.append(lead.as_fragment())
    parts.append(joined)
    if tail is not None:
        parts.append(tail.as_fragment())
    return PhraseFragment(parts=parts, separator=Separator.SPACE)


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
