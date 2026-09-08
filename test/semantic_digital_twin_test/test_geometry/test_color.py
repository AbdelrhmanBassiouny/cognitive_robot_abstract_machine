"""
Tests for the colours this twin has a word for, for reading a measured colour as one of
them, and for reading and writing a colour as a hex string.
"""

from __future__ import annotations

import pytest
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

from semantic_digital_twin.exceptions import MalformedHexColor
from semantic_digital_twin.world_description.geometry import Box, Color, ColorName

# %% naming a colour


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


# %% reading a hex string


def test_a_hex_string_names_one_channel_per_pair_of_digits():
    color = Color.from_hex("#4080C0")
    assert color.to_rgb() == (0x40 / 255, 0x80 / 255, 0xC0 / 255)


def test_a_hex_string_without_an_alpha_pair_is_fully_opaque():
    assert Color.from_hex("#4080C0").A == Color().A


def test_a_fourth_pair_of_digits_names_the_opacity():
    assert Color.from_hex("#4080C020").A == 0x20 / 255


def test_the_leading_hash_is_optional():
    assert Color.from_hex("4080C0") == Color.from_hex("#4080C0")


def test_a_hex_string_is_read_regardless_of_the_case_it_is_written_in():
    assert Color.from_hex("#4080c0") == Color.from_hex("#4080C0")


# %% rejecting what is not a hex string


@pytest.mark.parametrize(
    "malformed", ["#4080C", "#4080C0F", "", "#", "#4080GG", "#4080C0 "]
)
def test_a_string_that_is_not_a_color_is_rejected(malformed):
    """
    A malformed literal that is read as a color silently draws the wrong thing, so it
    has to be refused where it is read.
    """
    with pytest.raises(MalformedHexColor):
        Color.from_hex(malformed)


# %% writing a hex string


def test_a_color_read_from_a_hex_string_is_written_back_as_that_string():
    literal = "#4080C0"
    assert Color.from_hex(literal).to_hex() == literal


def test_the_written_hex_string_leaves_out_the_opacity():
    """
    :meth:`Color.to_hex` is the counterpart of :meth:`Color.to_rgb`, so a translucent
    color is written as the same three channels an opaque one is.
    """
    translucent = Color.from_hex("#4080C020")
    assert translucent.to_hex() == Color.from_hex("#4080C0").to_hex()


# %% colors as set and dictionary members


def test_equal_colors_are_one_and_the_same_set_member():
    assert len({Color.from_hex("#4080C0"), Color.from_hex("#4080C0")}) == 1


def test_colors_differing_only_in_opacity_are_told_apart():
    assert len({Color.from_hex("#4080C0"), Color.from_hex("#4080C020")}) == 2
