"""
A backend can answer a statement about the world by going and looking, rather than by
selecting from a domain it was handed.

Such a backend is generative: the look is what brings the instances into existence. It
reads the statement in three parts -- what its own look can act on, what it leaves to be
checked over what came back, and what it can do neither with, which it refuses rather
than silently drops.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.backends import (
    AttributeEqualityToLiteral,
    StatedRelation,
)
from krrood.entity_query_language.exceptions import (
    BackendCannotResolveCondition,
    GenerativeBackendQueryIsNotUnderspecifiedVariable,
)
from krrood.entity_query_language.factories import a, an, entity, variable
from krrood.entity_query_language.verbalization.vocabulary.english import Directive

from ..dataset.backend_that_looks_at_the_world import (
    BackendThatLooksAtTheWorld,
    Place,
    Sighting,
    SightingOfSomethingHeldUp,
    StandingBetween,
    StandingOn,
)

TABLE = Place(name="table")
"""
The place most of the sightings below stand in.
"""

LID = Place(name="lid")
"""
The place one of them stands in, one level up.
"""

CUBE_ON_THE_TABLE = Sighting(label="cube", place=TABLE.name)
DISK_ON_THE_TABLE = Sighting(label="disk", place=TABLE.name)
CUBE_ON_THE_LID = Sighting(label="cube", place=LID.name)
CUBE_HELD_UP_OVER_THE_TABLE = SightingOfSomethingHeldUp(label="cube", place=TABLE.name)


def looking_for_something_standing_on(place: Place):
    """
    A statement asking a look for whatever stands on a place, said as a relation.

    :param place: The place the thing sought is asserted to stand on.
    """
    statement = an(Sighting)()
    return statement.where(StandingOn(statement.variable, place))


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


def test_what_a_look_narrows_by_is_a_relation_rather_than_an_attributes_name():
    """
    The relation is a class, so it is its own source of truth and there is no name for a
    rename to leave behind.
    """
    assert BackendThatLooksAtTheWorld.narrowing_relations == (StandingOn,)


def test_an_equality_against_a_fixed_value_is_read_off_the_condition():
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.label == CUBE_ON_THE_LID.label))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEqualityToLiteral.read_from(
        condition, sighting
    ) == AttributeEqualityToLiteral(attribute_name="label", value=CUBE_ON_THE_LID.label)


def test_a_comparison_that_is_not_an_equality_states_no_fixed_value():
    sighting = variable(Sighting, [])
    query = an(entity(sighting).where(sighting.label != CUBE_ON_THE_LID.label))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEqualityToLiteral.read_from(condition, sighting) is None


def test_an_equality_about_another_variable_is_not_read_as_the_selections_own():
    sighting = variable(Sighting, [])
    other = variable(Sighting, [])
    query = an(entity(sighting).where(other.label == CUBE_ON_THE_LID.label))

    [condition] = query.build()._where_builder_.conditions

    assert AttributeEqualityToLiteral.read_from(condition, sighting) is None


# %% reading a relation


def test_a_relation_asserted_about_the_thing_sought_is_read_off_the_condition():
    statement = looking_for_something_standing_on(LID)

    request = BackendThatLooksAtTheWorld.read_request(statement)

    [stated] = request.stated_relations
    assert stated.relation_type is StandingOn
    assert stated.related_thing is LID


def test_the_thing_a_relation_relates_the_sought_thing_to_is_read_back_by_its_class():
    statement = looking_for_something_standing_on(LID)

    request = BackendThatLooksAtTheWorld.read_request(statement)

    assert request.related_by(StandingOn) is LID


def test_a_statement_asserting_no_relation_relates_the_thing_sought_to_nothing():
    request = BackendThatLooksAtTheWorld.read_request(an(Sighting)())

    assert request.stated_relations == []
    assert request.related_by(StandingOn) is None


def test_a_relation_of_more_than_two_operands_is_read_whole():
    """
    A look narrowed by a relation needs everything the statement holds it to relate the
    thing sought to, not only the one thing a triple names second.
    """
    statement = an(Sighting)()
    statement = statement.where(StandingBetween(statement.variable, TABLE, LID))

    [stated] = BackendThatLooksAtTheWorld.read_request(statement).stated_relations

    assert stated.relation_type is StandingBetween
    assert stated.stated_operands == {"one": TABLE, "other": LID}


def test_a_relation_read_off_a_statement_can_be_rebuilt_without_the_thing_sought():
    """
    What a relation allows is read from its other operands alone, so a search reads it
    before anything has been found -- which is the form this builds.
    """
    statement = an(Sighting)()
    statement = statement.where(StandingBetween(statement.variable, TABLE, LID))

    [stated] = BackendThatLooksAtTheWorld.read_request(statement).stated_relations
    constraint = stated.constraint()

    assert isinstance(constraint, StandingBetween)
    assert constraint.subject is None
    assert (constraint.one, constraint.other) == (TABLE, LID)


def test_a_relation_asserted_about_another_variable_is_not_read_as_the_sought_things():
    other = variable(Sighting, [])
    statement = an(Sighting)().where(StandingOn(other, LID))

    [condition] = statement._where_conditions_

    assert StatedRelation.read_from(condition, statement.variable) is None


# %% what the look is told, and what is checked afterwards


def test_a_relation_the_look_can_act_on_narrows_it(
    backend: BackendThatLooksAtTheWorld,
):
    results = list(looking_for_something_standing_on(LID).evaluate(backend=backend))

    assert backend.searched_place is LID
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
    statement = an(Sighting)(label=DISK_ON_THE_TABLE.label)
    statement = statement.where(StandingOn(statement.variable, TABLE))

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place is TABLE
    assert results == [DISK_ON_THE_TABLE]


def test_a_statement_that_narrows_nothing_is_answered_from_everything_the_look_found(
    backend: BackendThatLooksAtTheWorld,
):
    results = list(an(Sighting)().evaluate(backend=backend))

    assert results == backend.sightings


def test_a_where_condition_is_checked_over_what_the_look_found(
    backend: BackendThatLooksAtTheWorld,
):
    statement = an(Sighting)()
    statement = statement.where(
        StandingOn(statement.variable, TABLE),
        statement.variable.label == DISK_ON_THE_TABLE.label,
    )

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place is TABLE
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
    statement = an(Sighting)(label=...)
    statement = statement.where(StandingOn(statement.variable, LID))

    results = list(statement.evaluate(backend=backend))

    assert backend.searched_place is LID
    assert results == [CUBE_ON_THE_LID]


# %% saying which thing by describing it


def looking_for_something_standing_on_the_place_called(name: str):
    """
    A statement asking a look for whatever stands on a place it describes rather than
    hands over.

    :param name: What the world calls the place.
    """
    place = variable(Place, [TABLE, LID])
    statement = an(Sighting)()
    return statement.where(place.name == name, StandingOn(statement.variable, place))


def test_a_thing_the_statement_describes_narrows_the_look_as_one_handed_over_does(
    backend: BackendThatLooksAtTheWorld,
):
    """
    A statement can say what it wants by relating it to something it describes -- the
    place the world calls the lid -- rather than by naming that thing outright.

    Nothing
    is looked for to answer the description: it is answered out of the domain the
    statement gave it, before the look, so the relation stating it is a relation to
    something concrete.
    """
    results = list(
        looking_for_something_standing_on_the_place_called(LID.name).evaluate(
            backend=backend
        )
    )

    assert backend.searched_place == LID
    assert results == [CUBE_ON_THE_LID]


def test_a_description_no_single_thing_answers_is_refused_rather_than_guessed_at(
    backend: BackendThatLooksAtTheWorld,
):
    """
    Which place a look searches has to be settled before it is taken, so a description
    two places answer is a condition this backend cannot resolve rather than one of them
    picked.
    """
    place = variable(Place, [TABLE, LID])
    statement = an(Sighting)()
    statement = statement.where(
        place.name != "nowhere", StandingOn(statement.variable, place)
    )

    with pytest.raises(BackendCannotResolveCondition) as raised:
        list(statement.evaluate(backend=backend))

    assert raised.value.backend_type is BackendThatLooksAtTheWorld


def looking_for_something_standing_on_the_place_answering(name: str):
    """
    A statement asking a look for whatever stands on a place described by a statement of
    its own, handed to the relation where that place would stand.

    :param name: What the world calls the place.
    """
    place = a(Place)().from_([TABLE, LID])
    place.where(place.variable.name == name)
    statement = an(Sighting)()
    return statement.where(StandingOn(statement.variable, place.expression))


def test_a_thing_described_by_a_statement_of_its_own_narrows_the_look_too(
    backend: BackendThatLooksAtTheWorld,
):
    """
    A description can be written as a statement in its own right and handed to the
    relation in the place of the thing it describes, which says what stating its
    conditions beside that relation says.
    """
    results = list(
        looking_for_something_standing_on_the_place_answering(LID.name).evaluate(
            backend=backend
        )
    )

    assert backend.searched_place == LID
    assert results == [CUBE_ON_THE_LID]


def test_a_statement_of_its_own_no_single_thing_answers_is_refused_too(
    backend: BackendThatLooksAtTheWorld,
):
    """
    Where the description is written makes no difference to what has to be settled
    before a look is taken, so one two places answer is refused as the same description
    stated beside the relation is.
    """
    place = a(Place)().from_([TABLE, LID])
    place.where(place.variable.name != "nowhere")
    statement = an(Sighting)()
    statement = statement.where(StandingOn(statement.variable, place.expression))

    with pytest.raises(BackendCannotResolveCondition) as raised:
        list(statement.evaluate(backend=backend))

    assert raised.value.backend_type is BackendThatLooksAtTheWorld


# %% reading a statement as it grows


def test_a_statement_is_read_from_saying_nothing_to_saying_all_it_says():
    statement = an(Sighting)()
    statement = statement.where(
        StandingOn(statement.variable, LID),
        statement.variable.label == CUBE_ON_THE_LID.label,
    )

    said = statement.one_condition_at_a_time()

    assert [len(step._where_conditions_) for step in said] == [0, 1, 2]
    assert all(step.variable is statement.variable for step in said)


def test_a_description_is_carried_by_every_step_rather_than_being_one_of_them():
    """
    A description of another thing is what gives a condition about the thing sought its
    meaning, so it stands in every step rather than counting as a step of its own.
    """
    statement = looking_for_something_standing_on_the_place_called(LID.name)

    said = statement.one_condition_at_a_time()

    assert len(said) == 2
    assert [len(step._where_conditions_) for step in said] == [1, 2]


def test_each_condition_of_a_statement_narrows_what_a_look_answers(
    backend: BackendThatLooksAtTheWorld,
):
    statement = an(Sighting)()
    statement = statement.where(
        StandingOn(statement.variable, TABLE),
        statement.variable.label == DISK_ON_THE_TABLE.label,
    )

    answers = [
        list(step.evaluate(backend=backend))
        for step in statement.one_condition_at_a_time()
    ]

    assert answers == [
        backend.sightings,
        [CUBE_ON_THE_TABLE, DISK_ON_THE_TABLE],
        [DISK_ON_THE_TABLE],
    ]


# %% what it refuses


def test_a_condition_about_a_variable_the_world_cannot_answer_is_refused(
    backend: BackendThatLooksAtTheWorld,
):
    """
    A condition about something other than the thing sought is answerable only out of
    that thing's own domain, since a look cannot go and fetch it.

    One with nothing in it to answer is refused rather than dropped.
    """
    other = variable(Sighting, [])
    statement = an(Sighting)()
    statement = statement.where(other.label == CUBE_ON_THE_LID.label)

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
