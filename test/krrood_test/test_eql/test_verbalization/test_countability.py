"""Unit tests for the curated mass-noun lexicon used to drop the article before uncountable nouns."""

from __future__ import annotations

from krrood.entity_query_language.verbalization.vocabulary.countability import (
    Countability,
    NounCountability,
)


def test_known_mass_noun_is_uncountable():
    assert NounCountability().classify("money") is Countability.UNCOUNTABLE
    assert NounCountability().is_uncountable("water")


def test_ordinary_noun_is_countable():
    assert NounCountability().classify("battery") is Countability.COUNTABLE
    assert not NounCountability().is_uncountable("department")


def test_classification_is_case_insensitive():
    assert NounCountability().is_uncountable("Money")


def test_lexicon_is_overridable_for_a_domain():
    custom = NounCountability(uncountable_nouns=frozenset({"plasma"}))
    assert custom.is_uncountable("plasma")
    # the default mass nouns are not implied when a domain supplies its own set
    assert not custom.is_uncountable("money")
