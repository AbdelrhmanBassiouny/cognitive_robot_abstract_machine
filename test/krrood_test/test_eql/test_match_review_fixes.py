"""
Tests pinning three corners of ``match`` on collection-valued and nested attributes:

* a nested pattern's domain restricts every row, even a domain that can be read only once;
* a list of patterns on an optional list attribute that is ``None`` does not fail;
* a plain value is an element of an attribute declared as a list of a type union.

The domain classes have names no other module uses, since the class diagram resolves a
string annotation by class name.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Optional

from krrood.entity_query_language.factories import a, an
from krrood.symbol_graph.symbol_graph import Symbol

# %% Domain


@dataclass(eq=False)
class ReviewedPart(Symbol):
    name: str


@dataclass(eq=False)
class OtherReviewedPart(ReviewedPart):
    pass


@dataclass(eq=False)
class ReviewedHolder(Symbol):
    name: str
    one: Optional[ReviewedPart] = None
    sequence: Optional[List[ReviewedPart]] = None
    parts: List[OtherReviewedPart | ReviewedPart] | None = None


def names(query) -> List[str]:
    """
    :param query: A query over holders.
    :return: The names of the holders it answers, sorted.
    """
    return sorted(holder.name for holder in query.evaluate())


# %% Tests


def test_a_nested_domain_read_once_restricts_every_row():
    part = ReviewedPart("x")
    holders = [ReviewedHolder("h1", one=part), ReviewedHolder("h2", one=part)]
    query = an(ReviewedHolder)(
        one=a(ReviewedPart)().from_((candidate for candidate in [part]))
    ).from_(holders)
    assert names(query) == ["h1", "h2"]


def test_a_list_of_patterns_skips_an_absent_list():
    part = ReviewedPart("x")
    holders = [ReviewedHolder("empty"), ReviewedHolder("one", sequence=[part])]
    query = an(ReviewedHolder)(sequence=[a(ReviewedPart)(name="x")]).from_(holders)
    assert names(query) == ["one"]


def test_a_plain_value_is_an_element_of_a_list_of_a_union():
    part = ReviewedPart("x")
    holders = [
        ReviewedHolder("with", parts=[part]),
        ReviewedHolder("without", parts=[]),
    ]
    query = an(ReviewedHolder)(parts=part).from_(holders)
    assert names(query) == ["with"]
