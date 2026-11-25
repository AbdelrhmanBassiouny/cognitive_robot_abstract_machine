"""
Tests pinning corners of ``match`` on collection-valued and nested attributes: nested
domains, absent lists of patterns, and which plain values are an element of a list of a
type union or of a tuple.

Domain class names are unique to this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Optional

import pytest

from krrood.entity_query_language.exceptions import (
    ValueFitsNeitherElementNorCollection,
)
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


@dataclass(kw_only=True, eq=False)
class ReviewedTool(Symbol):
    """
    A tool a kit holds, unrelated to :class:`ReviewedPart` but through :class:`Symbol`.
    """

    name: str
    """
    The name the tool is told apart by.
    """


@dataclass(kw_only=True, eq=False)
class ReviewedLabel(Symbol):
    """
    A symbol of neither class a kit's collections declare.
    """

    name: str
    """
    The name the label is told apart by.
    """


@dataclass(kw_only=True, eq=False)
class ReviewedKit(Symbol):
    """
    A kit whose collections declare more than one element class.
    """

    name: str
    """
    The name the kit is told apart by.
    """

    contents: List[ReviewedPart | ReviewedTool] | None = None
    """
    Parts and tools, declared as a list of a union of two unrelated classes.
    """

    pair: tuple[ReviewedPart, ReviewedTool] | None = None
    """
    One part and one tool, declared as a tuple of two different positions.
    """


def names(query) -> List[str]:
    """
    :param query: A query over holders.
    :return: The names of the holders it answers, sorted.
    """
    return sorted(holder.name for holder in query.evaluate())


# %% Tests


def test_a_nested_domain_read_once_restricts_every_row():
    """
    A nested pattern over a domain that can be read only once restricts every holder.
    """
    part = ReviewedPart("x")
    holders = [ReviewedHolder("h1", one=part), ReviewedHolder("h2", one=part)]
    query = an(ReviewedHolder)(
        one=a(ReviewedPart).from_(domain=(candidate for candidate in [part]))
    ).from_(domain=holders)
    assert names(query) == ["h1", "h2"]


def test_a_list_of_patterns_skips_an_absent_list():
    part = ReviewedPart("x")
    holders = [ReviewedHolder("empty"), ReviewedHolder("one", sequence=[part])]
    query = an(ReviewedHolder)(sequence=[a(ReviewedPart)(name="x")]).from_(
        domain=holders
    )
    assert names(query) == ["one"]


def test_a_plain_value_is_an_element_of_a_list_of_a_union():
    """
    A value of the union's base member is an element of a list of the union.
    """
    part = ReviewedPart("x")
    holders = [
        ReviewedHolder("with", parts=[part]),
        ReviewedHolder("without", parts=[]),
    ]
    query = an(ReviewedHolder)(parts=part).from_(domain=holders)
    assert names(query) == ["with"]


# %% Union and tuple element types


def test_a_plain_value_of_any_union_member_is_an_element():
    """
    A value of the second of two unrelated union members is an element, not only one of
    their common base class.
    """
    part, tool = ReviewedPart("p"), ReviewedTool(name="t")
    kits = [
        ReviewedKit(name="parts", contents=[part]),
        ReviewedKit(name="tools", contents=[tool]),
    ]
    assert names(an(ReviewedKit)(contents=tool).from_(domain=kits)) == ["tools"]


def test_a_plain_value_of_no_union_member_is_refused():
    """
    A value that shares only a base class with the union's members is refused.
    """
    kits = [ReviewedKit(name="parts", contents=[ReviewedPart("p")])]
    with pytest.raises(ValueFitsNeitherElementNorCollection):
        an(ReviewedKit)(contents=ReviewedLabel(name="l")).from_(domain=kits).tolist()


def test_a_plain_value_of_any_tuple_position_is_an_element():
    """
    A value of a tuple's second position is an element, not only one of its first.
    """
    part, tool = ReviewedPart("p"), ReviewedTool(name="t")
    kits = [
        ReviewedKit(name="with", pair=(part, tool)),
        ReviewedKit(name="other", pair=(part, ReviewedTool(name="u"))),
    ]
    assert names(an(ReviewedKit)(pair=tool).from_(domain=kits)) == ["with"]
