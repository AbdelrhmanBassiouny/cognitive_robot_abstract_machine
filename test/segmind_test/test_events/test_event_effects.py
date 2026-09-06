"""
Tests for what an event says holds of the object it is about once it has happened,
stated in the world's own relation vocabulary.
"""

from __future__ import annotations

import pytest

from krrood.entity_query_language.factories import an
from segmind.datastructures.events import (
    ComesToRestEvent,
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

from ..dataset.plate_with_a_hole import (
    cube_in_the_hole,
    cube_lifted_clear_of_the_hole,
)
from ..dataset.stated_relations import says

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

ON_THE_TABLE = an(SupportedBy)(supporting=TABLE)
ON_THE_LID = an(SupportedBy)(supporting=LID)
IN_THE_SQUARE_HOLE = an(InsideRegion)(region=SQUARE_HOLE)


# %% what each kind of event says


def test_a_support_event_says_the_object_now_rests_on_what_it_names():
    """
    Support is what the event saw, so it is what holds afterwards, and it holds instead
    of whatever the object rested on before.
    """
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert says(effect.begins, ON_THE_TABLE)
    assert says(effect.ends, SUPPORTED_BY_ANYTHING)
    assert says(effect.applied_to((ON_THE_LID,), CUBE), ON_THE_TABLE)


def test_ending_every_support_ends_only_what_was_held_before_the_event():
    """
    What the event itself begins is never among what it ends, so the object rests on
    what the event names afterwards, not on nothing.
    """
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert says(effect.applied_to((ON_THE_TABLE, ON_THE_LID), CUBE), ON_THE_TABLE)


def test_a_placing_says_the_object_now_rests_on_what_it_was_placed_on():
    effect = PlacingEvent(tracked_object=CUBE, with_object=LID).effect()

    assert says(effect.applied_to((ON_THE_TABLE,), CUBE), ON_THE_LID)


def test_a_placing_and_a_support_event_state_one_effect():
    """
    Both are the object coming to rest on what the event names, so they share the one
    statement of it rather than each restating it.
    """
    assert isinstance(SupportEvent(tracked_object=CUBE), ComesToRestEvent)
    assert isinstance(PlacingEvent(tracked_object=CUBE), ComesToRestEvent)


def test_an_insertion_says_the_object_now_lies_in_the_region_it_went_into():
    """
    An insertion ends with the object in the hole's own region and off whatever it
    rested on before it went in.
    """
    effect = InsertionEvent(tracked_object=CUBE, with_object=SQUARE_HOLE).effect()

    assert says(effect.applied_to((ON_THE_LID,), CUBE), IN_THE_SQUARE_HOLE)


def test_a_pick_up_says_the_object_rests_on_nothing():
    """
    Picked up, an object is held rather than supported, whatever it rested on before.
    """
    effect = PickUpEvent(tracked_object=CUBE).effect()

    assert effect.ends == (SUPPORTED_BY_ANYTHING,)
    assert effect.applied_to((ON_THE_TABLE,), CUBE) == ()


def test_a_pick_up_is_a_reason_to_check_whether_the_object_still_lies_in_a_region():
    """
    A pick-up does not settle where the object now lies; it is the moment to look.
    """
    effect = PickUpEvent(tracked_object=CUBE).effect()

    assert effect.checks == (INSIDE_ANY_REGION,)


def test_a_pick_up_that_lifts_the_object_clear_of_a_hole_ends_its_being_in_it():
    scene = cube_lifted_clear_of_the_hole()

    held = (an(InsideRegion)(region=scene.hole),)
    after = PickUpEvent(tracked_object=scene.cube).effect().applied_to(held, scene.cube)

    assert after == ()


def test_a_pick_up_that_leaves_the_object_in_the_hole_keeps_its_being_in_it():
    """
    A gripper closing on a piece that stays sunk in its hole has not taken it out.
    """
    scene = cube_in_the_hole()

    held = (an(InsideRegion)(region=scene.hole),)
    after = PickUpEvent(tracked_object=scene.cube).effect().applied_to(held, scene.cube)

    assert after == held


def test_an_effect_that_checks_nothing_asks_nothing_of_the_object():
    """
    A support event settles what it says, so a bare body that no relation could be
    evaluated about is never asked.
    """
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect.checks == ()
    assert says(
        effect.applied_to((IN_THE_SQUARE_HOLE,), CUBE),
        IN_THE_SQUARE_HOLE,
        ON_THE_TABLE,
    )


def test_losing_support_from_what_the_object_rested_on_ends_that_support():
    effect = LossOfSupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert effect.applied_to((ON_THE_TABLE,), CUBE) == ()


def test_losing_support_from_something_else_leaves_what_it_rested_on_alone():
    """
    Coming off the table says nothing about an object resting on the lid.
    """
    effect = LossOfSupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert says(effect.applied_to((ON_THE_LID,), CUBE), ON_THE_LID)


# %% how an effect is applied


def test_an_effect_leaves_what_it_says_nothing_about_as_it_was():
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert says(
        effect.applied_to((IN_THE_SQUARE_HOLE,), CUBE),
        IN_THE_SQUARE_HOLE,
        ON_THE_TABLE,
    )


def test_an_effect_does_not_state_twice_what_already_held():
    effect = SupportEvent(tracked_object=CUBE, with_object=TABLE).effect()

    assert says(effect.applied_to((ON_THE_TABLE,), CUBE), ON_THE_TABLE)


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
