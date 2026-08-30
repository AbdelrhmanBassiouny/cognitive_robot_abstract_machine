"""
A selective backend can answer a query by fetching the domain itself instead of
selecting from one the query was given.

Such a backend reads the query's conditions in three parts: those its own search can act
on, those it leaves for the query to apply over what came back, and those it can do
neither with, which it refuses rather than silently drops.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.entity_query_language.backends import AttributeEquality
from krrood.entity_query_language.exceptions import BackendCannotResolveCondition
from krrood.entity_query_language.factories import an, entity, variable

from ..dataset.backend_that_looks_at_the_world import (
    BackendThatLooksAtTheWorld,
    Sighting,
)

TABLE = "table"
"""
The place most of the sightings below stand in.
"""

LID = "lid"
"""
The place one of them stands in, one level up.
"""

CUBE_ON_THE_TABLE = Sighting(label="cube", place=TABLE)
DISK_ON_THE_TABLE = Sighting(label="disk", place=TABLE)
CUBE_ON_THE_LID = Sighting(label="cube", place=LID)


@pytest.fixture
def backend() -> BackendThatLooksAtTheWorld:
    """
    A backend whose look finds three things across two places.
    """
    return BackendThatLooksAtTheWorld(
        sightings=[CUBE_ON_THE_TABLE, DISK_ON_THE_TABLE, CUBE_ON_THE_LID]
    )


# %% reading one condition


def test_the_attribute_the_search_narrows_by_is_one_a_sighting_has():
    """
    The backend names the attribute it narrows by, and a rename of that field would
    otherwise leave the name behind without anything failing.
    """
    assert BackendThatLooksAtTheWorld.PLACE_ATTRIBUTE_NAME in {
        field.name for field in fields(Sighting)
    }


def test_an_equality_against_a_fixed_value_is_read_off_the_condition():
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.place == LID))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEquality.read_from(condition, sighting) == AttributeEquality(
        attribute_name=BackendThatLooksAtTheWorld.PLACE_ATTRIBUTE_NAME, value=LID
    )


def test_a_comparison_that_is_not_an_equality_states_no_fixed_value():
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.place != LID))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEquality.read_from(condition, sighting) is None


def test_an_equality_about_another_variable_is_not_read_as_the_selections_own():
    sighting = variable(Sighting, [])
    other = variable(Sighting, [])
    query = an(entity(sighting).where(other.place == LID))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEquality.read_from(condition, sighting) is None


# %% what the search is told, and what is applied afterwards


def test_a_condition_the_search_can_act_on_narrows_the_look(
    backend: BackendThatLooksAtTheWorld,
):
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.place == LID))

    results = list(query.evaluate(backend=backend))

    assert backend.searched_place == LID
    assert results == [CUBE_ON_THE_LID]


def test_a_condition_the_search_cannot_act_on_is_applied_to_what_came_back(
    backend: BackendThatLooksAtTheWorld,
):
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.label == CUBE_ON_THE_TABLE.label))

    results = list(query.evaluate(backend=backend))

    assert backend.searched_place is None
    assert results == [CUBE_ON_THE_TABLE, CUBE_ON_THE_LID]


def test_a_narrowed_search_still_has_its_own_condition_applied_to_the_results(
    backend: BackendThatLooksAtTheWorld,
):
    sighting = variable(Sighting, [])
    query = an(
        entity(sighting).where(
            sighting.place == TABLE, sighting.label == DISK_ON_THE_TABLE.label
        )
    )

    results = list(query.evaluate(backend=backend))

    assert backend.searched_place == TABLE
    assert results == [DISK_ON_THE_TABLE]


def test_a_query_with_no_conditions_is_answered_from_everything_the_look_found(
    backend: BackendThatLooksAtTheWorld,
):
    sighting = variable(Sighting, [])

    results = list(an(entity(sighting)).evaluate(backend=backend))

    assert results == backend.sightings


def test_a_condition_about_another_variable_is_refused_rather_than_dropped(
    backend: BackendThatLooksAtTheWorld,
):
    sighting = variable(Sighting, [])
    other = variable(Sighting, [CUBE_ON_THE_LID])
    query = an(entity(sighting).where(other.place == LID))

    with pytest.raises(BackendCannotResolveCondition) as raised:
        list(query.evaluate(backend=backend))

    assert raised.value.backend_type is BackendThatLooksAtTheWorld
