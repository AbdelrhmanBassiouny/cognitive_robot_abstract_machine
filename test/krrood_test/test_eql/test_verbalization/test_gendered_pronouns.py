"""Grammatical-gender pronouns: a domain class marked Masculine/Feminine reads he/his, she/her
(and who/whom in a relative clause); an unmarked class keeps the default it/its (which)."""

from __future__ import annotations

import pytest

import krrood.entity_query_language.factories as eql
from krrood.entity_query_language.verbalization.example_domain import (
    Knight,
    Mission,
    Queen,
    Robot,
)
from krrood.entity_query_language.verbalization.grammatical_gender import (
    AmbiguousGrammaticalGenderError,
    Feminine,
    GrammaticalGender,
    Masculine,
    grammatical_gender,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression


def test_resolver_reads_each_marker():
    """The resolver maps each marker to its gender."""
    assert grammatical_gender(Knight) is GrammaticalGender.MASCULINE
    assert grammatical_gender(Queen) is GrammaticalGender.FEMININE


def test_unmarked_or_non_type_is_neuter():
    """An unmarked class, a primitive, and a non-type all resolve to neuter."""
    assert grammatical_gender(Robot) is GrammaticalGender.NEUTER
    assert grammatical_gender(int) is GrammaticalGender.NEUTER
    assert grammatical_gender("not a type") is GrammaticalGender.NEUTER


def test_conflicting_markers_raise():
    """A class inheriting both markers is ambiguous, not silently resolved by MRO."""

    class Contradiction(Masculine, Feminine):
        pass

    with pytest.raises(AmbiguousGrammaticalGenderError):
        grammatical_gender(Contradiction)


def test_gender_is_inherited():
    """A subclass of a gendered class keeps that gender."""

    class SeniorKnight(Knight):
        pass

    assert grammatical_gender(SeniorKnight) is GrammaticalGender.MASCULINE


def test_masculine_possessive_reads_his():
    """A masculine subject pronominalises its possessive chains to *his*."""
    knight = eql.variable(Knight, [])
    assert (
        verbalize_expression(
            eql.an(eql.entity(knight).where(knight.rank > knight.starting_rank))
        )
        == "Find a Knight such that his rank is greater than his starting_rank"
    )


def test_feminine_possessive_reads_her():
    """A feminine subject pronominalises its possessive chains to *her*."""
    queen = eql.variable(Queen, [])
    assert (
        verbalize_expression(
            eql.an(eql.entity(queen).where(queen.treasury > queen.starting_treasury))
        )
        == "Find a Queen such that her treasury is greater than her starting_treasury"
    )


def test_relative_clause_uses_whom_for_animate_head_and_he_for_subject():
    """An animate (feminine) related entity takes *whom*; the masculine subject is *he*."""
    knight = eql.variable(Knight, [])
    assert (
        verbalize_expression(
            eql.a(eql.entity(knight).where(knight.assigned_to.realm == "North"))
        )
        == "Find a Knight such that the realm of the Queen to whom he is assigned is 'North'"
    )


def test_plural_subject_is_gender_neutral_their():
    """English plural pronouns ignore gender — a plural masculine subject still reads *their*."""
    knight = eql.variable(Knight, [])
    assert (
        verbalize_expression(eql.an(eql.entity(knight).ordered_by(knight.rank)))
        == "Report Knights ordered by their ranks from lowest to highest"
    )


def test_neuter_referent_keeps_it_which():
    """An unmarked referent is unchanged — *the Robot to which it is assigned*."""
    mission = eql.variable(Mission, [])
    assert (
        verbalize_expression(
            eql.a(eql.entity(mission).where(mission.assigned_to.battery > 50))
        )
        == "Find a Mission such that the battery of the Robot to which it is assigned is greater than 50"
    )
