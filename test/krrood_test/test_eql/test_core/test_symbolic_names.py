"""
Which names a missing attribute read raises for, and which it reads as a symbolic
attribute of the value type.
"""

from dataclasses import dataclass

import pytest

from krrood.entity_query_language.core.mapped_variable import Attribute
from krrood.entity_query_language.factories import a, variable

from ...dataset.expression_stand_ins import ValueStandInWithUnreadableProperty


@dataclass
class SerialNumbered:
    """
    A class whose instances keep a single-underscore private attribute.
    """

    _serial: int
    """
    The serial number, private by Python's convention.
    """


# %% names the class declares


def test_unreadable_declared_property_raises_instead_of_reading_the_value_type():
    stand_in = ValueStandInWithUnreadableProperty(variable(int, domain=[1]))
    with pytest.raises(AttributeError):
        _ = stand_in._unreadable_


# %% names a match keeps for itself


def test_match_reads_a_private_attribute_of_the_matched_class_symbolically():
    match = a(SerialNumbered)
    assert isinstance(match._serial, Attribute)


def test_match_filters_on_a_private_attribute_of_the_matched_class():
    records = [SerialNumbered(1), SerialNumbered(2)]
    match = a(SerialNumbered).from_(records)
    assert match.where(match._serial == 2).tolist() == [records[1]]


def test_match_raises_for_a_missing_name_of_its_own_form():
    with pytest.raises(AttributeError):
        _ = a(SerialNumbered)._missing_
