from __future__ import annotations

import pytest
from typing_extensions import Generic, TypeVar

from krrood.patterns.exceptions import InvalidEnumerationKey
from krrood.patterns.generic_enumeration import GenericEnumeration
from krrood.utils import get_generic_type_parameters

# %% enumerations under test

LabelType = TypeVar("LabelType")
"""
The type of the labels an enumeration's members carry.
"""


class Labelled(Generic[LabelType], GenericEnumeration):
    """
    A generic enumeration whose members carry labels of one type.
    """


class Colours(Labelled[str]):
    """
    An enumeration binding the label type through subscription.
    """

    RED = "red"
    GREEN = "green"


# %% subscription with types binds the parameters


def test_subscripting_with_a_type_binds_the_parameter() -> None:
    assert get_generic_type_parameters(Colours, Labelled) == [str]


# %% members are accessed as on any enumeration


def test_subscripting_with_a_member_name_looks_up_the_member() -> None:
    assert Colours[Colours.RED.name] is Colours.RED


def test_subscripting_with_an_unknown_member_name_raises_key_error() -> None:
    with pytest.raises(KeyError):
        Colours["BLUE"]


def test_calling_with_a_value_looks_up_the_member() -> None:
    assert Colours(Colours.GREEN.value) is Colours.GREEN


def test_iterating_lists_the_members_in_declaration_order() -> None:
    assert list(Colours) == [Colours.RED, Colours.GREEN]


# %% subscription with anything else is refused


def test_subscripting_with_neither_a_name_nor_a_type_is_refused() -> None:
    with pytest.raises(InvalidEnumerationKey):
        Colours[1]


def test_subscripting_with_a_type_once_the_parameters_are_bound_is_refused() -> None:
    with pytest.raises(InvalidEnumerationKey):
        Colours[str]


def test_a_refused_key_is_both_a_key_error_and_a_type_error() -> None:
    assert issubclass(InvalidEnumerationKey, KeyError)
    assert issubclass(InvalidEnumerationKey, TypeError)
