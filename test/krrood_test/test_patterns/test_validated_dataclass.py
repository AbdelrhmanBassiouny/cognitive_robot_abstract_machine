"""
Tests of dataclasses validated on every instance and read from JSON by their field
types.
"""

from __future__ import annotations

import dataclasses

import pytest
from pydantic import ValidationError

from krrood.adapters.json_field import JSONField
from krrood.adapters.json_serializer import from_json, to_json
from ..dataset.validated_dataclasses import (
    CachedRecord,
    LabelledMeasurement,
    LinkedPage,
    Measurement,
    NamedStrictRecord,
    PageKey,
    ReadingKey,
    SensorReading,
    SourceMetadata,
    StrictLinkedPage,
    Survey,
)

# %% subclasses are validated dataclasses without a decorator


def test_subclass_is_a_dataclass() -> None:
    assert [field.name for field in dataclasses.fields(LabelledMeasurement)] == [
        "value",
        "label",
    ]


def test_value_is_converted_to_its_field_type() -> None:
    assert Measurement(value="1.5") == Measurement(value=1.5)


def test_value_of_the_wrong_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Measurement(value="not a number")


def test_inherited_field_of_a_subclass_is_validated() -> None:
    with pytest.raises(ValidationError):
        LabelledMeasurement(value="not a number", label="length")


# %% JSON


def test_json_round_trip_keeps_nested_objects() -> None:
    survey = Survey(measurements=[Measurement(value=1.0), Measurement(value=2.0)])
    assert from_json(to_json(survey)) == survey


def test_nested_object_is_read_as_the_class_of_its_field() -> None:
    survey = Survey._from_json({"measurements": [{"value": 3.0}]})
    assert survey.measurements == [Measurement(value=3.0)]


def test_key_without_a_field_is_ignored() -> None:
    assert Measurement._from_json({"value": 1.0, "unit": "m"}) == Measurement(value=1.0)


# %% settings


def test_settings_of_a_class_hold_for_its_subclasses() -> None:
    with pytest.raises(ValidationError):
        NamedStrictRecord._from_json(
            {"identifier": "first", "title": "First", "unit": "m"}
        )


def test_json_round_trip_of_a_class_rejecting_unknown_keys() -> None:
    record = NamedStrictRecord(identifier="first", title="First")
    assert from_json(to_json(record)) == record


# %% dataclass field arguments


def test_field_metadata_is_kept() -> None:
    assert SourceMetadata.of_field(CachedRecord, "identifier") == SourceMetadata()


def test_field_outside_the_constructor_takes_its_default() -> None:
    access_count = next(
        field
        for field in dataclasses.fields(CachedRecord)
        if field.name == "access_count"
    )
    assert CachedRecord(identifier="first").access_count == access_count.default


# %% keys named differently in the data


def test_value_is_read_under_its_alias() -> None:
    page = LinkedPage._from_json({PageKey.ADDRESS: "https://example.org"})
    assert page.address == "https://example.org"


def test_field_with_an_alias_is_set_by_its_name() -> None:
    assert LinkedPage(address="https://example.org").address == "https://example.org"


def test_value_is_written_under_its_alias() -> None:
    written = to_json(LinkedPage(address="https://example.org"))
    assert {key: value for key, value in written.items() if key not in JSONField} == {
        PageKey.ADDRESS: "https://example.org"
    }


def test_json_round_trip_of_a_field_with_an_alias() -> None:
    page = LinkedPage(address="https://example.org")
    assert from_json(to_json(page)) == page


def test_subclass_with_its_own_settings_is_set_by_field_name() -> None:
    page = StrictLinkedPage(address="https://example.org")
    assert from_json(to_json(page)) == page


def test_value_is_read_under_any_of_its_keys() -> None:
    reading = SensorReading._from_json({ReadingKey.MEASUREMENT: 2.5})
    assert reading == SensorReading(reading=2.5)
