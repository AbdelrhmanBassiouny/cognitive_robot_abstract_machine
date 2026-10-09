"""
Mimic procedures that count their calls, for testing that a query calls each predicate
and symbolic function once per distinct tuple of argument objects within one evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, List

from krrood.entity_query_language.predicate import (
    Predicate,
    RenderedFields,
    SymbolicFunction,
)
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    FunctionVerbalizationTemplates,
)

# %% places and a call log


@dataclass(eq=False)
class Place:
    """
    A place that a procedure is asked about.
    """

    distance: float
    """
    The distance to the place.
    """


@dataclass(eq=False)
class Visit:
    """
    A visit to a place; several visits can share one place.
    """

    place: Place
    """
    The place visited.
    """


@dataclass
class CallLog:
    """
    The arguments of every call of a counted procedure, in call order.
    """

    calls: List[Any] = field(default_factory=list)
    """
    The argument of each call.
    """


CALL_LOG = CallLog()
"""
The call log that the counted procedures append to.
"""

REACH = 10.0
"""
The greatest distance that :class:`IsWithinReach` accepts.
"""

# %% counted procedures


@dataclass(eq=False)
class IsWithinReach(Predicate):
    """
    Whether a place is within :data:`REACH`, recording each call.
    """

    place: Place
    """
    The place checked.
    """

    def __call__(self) -> bool:
        CALL_LOG.calls.append(self.place)
        return self.place.distance <= REACH

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        return FunctionVerbalizationTemplates.possessive(cls, *fields.values())


@dataclass(eq=False)
class TravelTime(SymbolicFunction):
    """
    The time to travel to a place at unit speed, recording each call.
    """

    place: Place
    """
    The place travelled to.
    """

    def __call__(self) -> float:
        CALL_LOG.calls.append(self.place)
        return self.place.distance

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        return FunctionVerbalizationTemplates.possessive(cls, *fields.values())
