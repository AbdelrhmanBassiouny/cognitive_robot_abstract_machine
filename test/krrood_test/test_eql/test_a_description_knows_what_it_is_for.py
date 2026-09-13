"""
What a description is for is said by the statement it is handed over by, not by the
description itself: the hole described inside an insertion of a piece is the hole that
piece goes through, and nothing of that is written in the description of the hole.

So a description knows the statements it is stated inside, and what each states it as.
"""

from __future__ import annotations

from krrood.entity_query_language.factories import a, an

from ..dataset.action_stated_over_what_a_look_finds import (
    Grip,
    TakingHoldOfSeveralThingsFound,
    TakingHoldOfSomethingFound,
)
from ..dataset.backend_that_looks_at_the_world import Place, Sighting

CUBE_ON_THE_LID = Sighting(label="cube", place="lid")
"""
The thing the statements below are answered with.
"""

# %% the statement a description is handed over by


def test_a_description_knows_the_statement_that_hands_it_over():
    described = a(Sighting)(label="cube")

    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    assert described._stated_by_.statement is statement


def test_a_description_knows_the_attribute_it_is_stated_to():
    described = a(Sighting)(label="cube")

    an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    assert described._stated_by_.attribute_name == "thing"


def test_a_description_stated_as_one_element_of_a_collection_knows_it_too():
    described = a(Sighting)(label="cube")

    statement = an(TakingHoldOfSeveralThingsFound)(
        things=[CUBE_ON_THE_LID, described], grip=Grip.FROM_ABOVE
    )

    assert described._stated_by_.statement is statement
    assert described._stated_by_.attribute_name == "things"


def test_a_statement_nobody_hands_over_is_stated_by_nothing():
    assert an(TakingHoldOfSomethingFound)(thing=..., grip=...)._stated_by_ is None


# %% every statement it is stated inside


def test_a_description_is_enclosed_by_every_statement_it_is_stated_inside():
    """
    Innermost first, so what a description is for is read from the statement nearest it
    before the ones that statement is itself part of.
    """
    place = a(Place)(name="lid")
    sighting = a(Sighting)(label="cube", place=place)
    statement = an(TakingHoldOfSomethingFound)(thing=sighting, grip=...)

    assert list(place._enclosing_statements_) == [sighting, statement]


def test_a_statement_nobody_hands_over_is_enclosed_by_nothing():
    statement = an(TakingHoldOfSomethingFound)(thing=..., grip=...)

    assert list(statement._enclosing_statements_) == []


# %% what becomes of it as the statement is answered


def test_a_description_still_open_is_handed_over_by_the_statement_as_it_now_stands():
    """
    A statement with one of its slots answered is that statement still, so a description
    it has not answered yet is for what the statement now says rather than for what it
    said before.
    """
    described = a(Sighting)(label="cube")
    statement = an(TakingHoldOfSomethingFound)(thing=described, grip=...)

    answered = statement.answering("grip", Grip.FROM_ABOVE)

    assert described._stated_by_.statement is answered
    assert list(described._enclosing_statements_) == [answered]
