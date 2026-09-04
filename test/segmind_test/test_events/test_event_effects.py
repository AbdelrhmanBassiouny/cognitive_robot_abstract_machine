"""
Tests for what an event says holds of the object it is about once it has happened,
stated in the world's own relation vocabulary.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.backends import StatedRelation
from segmind.datastructures.events import (
    Effect,
    EventWithEffect,
    INSIDE_ANY_REGION,
    InsertionEvent,
    LossOfSupportEvent,
    PickUpEvent,
    PlacingEvent,
    SUPPORTED_BY_ANYTHING,
    SupportEvent,
    TranslationEvent,
)
from segmind.exceptions import EventNamesNoObject
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.reasoning.predicates import InsideRegion, SupportedBy
from semantic_digital_twin.world_description.world_entity import Body, Region

# %% the world these events are about

SETUP = "event_effects_test"
"""
The prefix every entity of these tests is named under.
"""


def body_named(name: str) -> Body:
    """
    A body of the world these tests state their events over.

    :param name: What the world calls it.
    """
    return Body(name=PrefixedName(name, SETUP))


CUBE = body_named("cube")
TABLE = body_named("table")
LID = body_named("lid")
SQUARE_HOLE = Region(name=PrefixedName("square_hole", SETUP))

ON_THE_TABLE = StatedRelation.of(SupportedBy, TABLE)
ON_THE_LID = StatedRelation.of(SupportedBy, LID)
IN_THE_SQUARE_HOLE = StatedRelation.of(InsideRegion, SQUARE_HOLE)


# %% what each kind of event says


def test_a_support_event_says_the_object_now_rests_on_what_it_names():
    """
    Support is what the event saw, so it is what holds afterwards, and it holds instead
    of whatever the object rested on before.
    """
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect == Effect(begins=(ON_THE_TABLE,), ends=(SUPPORTED_BY_ANYTHING,))
    assert effect.applied_to((ON_THE_LID,)) == (ON_THE_TABLE,)


def test_a_placing_says_the_object_now_rests_on_what_it_was_placed_on():
    effect = PlacingEvent(tracked_object=CUBE, with_object=LID).effect()

    assert effect.applied_to((ON_THE_TABLE,)) == (ON_THE_LID,)


def test_an_insertion_says_the_object_now_lies_in_the_region_it_went_into():
    """
    An insertion ends with the object in the hole's own region and off whatever it
    rested on before it went in.
    """
    effect = InsertionEvent(tracked_object=CUBE, with_object=SQUARE_HOLE).effect()

    assert effect.applied_to((ON_THE_LID,)) == (IN_THE_SQUARE_HOLE,)


def test_a_pick_up_says_the_object_rests_on_nothing_and_lies_in_no_region():
    """
    Picked up, an object is held rather than supported, whatever it rested on or lay in
    before.
    """
    effect = PickUpEvent(tracked_object=CUBE).effect()

    assert effect == Effect(ends=(SUPPORTED_BY_ANYTHING, INSIDE_ANY_REGION))
    assert effect.applied_to((ON_THE_TABLE, IN_THE_SQUARE_HOLE)) == ()


def test_losing_support_from_what_the_object_rested_on_ends_that_support():
    effect = LossOfSupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect.applied_to((ON_THE_TABLE,)) == ()


def test_losing_support_from_something_else_leaves_what_it_rested_on_alone():
    """
    Coming off the table says nothing about an object resting on the lid.
    """
    effect = LossOfSupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect.applied_to((ON_THE_LID,)) == (ON_THE_LID,)


# %% how an effect is applied


def test_an_effect_leaves_what_it_says_nothing_about_as_it_was():
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect.applied_to((IN_THE_SQUARE_HOLE,)) == (
        IN_THE_SQUARE_HOLE,
        ON_THE_TABLE,
    )


def test_an_effect_does_not_state_twice_what_already_held():
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect.applied_to((ON_THE_TABLE,)) == (ON_THE_TABLE,)


# %% events that state no effect


def test_a_support_event_naming_no_supporter_is_refused():
    with pytest.raises(EventNamesNoObject):
        SupportEvent(tracked_object=CUBE).effect()


def test_an_insertion_into_something_that_is_not_a_region_is_refused():
    with pytest.raises(EventNamesNoObject):
        InsertionEvent(tracked_object=CUBE, with_object=TABLE).effect()


def test_a_translation_says_nothing_about_what_holds():
    """
    That an object moved says nothing about what it came to rest against.
    """
    assert not isinstance(
        TranslationEvent(tracked_object=CUBE, with_object=TABLE), EventWithEffect
    )
