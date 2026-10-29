"""
Fluents, and the states that assign values to them without changing live objects.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field

from typing_extensions import Any, Iterator

from krrood.entity_query_language.attribute_reader import (
    AttributeReader,
    LiveAttributeReader,
)
from krrood.entity_query_language.evaluation import create_default_evaluation_context

# %% fluents


@dataclass(frozen=True, eq=False)
class Fluent:
    """
    An attribute of one instance whose value a state can change.

    Two fluents are the same when they name the same attribute of the same object, even
    if another object compares equal to it.
    """

    instance: Any
    """
    The object the attribute belongs to.
    """

    attribute_name: str
    """
    The name of the attribute.
    """

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Fluent)
            and self.instance is other.instance
            and self.attribute_name == other.attribute_name
        )

    def __hash__(self) -> int:
        return hash((id(self.instance), self.attribute_name))


# %% states


@dataclass(frozen=True)
class State(AttributeReader):
    """
    A valuation of fluents that differs from the live objects only where it assigns a
    value.

    Queries evaluated under :meth:`as_current` read the assigned values, and the live
    value of every fluent the state does not assign. The live objects are never
    changed. Two states are equal when they assign the same values to the same fluents.
    """

    assignments: dict[Fluent, Any] = field(default_factory=dict)
    """
    The value of every fluent this state changes. Never mutated; a changed state is a
    new :class:`State`.
    """

    def __hash__(self) -> int:
        return hash(frozenset(self.assignments))

    def with_assignments(self, assignments: dict[Fluent, Any]) -> State:
        """
        :param assignments: The new value of each fluent to change.
        :return: A new state that assigns *assignments* on top of this state's own
            assignments, the new value winning where both assign a fluent.
        """
        return State(assignments=self.assignments | assignments)

    def read(self, instance: Any, attribute_name: str) -> Iterator[Any]:
        fluent = Fluent(instance, attribute_name)
        if fluent in self.assignments:
            yield self.assignments[fluent]
            return
        yield from LiveAttributeReader().read(instance, attribute_name)

    @contextmanager
    def as_current(self) -> Iterator[None]:
        """
        Evaluate every query in the block against this state.
        """
        evaluation_context = create_default_evaluation_context()
        evaluation_context.attribute_reader = self
        with evaluation_context.as_current():
            yield
