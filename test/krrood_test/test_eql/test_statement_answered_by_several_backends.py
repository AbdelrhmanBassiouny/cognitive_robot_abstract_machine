"""
A statement can hand over descriptions no one backend answers: the thing it is about has
to be looked for, and what nothing has stated has to be generated.

One backend chosen from several answers such a statement by answering each description
it hands over with whichever backend can, innermost first, so a plan states what it
wants without saying who is to supply it.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.backends import (
    AnsweredStatement,
    BackendChoice,
    EntityQueryLanguageGenerativeBackend,
    backend_supplies,
)
from krrood.entity_query_language.exceptions import NoBackendAnswers
from krrood.entity_query_language.factories import a, an, variable
from krrood.entity_query_language.query.match import Match

from ..dataset.action_stated_over_what_a_look_finds import (
    Grip,
    TakingHoldOfSeveralThingsFound,
    TakingHoldOfSomethingFound,
)
from ..dataset.backend_that_looks_at_the_world import (
    BackendThatLooksAtTheWorld,
    Place,
    Sighting,
    StandingOn,
)

TABLE = Place(name="table")
"""
The place two of the sightings below stand in.
"""

LID = Place(name="lid", adjoins=(TABLE.name,))
"""
The place the others stand in, one level up, alongside the table.
"""

CUBE_ON_THE_TABLE = Sighting(label="cube", place=TABLE.name)
DISK_ON_THE_TABLE = Sighting(label="disk", place=TABLE.name)
CUBE_ON_THE_LID = Sighting(label="cube", place=LID.name)
DISK_ON_THE_LID = Sighting(label="disk", place=LID.name)


def standing_on(place: Place) -> Match[Sighting]:
    """
    A description of whatever stands on a place, which only a look can answer.

    :param place: The place the thing described is asserted to stand on.
    """
    described = a(Sighting)()
    return described.where(StandingOn(described, place))


@pytest.fixture
def looking() -> BackendThatLooksAtTheWorld:
    """
    A backend whose look finds three things across two places.
    """
    return BackendThatLooksAtTheWorld(
        sightings=[CUBE_ON_THE_TABLE, DISK_ON_THE_TABLE, CUBE_ON_THE_LID]
    )


@pytest.fixture
def generating() -> EntityQueryLanguageGenerativeBackend:
    """
    A backend that enumerates what nothing has stated.
    """
    return EntityQueryLanguageGenerativeBackend()


@pytest.fixture
def choice(
    looking: BackendThatLooksAtTheWorld,
    generating: EntityQueryLanguageGenerativeBackend,
) -> BackendChoice:
    """
    A choice preferring the look to generation.
    """
    return BackendChoice(backends=[looking, generating])


# %% one statement, a backend per part of it


def test_a_statement_is_answered_by_a_backend_per_description_it_hands_over(
    choice: BackendChoice,
):
    described = standing_on(LID)
    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    assert list(choice.evaluate(statement)) == [
        TakingHoldOfSomethingFound(CUBE_ON_THE_LID, Grip.FROM_ABOVE),
        TakingHoldOfSomethingFound(CUBE_ON_THE_LID, Grip.FROM_THE_SIDE),
    ]


def test_a_statement_is_answered_once_for_every_answer_a_description_it_hands_over_has(
    choice: BackendChoice,
):
    described = standing_on(TABLE)
    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    assert list(choice.evaluate(statement)) == [
        TakingHoldOfSomethingFound(CUBE_ON_THE_TABLE, Grip.FROM_ABOVE),
        TakingHoldOfSomethingFound(CUBE_ON_THE_TABLE, Grip.FROM_THE_SIDE),
        TakingHoldOfSomethingFound(DISK_ON_THE_TABLE, Grip.FROM_ABOVE),
        TakingHoldOfSomethingFound(DISK_ON_THE_TABLE, Grip.FROM_THE_SIDE),
    ]


def test_a_description_handed_over_as_one_element_of_a_collection_is_answered_too(
    choice: BackendChoice,
):
    statement = an(TakingHoldOfSeveralThingsFound)(
        things=[CUBE_ON_THE_TABLE, standing_on(LID)], grip=Grip.FROM_ABOVE
    )

    assert list(choice.evaluate(statement)) == [
        TakingHoldOfSeveralThingsFound(
            [CUBE_ON_THE_TABLE, CUBE_ON_THE_LID], Grip.FROM_ABOVE
        )
    ]


def test_a_statement_handing_nothing_over_is_answered_by_the_backend_chosen_for_it(
    choice: BackendChoice,
):
    assert list(choice.evaluate(standing_on(LID))) == [CUBE_ON_THE_LID]


# %% which backend answered which part


def test_each_statement_is_recorded_against_the_backend_that_answered_it(
    choice: BackendChoice,
    looking: BackendThatLooksAtTheWorld,
    generating: EntityQueryLanguageGenerativeBackend,
):
    """
    Innermost first, so the record reads in the order the statement was answered.
    """
    described = standing_on(LID)
    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    list(choice.evaluate(statement))

    assert choice.answered == [
        AnsweredStatement(statement=described, backend=looking),
        AnsweredStatement(statement=statement, backend=generating),
    ]


def test_the_first_backend_that_can_answer_is_the_one_that_does(
    generating: EntityQueryLanguageGenerativeBackend,
):
    """
    Both looks can answer the description, so which of them does is the order alone.
    """
    preferred = BackendThatLooksAtTheWorld(sightings=[CUBE_ON_THE_LID])
    choice = BackendChoice(
        backends=[
            preferred,
            BackendThatLooksAtTheWorld(sightings=[DISK_ON_THE_LID]),
            generating,
        ]
    )
    described = standing_on(LID)

    assert list(choice.evaluate(described)) == [CUBE_ON_THE_LID]
    assert choice.answered == [
        AnsweredStatement(statement=described, backend=preferred)
    ]


# %% a statement none of them can answer


def test_a_statement_no_backend_can_answer_is_refused(
    generating: EntityQueryLanguageGenerativeBackend,
):
    choice = BackendChoice(backends=[generating])
    statement = an(TakingHoldOfSomethingFound)(thing=..., grip=...)

    with pytest.raises(NoBackendAnswers):
        list(choice.evaluate(statement))


# %% asking the choice for one field rather than a whole statement


def test_a_field_one_of_its_backends_can_supply(
    generating: EntityQueryLanguageGenerativeBackend,
):
    choice = BackendChoice(backends=[generating])
    action = variable(TakingHoldOfSomethingFound, domain=[])

    assert backend_supplies(choice, action.grip) is True


def test_a_field_none_of_its_backends_can_supply(
    generating: EntityQueryLanguageGenerativeBackend,
):
    choice = BackendChoice(backends=[generating])
    action = variable(TakingHoldOfSomethingFound, domain=[])

    assert backend_supplies(choice, action.thing) is False


# %% what a statement says survives its descriptions being answered


def test_a_statement_with_a_description_answered_states_the_answer_in_its_place():
    described = standing_on(LID)
    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    answered = statement.answering(described, CUBE_ON_THE_LID)

    assert answered._kwargs_ == {"thing": CUBE_ON_THE_LID, "grip": ...}


def test_a_statement_keeps_the_conditions_it_states_once_a_description_is_answered(
    choice: BackendChoice,
):
    described = standing_on(LID)
    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)
    statement = statement.where(statement.grip == Grip.FROM_ABOVE)

    assert list(choice.evaluate(statement)) == [
        TakingHoldOfSomethingFound(CUBE_ON_THE_LID, Grip.FROM_ABOVE)
    ]
