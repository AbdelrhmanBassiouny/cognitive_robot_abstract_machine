from __future__ import annotations

from typing_extensions import List

from krrood.entity_query_language.verbalization.navigation_path import PathStep
from krrood.entity_query_language.verbalization.fragments.base import (
    PhraseFragment,
    RoleFragment,
    Fragment,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Articles,
    Copulas,
    Keywords,
    Prepositions,
)


def _attribute_fragment(step: PathStep) -> RoleFragment:
    """:return: A role-tagged attribute fragment for *step*."""
    return RoleFragment(
        text=step.name,
        role=SemanticRole.ATTRIBUTE,
        source_reference=step.source_reference,
    )


def _genitive_step(step: PathStep, owner_fragment: Fragment) -> Fragment:
    """:return: *"the <attribute> of <owner>"* — one plain (noun) hop wrapping its owner."""
    return PhraseFragment(
        parts=[
            Articles.THE.as_fragment(),
            _attribute_fragment(step),
            Prepositions.OF.as_fragment(),
            owner_fragment,
        ]
    )


def _relative_clause(step: PathStep, owner_fragment: Fragment) -> Fragment:
    """:return: *"the <Type> which <owner> is <verb-phrase>"* — one relational hop wrapping its
    owner as a relative clause. Keeping the owner the verb's subject means the meaning never flips
    (*"the Person which a Book is owned by"*, not the reversed *"the Person owned by a Book"*).
    """
    relation = step.relation
    return PhraseFragment(
        parts=[
            Articles.THE.as_fragment(),
            RoleFragment.for_type(relation.value_type),
            Keywords.WHICH.as_fragment(),
            owner_fragment,
            Copulas.IS.as_fragment(),
            RoleFragment.for_attribute(
                relation.owner_class, step.name, text=relation.verb_phrase
            ),
        ]
    )


def possessive_path(parts: List[PathStep], root_fragment: Fragment) -> Fragment:
    """:return: the navigation read out from the root, hop by hop (parts innermost-first) — a plain
    hop as the genitive *"the <attribute> of <owner>"*, a relational hop as the relative clause
    *"the <Type> which <owner> is <verb-phrase>"*. With only plain hops this is the familiar
    *"the <outer> of the <inner> of <root>"*."""
    owner = root_fragment
    for step in parts:
        owner = (
            _relative_clause(step, owner)
            if step.is_relation
            else _genitive_step(step, owner)
        )
    return owner


def pronominal_path(parts: List[PathStep], pronoun: Fragment) -> Fragment:
    """:return: *"its attribute"* (single hop) or *"the attribute of its foo"* (multi-hop)."""
    if not parts:
        return pronoun
    reversed_parts = list(reversed(parts))
    last = len(reversed_parts) - 1
    fragment_parts: List[Fragment] = []
    for index, step in enumerate(reversed_parts):
        attribute_fragment = _attribute_fragment(step)
        if index == 0 and index != last:
            fragment_parts.extend([Articles.THE.as_fragment(), attribute_fragment])
        elif index == 0:  # single attribute → "its booking_date"
            fragment_parts.extend([pronoun, attribute_fragment])
        elif index == last:  # adjacent to the elided root → "of its amount_details"
            fragment_parts.extend(
                [Prepositions.OF.as_fragment(), pronoun, attribute_fragment]
            )
        else:
            fragment_parts.extend(
                [Prepositions.OF_THE.as_fragment(), attribute_fragment]
            )
    return PhraseFragment(parts=fragment_parts)
