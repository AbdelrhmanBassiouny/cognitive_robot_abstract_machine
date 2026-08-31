"""
A backend can answer a statement about the world by going and looking, rather than by
selecting from a domain it was handed.

Such a backend is generative: the look is what brings the instances into existence. It
reads the statement in three parts -- what its own look can act on, what it leaves to be
checked over what came back, and what it can do neither with, which it refuses rather
than silently drops.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.entity_query_language.backends import AttributeEqualityToLiteral
from krrood.entity_query_language.exceptions import (
    BackendCannotResolveCondition,
    GenerativeBackendQueryIsNotUnderspecifiedVariable,
)
from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.verbalization.vocabulary.english import Directive

from ..dataset.backend_that_looks_at_the_world import (
    BackendThatLooksAtTheWorld,
    Sighting,
    SightingOfSomethingHeldUp,
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
CUBE_HELD_UP_OVER_THE_TABLE = SightingOfSomethingHeldUp(label="cube", place=TABLE)


@pytest.fixture
def backend() -> BackendThatLooksAtTheWorld:
    """
    A backend whose look finds three things across two places.
    """
    return BackendThatLooksAtTheWorld(
        sightings=[CUBE_ON_THE_TABLE, DISK_ON_THE_TABLE, CUBE_ON_THE_LID]
    )


# %% how a look reads


def test_a_backend_that_looks_opens_its_request_by_looking_rather_than_finding():
    assert BackendThatLooksAtTheWorld.opening_directive is Directive.LOOK_FOR


# %% reading one condition


def test_the_attribute_the_look_narrows_by_is_one_a_sighting_has():
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

    assert AttributeEqualityToLiteral.read_from(
        condition, sighting
    ) == AttributeEqualityToLiteral(
        attribute_name=BackendThatLooksAtTheWorld.PLACE_ATTRIBUTE_NAME, value=LID
    )


def test_a_comparison_that_is_not_an_equality_states_no_fixed_value():
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.place != LID))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEqualityToLiteral.read_from(condition, sighting) is None


def test_an_equality_about_another_variable_is_not_read_as_the_selections_own():
    sighting = variable(Sighting, [])
    other = variable(Sighting, [])
    query = an(entity(sighting).where(other.place == LID))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEqualityToLiteral.read_from(condition, sighting) is None


# %% what the look is told, and what is checked afterwards


def test_an_attribute_the_look_can_act_on_narrows_it(
    backend: BackendThatLooksAtTheWorld,
):
    statement = an(Sighting)(place=LID)

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place == LID
    assert results == [CUBE_ON_THE_LID]


def test_an_attribute_the_look_cannot_act_on_is_checked_over_what_came_back(
    backend: BackendThatLooksAtTheWorld,
):
    statement = an(Sighting)(label=CUBE_ON_THE_TABLE.label)

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place is None
    assert results == [CUBE_ON_THE_TABLE, CUBE_ON_THE_LID]


def test_a_narrowed_look_still_has_its_own_attribute_checked_over_the_results(
    backend: BackendThatLooksAtTheWorld,
):
    statement = an(Sighting)(place=TABLE, label=DISK_ON_THE_TABLE.label)

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place == TABLE
    assert results == [DISK_ON_THE_TABLE]


def test_a_statement_that_narrows_nothing_is_answered_from_everything_the_look_found(
    backend: BackendThatLooksAtTheWorld,
):
    results = list(an(Sighting)().evaluate(backend=backend))

    assert results == backend.sightings


def test_a_where_condition_is_checked_over_what_the_look_found(
    backend: BackendThatLooksAtTheWorld,
):
    statement = an(Sighting)(place=TABLE)
    statement = statement.where(statement.variable.label == DISK_ON_THE_TABLE.label)

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place == TABLE
    assert results == [DISK_ON_THE_TABLE]


def test_a_look_answering_with_more_kinds_than_were_asked_for_reports_only_the_kind():
    """
    A statement asks for a kind, and the kind a variable declares is not one of the
    conditions the statement itself re-checks -- so the look's own answer is narrowed to
    it here or not at all.
    """
    backend = BackendThatLooksAtTheWorld(
        sightings=[CUBE_ON_THE_TABLE, CUBE_HELD_UP_OVER_THE_TABLE]
    )

    results = list(an(SightingOfSomethingHeldUp)().evaluate(backend=backend))

    assert results == [CUBE_HELD_UP_OVER_THE_TABLE]


# %% what an unstated attribute means


def test_an_unstated_attribute_is_what_the_look_fills_in(
    backend: BackendThatLooksAtTheWorld,
):
    """
    ``...`` says the statement does not know this and the look must supply it, so it
    narrows nothing and rejects nothing.
    """
    statement = an(Sighting)(place=LID, label=...)

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place == LID
    assert results == [CUBE_ON_THE_LID]


# %% what it refuses


def test_a_condition_about_another_variable_is_refused_rather_than_dropped(
    backend: BackendThatLooksAtTheWorld,
):
    other = variable(Sighting, [CUBE_ON_THE_LID])
    statement = an(Sighting)(place=LID)
    statement = statement.where(other.place == LID)

    with pytest.raises(BackendCannotResolveCondition) as raised:
        list(statement.evaluate(backend=backend))

    assert raised.value.backend_type is BackendThatLooksAtTheWorld


def test_a_query_over_a_domain_is_refused_because_a_look_generates_its_own(
    backend: BackendThatLooksAtTheWorld,
):
    """
    A look reports what is in front of it, so there is no handed-in domain for it to
    select from -- which is what tells this backend family apart from a selective one.
    """
    sighting = variable(Sighting, [CUBE_ON_THE_LID])

    with pytest.raises(GenerativeBackendQueryIsNotUnderspecifiedVariable):
        list(an(entity(sighting)).evaluate(backend=backend))
