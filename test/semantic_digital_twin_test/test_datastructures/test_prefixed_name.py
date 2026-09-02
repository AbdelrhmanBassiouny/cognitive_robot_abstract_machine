"""
Tests for what a prefixed name is read as.
"""

from __future__ import annotations

from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from semantic_digital_twin.world_description.world_entity import Body


def test_asking_for_a_name_asks_for_the_name_of_the_thing():
    """
    A name is what a prefixed name is, so asking for it says the thing whose name it is
    rather than saying the word twice.
    """
    body = variable(Body, [])
    assert (
        verbalize_expression(body.name.name == "board_lid")
        == "the name of a Body is 'board_lid'"
    )


def test_a_namespace_is_still_said_as_the_namespace_of_a_name():
    """
    Only the name itself stands for the whole; the namespace it is told apart by names
    itself.
    """
    body = variable(Body, [])
    assert (
        verbalize_expression(body.name.prefix == "tracy")
        == "the prefix of the name of a Body is 'tracy'"
    )
