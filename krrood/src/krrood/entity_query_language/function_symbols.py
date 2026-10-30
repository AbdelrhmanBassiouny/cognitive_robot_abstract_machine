"""
Function symbols - what a ground term applies to its arguments - and how each reads its
live value.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing_extensions import Any, Callable, Mapping, Sequence

from krrood.entity_query_language.core.bound_value import HasBoundValue
from krrood.utils import ensure_hashable

# %% function symbols


class FunctionSymbol(ABC):
    """
    What a ground term applies to its arguments: reading an attribute, indexing, or
    calling.
    """

    def normalized_arguments(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """
        :param arguments: The positional arguments of the application.
        :param keyword_arguments: The keyword arguments of the application.
        :return: The positional and keyword arguments that every way of writing this
            application passes alike.
        """
        return arguments, keyword_arguments

    def has_live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> bool:
        """
        :param arguments: The positional arguments of the application.
        :param keyword_arguments: The keyword arguments of the application.
        :return: Whether the application currently has a value.
        """
        return True

    @abstractmethod
    def live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Any:
        """
        :param arguments: The positional arguments of the application.
        :param keyword_arguments: The keyword arguments of the application.
        :return: The value the application currently has, where
            :meth:`has_live_value` holds.
        """


@dataclass(frozen=True)
class AttributeSymbol(FunctionSymbol):
    """
    Reading one attribute of an instance.
    """

    attribute_name: str
    """
    The name of the attribute.
    """

    def has_live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> bool:
        (instance,) = arguments
        return hasattr(instance, self.attribute_name)

    def live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Any:
        (instance,) = arguments
        return getattr(instance, self.attribute_name)


@dataclass(frozen=True)
class IndexSymbol(FunctionSymbol):
    """
    Reading the element a container stores under a key.
    """

    def has_live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> bool:
        container, key = arguments
        if isinstance(container, Mapping):
            return key in container
        if isinstance(container, Sequence) and isinstance(key, int):
            return -len(container) <= key < len(container)
        return True

    def live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Any:
        container, key = arguments
        return container[key]


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

    def normalized_arguments(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """
        Passing an argument by position or by name, or leaving out one that has a
        default, gives the same arguments.
        """
        bound_arguments = inspect.signature(self.callee).bind(
            *arguments, **keyword_arguments
        )
        bound_arguments.apply_defaults()
        return bound_arguments.args, bound_arguments.kwargs

    def live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Any:
        return self.callee(*arguments, **keyword_arguments)


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

    def live_value(
        self, arguments: tuple[Any, ...], keyword_arguments: dict[str, Any]
    ) -> Any:
        bound_arguments = inspect.signature(self.callee).bind(
            *arguments, **keyword_arguments
        )
        return self.callee._bound_value_(**bound_arguments.arguments)
