"""
A statement handed to a symbolic operation in place of the thing it describes.

A match stands for the thing it looks for, so writing the match itself where an operand
is expected says the same as writing the variable it describes, and the operation is
built symbolically rather than computed over the match object.
"""

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.core.variable import InstantiatedVariable
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.predicate import symbolic_function

from ..dataset.backend_that_looks_at_the_world import Place, Sighting, StandingOn

TABLE = Place(name="table")
"""
The place the sightings below stand in.
"""

LID = Place(name="lid", adjoins=(TABLE.name,))
"""
The place the one sighting that is not on the table stands in.
"""

CUBE_ON_THE_TABLE = Sighting(label="cube", place=TABLE.name)
CUBE_ON_THE_LID = Sighting(label="cube", place=LID.name)


@pytest.fixture
def sightings() -> list[Sighting]:
    """
    One sighting in each of the two places, so a statement about a place tells them
    apart.
    """
    return [CUBE_ON_THE_TABLE, CUBE_ON_THE_LID]


# %% a relation given the match itself


def test_a_relation_given_a_match_is_stated_about_the_variable_it_describes():
    statement = a(Sighting)

    stated = StandingOn(statement, TABLE)

    assert stated._kwargs_["thing"] is statement._variable_


def test_a_relation_given_a_match_is_built_symbolically():
    statement = a(Sighting)

    stated = StandingOn(statement, TABLE)

    assert isinstance(stated, InstantiatedVariable)


def test_a_statement_narrowed_by_a_relation_given_the_match_keeps_only_what_it_asserts(
    sightings: list[Sighting],
):
    statement = a(Sighting).from_(sightings)

    narrowed = statement.where(StandingOn(statement, LID))

    assert narrowed.tolist() == [CUBE_ON_THE_LID]


# %% a function given the match itself


def test_a_symbolic_function_given_a_match_is_stated_about_the_variable_it_describes():
    @symbolic_function
    def place_of(sighting: Sighting) -> str:
        return sighting.place

    statement = a(Sighting)

    called = place_of(statement)

    assert called._kwargs_["sighting"] is statement._variable_


def test_a_statement_narrowed_by_a_function_given_the_match_keeps_only_what_it_computes(
    sightings: list[Sighting],
):
    @symbolic_function
    def place_of(sighting: Sighting) -> str:
        return sighting.place

    statement = a(Sighting).from_(sightings)

    narrowed = statement.where(place_of(statement) == LID.name)

    assert narrowed.tolist() == [CUBE_ON_THE_LID]


# %% a match nested in another match's pattern is unaffected


def test_a_match_given_as_a_pattern_value_still_describes_its_own_pattern():
    @dataclass(unsafe_hash=True)
    class Shelf:
        place: Place

    described = a(Shelf)(place=a(Place)(name=LID.name))

    assert described._kwargs_["place"]._type_ is Place
