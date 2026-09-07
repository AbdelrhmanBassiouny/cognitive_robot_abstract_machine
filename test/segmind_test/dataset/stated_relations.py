"""
Reading relations stated about one thing by what they say.

A relation stated about the thing sought is an ordinary match, so two of them are told
apart by which one they are rather than by what they state -- and an effect or a look
request states its own rather than handing back the ones it was given. Comparing what
they say is what a test about either of those actually means.
"""

from __future__ import annotations

from typing_extensions import Sequence

from krrood.entity_query_language.predicate import Relation
from krrood.entity_query_language.query.match import Match


def says(relations: Sequence[Match[Relation]], *expected: Match[Relation]) -> bool:
    """
    Whether relations say exactly what is expected, in the order they are given.

    :param relations: The relations answered.
    :param expected: What they should say.
    """
    return len(relations) == len(expected) and all(
        stated.states_the_same(other) for stated, other in zip(relations, expected)
    )
