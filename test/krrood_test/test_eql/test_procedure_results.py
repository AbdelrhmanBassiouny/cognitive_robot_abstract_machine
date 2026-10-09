"""
Tests that one evaluation calls each predicate and symbolic function once per distinct
tuple of argument objects, without changing the answers.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import an, entity, variable

from ..dataset.counted_procedures import (
    CALL_LOG,
    REACH,
    IsWithinReach,
    Place,
    TravelTime,
    Visit,
)


@pytest.fixture
def visits():
    """
    Six visits to three places, two of which are within reach.
    """
    CALL_LOG.calls.clear()
    places = [Place(REACH - 1), Place(REACH), Place(REACH + 1)]
    return [Visit(place) for place in places for _ in range(2)]


# %% predicates


def test_predicate_is_called_once_per_distinct_argument(visits):
    v = variable(Visit, domain=visits)
    reachable = an(entity(v).where(IsWithinReach(v.place)))

    answers = reachable.tolist()

    assert answers == [visit for visit in visits if visit.place.distance <= REACH]
    assert len(CALL_LOG.calls) == len({id(visit.place) for visit in visits})


def test_predicate_is_called_again_in_a_new_evaluation(visits):
    v = variable(Visit, domain=visits)
    reachable = an(entity(v).where(IsWithinReach(v.place)))
    distinct_places = len({id(visit.place) for visit in visits})

    reachable.tolist()
    reachable.tolist()

    assert len(CALL_LOG.calls) == 2 * distinct_places


# %% symbolic functions


def test_symbolic_function_is_called_once_per_distinct_argument(visits):
    v = variable(Visit, domain=visits)
    short_trips = an(entity(v).where(TravelTime(v.place) < REACH))

    answers = short_trips.tolist()

    assert answers == [visit for visit in visits if visit.place.distance < REACH]
    assert len(CALL_LOG.calls) == len({id(visit.place) for visit in visits})
