"""
Ground terms - a function symbol applied to concrete arguments - and how an evaluation
reads their values.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import cached_property

from typing_extensions import Any, Callable, Hashable, Iterator

from krrood.entity_query_language.core.bound_value import HasBoundValue
from krrood.utils import ensure_hashable

# %% function symbols


class FunctionSymbol(ABC):
    """
    What a ground term applies to its arguments: reading an attribute, indexing, or
    calling.
    """

    @abstractmethod
    def live_values(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Iterator[Any]:
        """
        :param arguments: The positional arguments of the application.
        :param keyword_arguments: The keyword arguments of the application.
        :return: The value the application currently has, or nothing when it has none.
        """

    def canonical_arguments(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> tuple[Hashable, ...]:
        """
        :param arguments: The positional arguments of the application.
        :param keyword_arguments: The keyword arguments of the application.
        :return: A key that is equal for two applications exactly when they name the same
            ground term. Hashable arguments are compared by value and all others by
            identity.
        """
        return tuple(ensure_hashable(argument) for argument in arguments)


@dataclass(frozen=True)
class AttributeSymbol(FunctionSymbol):
    """
    Reading one attribute of an instance.
    """

    attribute_name: str
    """
    The name of the attribute.
    """

    def live_values(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Iterator[Any]:
        (instance,) = arguments
        if hasattr(instance, self.attribute_name):
            yield getattr(instance, self.attribute_name)


@dataclass(frozen=True)
class IndexSymbol(FunctionSymbol):
    """
    Reading the element a container stores under a key.
    """

    def live_values(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Iterator[Any]:
        container, key = arguments
        try:
            yield container[key]
        except IndexError:  # break iterator if the key does not exist
            return


@dataclass(frozen=True, eq=False)
class CallableSymbol(FunctionSymbol):
    """
    Calling a function, method or class, whose result is the value.

    Two symbols are the same when they call the same callee.
    """

    callee: Callable[..., Any]
    """
    What is called.
    """

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CallableSymbol) and ensure_hashable(
            self.callee
        ) == ensure_hashable(other.callee)

    def __hash__(self) -> int:
        return hash(ensure_hashable(self.callee))

    def live_values(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Iterator[Any]:
        yield self.callee(*arguments, **keyword_arguments)

    def canonical_arguments(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> tuple[Hashable, ...]:
        """
        Arguments are matched to the callee's parameters first, so passing one by
        position or by name, or leaving out one that has a default, names the same
        ground term.
        """
        bound_arguments = inspect.signature(self.callee).bind(
            *arguments, **keyword_arguments
        )
        bound_arguments.apply_defaults()
        return tuple(
            (name, ensure_hashable(value))
            for name, value in bound_arguments.arguments.items()
        )


@dataclass(frozen=True, eq=False)
class CallableClassSymbol(CallableSymbol):
    """
    Applying a :class:`~krrood.entity_query_language.core.bound_value.HasBoundValue`
    class, such as a predicate or a symbolic function class, whose bound value is the
    value.
    """

    callee: type[HasBoundValue]
    """
    The class that is applied.
    """

    def live_values(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Iterator[Any]:
        if not arguments:
            yield self.callee._bound_value_(**keyword_arguments)
            return
        bound_arguments = inspect.signature(self.callee).bind(
            *arguments, **keyword_arguments
        )
        yield self.callee._bound_value_(**bound_arguments.arguments)


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
    def attribute(cls, instance: Any, attribute_name: str) -> GroundTerm:
        """
        :param instance: The instance whose attribute is meant.
        :param attribute_name: The name of the attribute.
        :return: The attribute *attribute_name* of *instance*.
        """
        return cls(AttributeSymbol(attribute_name), (instance,))

    @classmethod
    def index(cls, container: Any, key: Any) -> GroundTerm:
        """
        :param container: The container that is indexed.
        :param key: The key of the element.
        :return: The element *container* stores under *key*.
        """
        return cls(IndexSymbol(), (container, key))

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
            return cls(
                CallableSymbol(callee.__func__),
                (callee.__self__, *arguments),
                keyword_arguments,
            )
        if inspect.isclass(callee) and issubclass(callee, HasBoundValue):
            return cls(CallableClassSymbol(callee), arguments, keyword_arguments)
        return cls(CallableSymbol(inspect.unwrap(callee)), arguments, keyword_arguments)

    @cached_property
    def _key_(self) -> tuple[Hashable, ...]:
        """
        :return: What identifies this ground term, independently of how its arguments
            were passed.
        """
        return self.symbol, self.symbol.canonical_arguments(
            self.arguments, self.keyword_arguments
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GroundTerm) and self._key_ == other._key_

    def __hash__(self) -> int:
        return hash(self._key_)

    def live_values(self) -> Iterator[Any]:
        """
        :return: The value this ground term currently has, or nothing when it has none.
        """
        return self.symbol.live_values(self.arguments, self.keyword_arguments)


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
