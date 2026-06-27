from __future__ import annotations

from enum import StrEnum


class Countability(StrEnum):
    """Whether a noun denotes discrete instances (countable) or an undifferentiated mass.

    Authored per field in the offline field metadata; there is no name-based default, so a field the
    metadata says nothing about is treated as countable.
    """

    COUNTABLE = "countable"
    """A noun that pluralises and takes an article — *"a battery"* / *"the battery"*."""
    UNCOUNTABLE = "uncountable"
    """A mass noun that drops the article in a non-anaphoric genitive hop — *"the amount of money"*,
    not *"the amount of the money"*."""
