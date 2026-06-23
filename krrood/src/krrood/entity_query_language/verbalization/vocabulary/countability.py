from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from typing_extensions import FrozenSet


class Countability(StrEnum):
    """Whether a noun denotes discrete instances (countable) or an undifferentiated mass."""

    COUNTABLE = "countable"
    """A noun that pluralises and takes an article — *"a battery"* / *"the battery"*."""
    UNCOUNTABLE = "uncountable"
    """A mass noun that resists the indefinite article and, in non-anaphoric use, the definite one —
    *"money"*, not *"a money"* / *"the money"* when first mentioned generically."""


_UNCOUNTABLE_NOUNS: FrozenSet[str] = frozenset(
    {
        "money",
        "cash",
        "wealth",
        "water",
        "milk",
        "blood",
        "oxygen",
        "air",
        "gasoline",
        "electricity",
        "sand",
        "salt",
        "sugar",
        "rice",
        "information",
        "knowledge",
        "evidence",
        "advice",
        "news",
        "research",
        "homework",
        "progress",
        "music",
        "furniture",
        "equipment",
        "machinery",
        "hardware",
        "software",
        "luggage",
        "baggage",
        "traffic",
        "weather",
    }
)
"""Common English mass nouns, lower-cased. Curated rather than inferred: countability is a stable
lexical property, so a small audited set is more reliable than a runtime heuristic over schema-derived
attribute names."""


@dataclass(frozen=True)
class NounCountability:
    """Classifies a noun as countable or uncountable against a curated mass-noun lexicon."""

    uncountable_nouns: FrozenSet[str] = _UNCOUNTABLE_NOUNS
    """The mass-noun lexicon consulted; overridable so a domain may extend it."""

    def classify(self, noun: str) -> Countability:
        """:return: the countability of *noun* (case-insensitive lookup).

        >>> NounCountability().classify("money")
        <Countability.UNCOUNTABLE: 'uncountable'>
        >>> NounCountability().classify("battery")
        <Countability.COUNTABLE: 'countable'>
        """
        if noun.lower() in self.uncountable_nouns:
            return Countability.UNCOUNTABLE
        return Countability.COUNTABLE

    def is_uncountable(self, noun: str) -> bool:
        """:return: whether *noun* is a mass noun.

        >>> NounCountability().is_uncountable("water")
        True
        >>> NounCountability().is_uncountable("department")
        False
        """
        return self.classify(noun) is Countability.UNCOUNTABLE
