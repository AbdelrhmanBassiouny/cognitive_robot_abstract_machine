from __future__ import annotations

import pytest
from typing_extensions import Generic, TypeVar

from krrood.ormatic.utils import classproperty
from krrood.patterns.exceptions import InvalidEnumerationKey
from krrood.patterns.generic_enumeration import GenericEnumeration
from krrood.utils import get_generic_type_parameters

# %% enumerations under test

EnclosingType = TypeVar("EnclosingType")
"""
The enumeration another enumeration is nested under.
"""


class Menu(GenericEnumeration):
    """
    An enumeration without type parameters that others are nested under.
    """

    STARTER = "starter"
    MAIN_COURSE = "main course"


class NestedEnumeration(Generic[EnclosingType], GenericEnumeration):
    """
    An enumeration nested under the enumeration it binds as its type parameter.
    """

    @classproperty
    def enclosing(cls) -> type[GenericEnumeration]:
        """
        The enumeration this one is nested under.
        """
        return get_generic_type_parameters(cls, NestedEnumeration)[0]


class Starters(NestedEnumeration[Menu]):
    """
    An enumeration nested under :class:`Menu` through subscription.
    """

    SOUP = "soup"
    SALAD = "salad"


# %% subscription with types binds the parameters


def test_subscripting_with_a_type_binds_the_parameter() -> None:
    assert Starters.enclosing is Menu


# %% members are accessed as on any enumeration


def test_subscripting_with_a_member_name_looks_up_the_member() -> None:
    assert Starters[Starters.SOUP.name] is Starters.SOUP


def test_subscripting_with_an_unknown_member_name_raises_key_error() -> None:
    with pytest.raises(KeyError):
        Starters["DESSERT"]


def test_calling_with_a_value_looks_up_the_member() -> None:
    assert Starters(Starters.SALAD.value) is Starters.SALAD


def test_iterating_lists_the_members_in_declaration_order() -> None:
    assert list(Starters) == [Starters.SOUP, Starters.SALAD]


# %% subscription with anything else is refused


def test_subscripting_with_neither_a_name_nor_a_type_is_refused() -> None:
    with pytest.raises(InvalidEnumerationKey):
        Starters[1]


def test_subscripting_an_enumeration_without_type_parameters_is_refused() -> None:
    with pytest.raises(InvalidEnumerationKey):
        Menu[Menu]


def test_subscripting_with_a_type_once_the_parameters_are_bound_is_refused() -> None:
    with pytest.raises(InvalidEnumerationKey):
        Starters[Menu]


def test_a_refused_key_is_both_a_key_error_and_a_type_error() -> None:
    assert issubclass(InvalidEnumerationKey, KeyError)
    assert issubclass(InvalidEnumerationKey, TypeError)
