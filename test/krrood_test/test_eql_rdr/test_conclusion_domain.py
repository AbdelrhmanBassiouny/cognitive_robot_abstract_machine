"""
Tests for resolving an RDR conclusion attribute's allowable-value domain from its type.

Covers the enumerable (Enum / bool), open (str / arbitrary), Union, non-Optional and
unresolvable cases, plus the display / membership / example helpers.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from typing_extensions import Optional, Union

from krrood.entity_query_language.rdr.conclusion_domain import (
    ConclusionDomain,
    resolve_conclusion_domain,
)

from .animal import Animal, Species


class Colour(enum.Enum):
    red = 1
    green = 2


@dataclass
class Light:
    on: bool = False


@dataclass
class Doc:
    label: Optional[str] = None


@dataclass
class Tag:
    name: str = ""


@dataclass
class RequiredColour:
    colour: Colour = Colour.red


@dataclass
class Mixed:
    value: Union[str, int] = ""


class TestResolveConclusionDomain:
    def test_optional_enum_is_enumerable_and_optional(self):
        domain = resolve_conclusion_domain(Animal, "species")
        assert domain.is_enumerable
        assert set(domain.members) == set(Species)
        assert domain.expected_types == (Species,)
        assert domain.allows_none

    def test_required_enum_disallows_none(self):
        domain = resolve_conclusion_domain(RequiredColour, "colour")
        assert domain.is_enumerable
        assert set(domain.members) == set(Colour)
        assert not (domain.allows_none)

    def test_bool_is_enumerable(self):
        domain = resolve_conclusion_domain(Light, "on")
        assert domain.is_enumerable
        assert set(domain.members) == {True, False}
        assert domain.expected_types == (bool,)
        assert not (domain.allows_none)

    def test_optional_str_is_open_and_optional(self):
        domain = resolve_conclusion_domain(Doc, "label")
        assert not (domain.is_enumerable)
        assert domain.expected_types == (str,)
        assert domain.allows_none
        assert domain.members == ()

    def test_required_str_is_open_non_optional(self):
        domain = resolve_conclusion_domain(Tag, "name")
        assert not (domain.is_enumerable)
        assert domain.expected_types == (str,)
        assert not (domain.allows_none)

    def test_union_of_real_types_is_open_with_both_types(self):
        domain = resolve_conclusion_domain(Mixed, "value")
        assert not (domain.is_enumerable)
        assert set(domain.expected_types) == {str, int}
        assert not (domain.allows_none)

    def test_unresolvable_attribute_degrades_to_open(self):
        domain = resolve_conclusion_domain(Animal, "does_not_exist")
        assert not (domain.is_enumerable)
        assert domain.expected_types == ()
        assert not (domain.allows_none)


class TestConclusionDomainHelpers:
    def test_contains_matches_enum_members(self):
        domain = resolve_conclusion_domain(Animal, "species")
        assert domain.contains(Species.mammal)
        assert not (domain.contains("mammal"))

    def test_display_lists_members_when_enumerable(self):
        domain = resolve_conclusion_domain(Animal, "species")
        text = domain.display()
        assert "Species.mammal" in text
        assert "Species.molusc" in text

    def test_display_shows_type_when_open(self):
        domain = resolve_conclusion_domain(Tag, "name")
        assert domain.display() == "str"

    def test_example_uses_first_member_when_enumerable(self):
        domain = resolve_conclusion_domain(Animal, "species")
        assert domain.example_for("conclusion").startswith("conclusion = Species.")

    def test_example_shows_type_when_open(self):
        domain = resolve_conclusion_domain(Tag, "name")
        assert domain.example_for("conclusion") == "conclusion = <str>"
