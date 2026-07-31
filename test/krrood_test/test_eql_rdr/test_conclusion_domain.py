"""
Tests for resolving an RDR conclusion attribute's allowable-value domain from its type.

Covers the enumerable (Enum / bool), open (str / arbitrary), Union, non-Optional and
unresolvable cases, plus the display / membership / example helpers.
"""

from __future__ import annotations

import enum
import unittest
from dataclasses import dataclass

from typing_extensions import Optional, Union

from krrood.entity_query_language.rdr.conclusion_domain import (
    ConclusionDomain,
    resolve_conclusion_domain,
)
from krrood.entity_query_language.rdr.exceptions import (
    ConclusionMayNotBeNone,
    ConclusionNotInDomain,
    ConclusionRequired,
    ConclusionWrongType,
)
from krrood.entity_query_language.rdr.utils import UNSET

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


class TestResolveConclusionDomain(unittest.TestCase):
    def test_optional_enum_is_enumerable_and_optional(self):
        domain = resolve_conclusion_domain(Animal, "species")
        self.assertTrue(domain.is_enumerable)
        self.assertEqual(set(domain.members), set(Species))
        self.assertEqual(domain.expected_types, (Species,))
        self.assertTrue(domain.allows_none)

    def test_required_enum_disallows_none(self):
        domain = resolve_conclusion_domain(RequiredColour, "colour")
        self.assertTrue(domain.is_enumerable)
        self.assertEqual(set(domain.members), set(Colour))
        self.assertFalse(domain.allows_none)

    def test_bool_is_enumerable(self):
        domain = resolve_conclusion_domain(Light, "on")
        self.assertTrue(domain.is_enumerable)
        self.assertEqual(set(domain.members), {True, False})
        self.assertEqual(domain.expected_types, (bool,))
        self.assertFalse(domain.allows_none)

    def test_optional_str_is_open_and_optional(self):
        domain = resolve_conclusion_domain(Doc, "label")
        self.assertFalse(domain.is_enumerable)
        self.assertEqual(domain.expected_types, (str,))
        self.assertTrue(domain.allows_none)
        self.assertEqual(domain.members, ())

    def test_required_str_is_open_non_optional(self):
        domain = resolve_conclusion_domain(Tag, "name")
        self.assertFalse(domain.is_enumerable)
        self.assertEqual(domain.expected_types, (str,))
        self.assertFalse(domain.allows_none)

    def test_union_of_real_types_is_open_with_both_types(self):
        domain = resolve_conclusion_domain(Mixed, "value")
        self.assertFalse(domain.is_enumerable)
        self.assertEqual(set(domain.expected_types), {str, int})
        self.assertFalse(domain.allows_none)

    def test_unresolvable_attribute_degrades_to_open(self):
        domain = resolve_conclusion_domain(Animal, "does_not_exist")
        self.assertFalse(domain.is_enumerable)
        self.assertEqual(domain.expected_types, ())
        self.assertFalse(domain.allows_none)


class TestConclusionDomainHelpers(unittest.TestCase):
    def test_contains_matches_enum_members(self):
        domain = resolve_conclusion_domain(Animal, "species")
        self.assertTrue(domain.contains(Species.mammal))
        self.assertFalse(domain.contains("mammal"))

    def test_display_lists_members_when_enumerable(self):
        domain = resolve_conclusion_domain(Animal, "species")
        text = domain.display()
        self.assertIn("Species.mammal", text)
        self.assertIn("Species.molusc", text)

    def test_display_shows_type_when_open(self):
        domain = resolve_conclusion_domain(Tag, "name")
        self.assertEqual(domain.display(), "str")

    def test_example_uses_first_member_when_enumerable(self):
        domain = resolve_conclusion_domain(Animal, "species")
        self.assertTrue(
            domain.example_for("conclusion").startswith("conclusion = Species.")
        )

    def test_example_shows_type_when_open(self):
        domain = resolve_conclusion_domain(Tag, "name")
        self.assertEqual(domain.example_for("conclusion"), "conclusion = <str>")

    def test_hint_lists_members_when_enumerable(self):
        domain = resolve_conclusion_domain(Animal, "species")
        self.assertEqual(domain.hint(), f"one of: {domain.display()}")

    def test_hint_shows_type_when_open(self):
        domain = resolve_conclusion_domain(Tag, "name")
        self.assertEqual(domain.hint(), "a str")


class TestConclusionDomainValidate(unittest.TestCase):
    def test_unset_accepted_only_when_allowed(self):
        domain = resolve_conclusion_domain(Animal, "species")
        self.assertIsNone(domain.validate(UNSET, allow_unset=True))
        self.assertIsInstance(
            domain.validate(UNSET, allow_unset=False), ConclusionRequired
        )

    def test_none_accepted_only_when_domain_allows_it(self):
        optional_domain = resolve_conclusion_domain(Animal, "species")
        self.assertIsNone(optional_domain.validate(None, allow_unset=False))

        required_domain = resolve_conclusion_domain(RequiredColour, "colour")
        self.assertIsInstance(
            required_domain.validate(None, allow_unset=False), ConclusionMayNotBeNone
        )

    def test_enumerable_domain_requires_membership(self):
        domain = resolve_conclusion_domain(Animal, "species")
        self.assertIsNone(domain.validate(Species.mammal, allow_unset=False))
        self.assertIsInstance(
            domain.validate("mammal", allow_unset=False), ConclusionNotInDomain
        )

    def test_open_domain_requires_expected_type(self):
        domain = resolve_conclusion_domain(Tag, "name")
        self.assertIsNone(domain.validate("x", allow_unset=False))
        self.assertIsInstance(
            domain.validate(5, allow_unset=False), ConclusionWrongType
        )
