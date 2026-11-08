"""
Classes read from data whose shape another program controls, validated on every
instance.
"""

from __future__ import annotations

from dataclasses import field

from pydantic import ConfigDict

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
