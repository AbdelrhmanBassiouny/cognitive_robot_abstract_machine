"""
Tests for resolving an RDR conclusion attribute's allowable-value domain from its type.

Covers the enumerable (Enum / bool), open (str / arbitrary), Union, non-Optional and
unresolvable cases, plus the display / membership / example helpers.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


from krrood.entity_query_language.rdr.conclusion_domain import (
    resolve_conclusion_domain,
)

from .animal import Animal, Species


class Colour(enum.Enum):
    """
    An enumerable conclusion type with two members.
    """

    red = 1
    green = 2


@dataclass(kw_only=True)
class Light:
    """
    A conclusion owner with a plain boolean attribute.
    """

    on: bool = False
    """
    Whether the light is on.
    """


@dataclass(kw_only=True)
class Doc:
    """
    A conclusion owner with an optional string attribute.
    """

    label: str | None = None
    """
    A free-text label, ``None`` by default.
    """


@dataclass(kw_only=True)
class Tag:
    """
    A conclusion owner with a required string attribute.
    """

    name: str = ""
    """
    The text of the tag.
    """


@dataclass(kw_only=True)
class RequiredColour:
    """
    A conclusion owner with a non-optional enum attribute.
    """

    colour: Colour = Colour.red
    """
    The colour, red by default.
    """


@dataclass(kw_only=True)
class Mixed:
    """
    A conclusion owner whose attribute is a union of two real types.
    """

    value: str | int = ""
    """
    A string or an integer.
    """


class TestResolveConclusionDomain:
    """
    Resolving an attribute's declared type into a :class:`ConclusionDomain`.
    """

    def test_optional_enum_is_enumerable_and_optional(self):
        """
        An optional enum resolves to its members and allows ``None``.
        """
        domain = resolve_conclusion_domain(Animal, "species")
        assert domain.is_enumerable
        assert set(domain.members) == set(Species)
        assert domain.expected_types == (Species,)
        assert domain.allows_none

    def test_required_enum_disallows_none(self):
        """
        A non-optional enum resolves to its members and disallows ``None``.
        """
        domain = resolve_conclusion_domain(RequiredColour, "colour")
        assert domain.is_enumerable
        assert set(domain.members) == set(Colour)
        assert not (domain.allows_none)

    def test_bool_is_enumerable(self):
        """
        A ``bool`` resolves to the members ``True`` and ``False``.
        """
        domain = resolve_conclusion_domain(Light, "on")
        assert domain.is_enumerable
        assert set(domain.members) == {True, False}
        assert domain.expected_types == (bool,)
        assert not (domain.allows_none)

    def test_optional_str_is_open_and_optional(self):
        """
        An optional ``str`` is open, type-checked as ``str``, and allows ``None``.
        """
        domain = resolve_conclusion_domain(Doc, "label")
        assert not (domain.is_enumerable)
        assert domain.expected_types == (str,)
        assert domain.allows_none
        assert domain.members == ()

    def test_required_str_is_open_non_optional(self):
        """
        A non-optional ``str`` is open and disallows ``None``.
        """
        domain = resolve_conclusion_domain(Tag, "name")
        assert not (domain.is_enumerable)
        assert domain.expected_types == (str,)
        assert not (domain.allows_none)

    def test_union_of_real_types_is_open_with_both_types(self):
        """
        A union of real types is open and accepts each of its types.
        """
        domain = resolve_conclusion_domain(Mixed, "value")
        assert not (domain.is_enumerable)
        assert set(domain.expected_types) == {str, int}
        assert not (domain.allows_none)

    def test_unresolvable_attribute_degrades_to_open(self):
        """
        An attribute that cannot be resolved degrades to an open domain with no expected
        type.
        """
        domain = resolve_conclusion_domain(Animal, "does_not_exist")
        assert not (domain.is_enumerable)
        assert domain.expected_types == ()
        assert not (domain.allows_none)


class TestConclusionDomainHelpers:
    """
    The helpers a :class:`ConclusionDomain` offers its consumers.
    """

    def test_contains_matches_enum_members(self):
        """
        An enum domain contains its members and not their names.
        """
        domain = resolve_conclusion_domain(Animal, "species")
        assert domain.contains(value=Species.mammal)
        assert not (domain.contains(value="mammal"))

    def test_display_lists_members_when_enumerable(self):
        """
        An enumerable domain is displayed as its members.
        """
        domain = resolve_conclusion_domain(Animal, "species")
        text = domain.display()
        assert "Species.mammal" in text
        assert "Species.molusc" in text

    def test_display_shows_type_when_open(self):
        """
        An open domain is displayed as its type.
        """
        domain = resolve_conclusion_domain(Tag, "name")
        assert domain.display() == "str"

    def test_example_uses_first_member_when_enumerable(self):
        """
        The example answer of an enumerable domain assigns its first member.
        """
        domain = resolve_conclusion_domain(Animal, "species")
        assert domain.example_for(name="conclusion").startswith("conclusion = Species.")

    def test_example_shows_type_when_open(self):
        """
        The example answer of an open domain is a placeholder for its type.
        """
        domain = resolve_conclusion_domain(Tag, "name")
        assert domain.example_for(name="conclusion") == "conclusion = <str>"
