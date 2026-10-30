"""
Ground terms - a function symbol applied to concrete arguments - the expressions that
read them, and how an evaluation reads their values.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property

from typing_extensions import TYPE_CHECKING, Any, Callable, Hashable, Iterator

from krrood.entity_query_language.core.bound_value import HasBoundValue
from krrood.entity_query_language.function_symbols import (
    CallableClassSymbol,
    CallableSymbol,
    FunctionSymbol,
)
from krrood.utils import ensure_hashable

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression

# %% ground terms


@dataclass(frozen=True, eq=False)
class GroundTerm:
    """
    A function symbol applied to concrete arguments, such as the attribute ``support``
    of one block or a predicate applied to two objects.

    Two ground terms are equal when they apply the same symbol to the same arguments,
    however the arguments were passed and including defaults that were left out.
    Hashable arguments are compared by value and all others by identity, so two objects
    that compare equal but cannot be hashed are different arguments.
    """

    symbol: FunctionSymbol
    """
    What is applied to the arguments.
    """

    arguments: tuple[Any, ...] = ()
    """
    The positional arguments of the application.
    """

    keyword_arguments: dict[str, Any] = field(default_factory=dict)
    """
    The keyword arguments of the application.
    """

    @classmethod
    def call(
        cls, callee: Callable[..., Any], *arguments: Any, **keyword_arguments: Any
    ) -> GroundTerm:
        """
        :param callee: A function, a bound method, a class, or a function decorated
            with :func:`~krrood.entity_query_language.predicate.symbolic_function`.
        :param arguments: The positional arguments of the call.
        :param keyword_arguments: The keyword arguments of the call.
        :return: The result of calling *callee* with the given arguments, as queries
            reach it.
        """
        if inspect.ismethod(callee):
            arguments = (callee.__self__, *arguments)
            callee = callee.__func__
        if inspect.isclass(callee) and issubclass(callee, HasBoundValue):
            symbol = CallableClassSymbol(callee)
        else:
            symbol = CallableSymbol(inspect.unwrap(callee))
        return cls(symbol, arguments, keyword_arguments)

    @cached_property
    def _key_(self) -> tuple[Hashable, ...]:
        """
        :return: What identifies this ground term, independently of how its arguments
            were passed.
        """
        arguments, keyword_arguments = self.symbol.normalized_arguments(
            self.arguments, self.keyword_arguments
        )
        return (
            self.symbol,
            tuple(ensure_hashable(argument) for argument in arguments),
            tuple(
                (name, ensure_hashable(value))
                for name, value in sorted(keyword_arguments.items())
            ),
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GroundTerm) and self._key_ == other._key_

    def __hash__(self) -> int:
        return hash(self._key_)

    def has_live_value(self) -> bool:
        """
        :return: Whether this ground term currently has a value.
        """
        return self.symbol.has_live_value(self.arguments, self.keyword_arguments)

    def live_values(self) -> Iterator[Any]:
        """
        :return: The value this ground term currently has, or nothing when it has none.
        """
        if self.has_live_value():
            yield self.symbol.live_value(self.arguments, self.keyword_arguments)


# %% expressions that read ground terms


class GroundTermExpression(ABC):
    """
    An expression whose value, for each binding of its operands, is the value of one
    ground term.
    """

    @property
    @abstractmethod
    def _ground_term_operands_(self) -> tuple[SymbolicExpression, ...]:
        """
        :return: The expressions whose values are the arguments of the ground term.
        """

    @abstractmethod
    def _ground_term_(self, *operand_values: Any) -> GroundTerm:
        """
        :param operand_values: One value of each of :attr:`_ground_term_operands_`, in
            the same order.
        :return: The ground term this expression reads for *operand_values*.
        """


# %% reading ground terms


class TermReader(ABC):
    """
    Reads the value of a ground term during an evaluation.
    """

    @abstractmethod
    def values_of(self, term: GroundTerm) -> Iterator[Any]:
        """
        :param term: The ground term to read.
        :return: The value of *term*, or nothing when it has none.
        """


@dataclass
class LiveTermReader(TermReader):
    """
    Reads the value a ground term currently has on the live objects.
    """

    def values_of(self, term: GroundTerm) -> Iterator[Any]:
        return term.live_values()
