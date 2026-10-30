"""
States that assign values to fluents without changing live objects.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property

from typing_extensions import Any, Iterator

from krrood.entity_query_language.evaluation import create_default_evaluation_context
from krrood.entity_query_language.ground_term import (
    FunctionSymbol,
    GroundTerm,
    TermReader,
)

# %% states


@dataclass(frozen=True)
class State(TermReader):
    """
    A valuation of fluents that differs from the live objects only where it assigns a
    value.

    A fluent is any :class:`~krrood.entity_query_language.ground_term.GroundTerm`: an
    attribute of an instance, an indexed element, or the result of a call, a symbolic
    function or a predicate for concrete arguments. Queries evaluated under
    :meth:`as_current` read the assigned value of every assigned fluent, and the live
    value of every other. The live objects are never changed.

    .. note:: An unassigned derived fluent follows the state only where its value comes
        from EQL: a body that is itself an EQL query, or inputs passed to it as EQL
        arguments, as in ``is_table(block.support)``. A Python body that reads an
        attribute directly, such as ``self.block.support``, reads the live value.

    .. warning:: An assigned fluent keeps its value even where it is derived from other
        fluents, so assigning a predicate overrides what it would compute from the
        fluents it reads, also after those change.
    """

    assignments: dict[GroundTerm, Any] = field(default_factory=dict)
    """
    The value of every fluent this state changes.

    Never mutated; a changed state is a new :class:`State`.
    """

    def __hash__(self) -> int:
        return hash(frozenset(self.assignments))

    @cached_property
    def assigned_symbols(self) -> frozenset[FunctionSymbol]:
        """
        :return: The symbols of the fluents this state assigns.
        """
        return frozenset(term.symbol for term in self.assignments)

    def with_assignments(self, assignments: dict[GroundTerm, Any]) -> State:
        """
        :param assignments: The new value of each fluent to change.
        :return: A new state that assigns *assignments* on top of this state's own
            assignments, the new value winning where both assign a fluent.
        """
        return State(assignments=self.assignments | assignments)

    def values_of(self, term: GroundTerm) -> Iterator[Any]:
        if term.symbol in self.assigned_symbols and term in self.assignments:
            yield self.assignments[term]
            return
        yield from term.live_values()

    @contextmanager
    def as_current(self) -> Iterator[None]:
        """
        Evaluate every query in the block against this state.
        """
        evaluation_context = create_default_evaluation_context()
        evaluation_context.term_reader = self
        with evaluation_context.as_current():
            yield
