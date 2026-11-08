"""
Classes read from data whose shape another program controls, validated on every
instance.
"""

from __future__ import annotations

from dataclasses import field
from enum import StrEnum

from pydantic import AliasChoices, ConfigDict, Field
from typing_extensions import Annotated

from krrood.patterns.field_metadata import FieldMetadata
from krrood.patterns.validated_dataclass import ValidatedDataclass

# %% nested objects


class Measurement(ValidatedDataclass):
    """
    A value measured once.
    """

    value: float
    """
    The measured value.
    """


class LabelledMeasurement(Measurement):
    """
    A measurement whose value is named.
    """

    label: str
    """
    What was measured.
    """


class Survey(ValidatedDataclass):
    """
    The measurements taken together.
    """

    measurements: list[Measurement] = field(default_factory=list)
    """
    The measurements, in the order they were taken.
    """


# %% settings inherited by subclasses


class StrictRecord(ValidatedDataclass, config=ConfigDict(extra="forbid")):
    """
    A record that rejects keys it has no field for.
    """

    identifier: str
    """
    The record's identifier in the data it is read from.
    """


class NamedStrictRecord(StrictRecord):
    """
    A strict record with a name.
    """

    title: str
    """
    The name shown for the record.
    """


# %% dataclass field arguments


class SourceMetadata(FieldMetadata):
    """
    Marks a field as read from the source data.
    """


class CachedRecord(ValidatedDataclass):
    """
    A record holding a value computed from it rather than read.
    """

    identifier: str = field(metadata=SourceMetadata().as_dict())
    """
    The record's identifier in the data it is read from.
    """

    access_count: int = field(default=0, init=False)
    """
    How often the record was read since it was made.
    """


# %% keys named differently in the data


class PageKey(StrEnum):
    """
    The keys of a web page's data that differ from the field names they are read into.
    """

    ADDRESS = "html_url"
    """
    The address of the page.
    """


class LinkedPage(ValidatedDataclass):
    """
    A web page whose address the data names differently from its field.
    """

    address: Annotated[str, Field(alias=PageKey.ADDRESS)]
    """
    The address of the page.
    """


class StrictLinkedPage(LinkedPage, config=ConfigDict(extra="forbid")):
    """
    A web page that rejects keys it has no field for.
    """


class ReadingKey(StrEnum):
    """
    The keys a sensor reading is found under, depending on the data's version.
    """

    VALUE = "value"
    """
    The key of the current version.
    """

    MEASUREMENT = "measurement"
    """
    The key of the earlier version.
    """


class SensorReading(ValidatedDataclass):
    """
    A reading whose value is found under one of several keys.
    """

    reading: Annotated[
        float,
        Field(validation_alias=AliasChoices(ReadingKey.VALUE, ReadingKey.MEASUREMENT)),
    ]
    """
    The value read.
    """
