"""
States that assign values to fluents without changing live objects.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property

from typing_extensions import Any, Iterator

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.evaluation import create_default_evaluation_context
from krrood.entity_query_language.function_symbols import FunctionSymbol
from krrood.entity_query_language.ground_term import GroundTerm, TermReader
from krrood.planning.fact import Fact

# %% states


@dataclass(frozen=True)
class State(TermReader):
    """
    A valuation of fluents that differs from the live objects only where it assigns a
    value.

    A fluent is a :class:`~krrood.entity_query_language.ground_term.GroundTerm`: an
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

    def with_facts(self, *facts: SymbolicExpression) -> State:
        """
        :param facts: Conditions that each fix the value of fluents, as
            :meth:`~krrood.planning.fact.Fact.from_condition` reads them. A fact whose
            expression has variables fixes the fluent for every binding of them.
        :return: A new state that assigns the values *facts* state on top of this
            state's own assignments, a later value winning where two assign a fluent.
        """
        assignments = dict(self.assignments)
        for fact in facts:
            assignments |= Fact.from_condition(fact).assignments()
        return State(assignments=assignments)

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
