"""
Tests for the colours this twin has a word for, and for reading a measured colour as one
of them.
"""

from __future__ import annotations

import pytest
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from semantic_digital_twin.world_description.geometry import Box, Color, ColorName


@pytest.mark.parametrize("name", list(ColorName))
def test_every_named_colour_is_nearest_to_itself(name: ColorName):
    """
    A colour that is exactly one of the named ones is read as that name.
    """
    assert ColorName.nearest_to(name.color) is name


def test_a_name_hands_out_a_colour_of_its_own():
    """
    Each reading of a name is a colour of its own, so changing one cannot change what
    the name means.
    """
    first, second = ColorName.CYAN.color, ColorName.CYAN.color
    first.R = 0.5
    assert first != second
    assert second == ColorName.CYAN.color


def test_a_measured_colour_reads_as_the_nearest_name():
    """
    A colour measured off a real object never lands exactly on a named one, and is read
    as the name it lies nearest to.
    """
    measured = Color(0.0, 1.0, 0.8666666666666667)
    box = variable(Box, [])
    assert (
        verbalize_expression(box.color == measured)
        == f"the color of a Box is {ColorName.CYAN.name.lower()}"
    )


def test_a_named_colour_reads_as_its_own_name():
    """
    A colour stated as one of the named ones reads as that name.
    """
    box = variable(Box, [])
    assert (
        verbalize_expression(box.color == Color.BEIGE())
        == f"the color of a Box is {ColorName.BEIGE.name.lower()}"
    )
