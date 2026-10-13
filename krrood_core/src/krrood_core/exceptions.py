from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol

# %% exception base


@dataclass
class CanBehaveLikeDataclassException(Protocol):
    """
    A structural template that indicates the matching class is an exception or can be
    treated as one.
    """

    @abstractmethod
    def error_message(self) -> str:
        """
        :return: A human-readable description of what went wrong.
        """

    @abstractmethod
    def suggest_correction(self) -> str:
        """
        :return: Advice on how to fix the error, or an empty string if there is no specific advice.
        """


@dataclass
class DataclassException(Exception, CanBehaveLikeDataclassException, ABC):
    """
    A base exception class for dataclass-based exceptions.

    Subclasses implement error_message() and suggest_correction(); both are evaluated at
    construction time and composed into the actual exception message (the args passed to
    Exception). A non-empty suggest_correction() is rendered as a trailing "Suggestion:
    ..." line. Subclasses that override __post_init__ must call super().__post_init__()
    at the end.
    """

    print_stack_trace: bool = field(default=True, kw_only=True)
    """
    Whether the stack trace of this exception should be printed when it is handled.
    """

    def __post_init__(self):
        # BaseException.__new__ bypasses the usual ABC instantiation check, so enforce it here.
        if getattr(type(self), "__abstractmethods__", None):
            raise TypeError(
                f"Can't instantiate abstract class {type(self).__name__} without an implementation of "
                f"{', '.join(sorted(type(self).__abstractmethods__))}."
            )
        message = self.error_message()
        correction = self.suggest_correction()
        if correction:
            message = f"{message}\nSuggestion: {correction}"
        super().__init__(message)

    def __str__(self) -> str:
        # Stdlib mixins like KeyError override __str__ to repr their args; always render the
        # plain message that __post_init__ baked into the args.
        return Exception.__str__(self)


# %% generic arguments


@dataclass
class NoGenericError(DataclassException, TypeError):
    """
    Exception raised when the original class for a DataAccessObject subclass cannot be
    determined.

    This exception is typically raised when a DataAccessObject subclass has not been
    parameterized properly, which prevents identifying the original class associated
    with it.
    """

    clazz: type

    def error_message(self) -> str:
        return f"Cannot determine original class for {self.clazz}."

    def suggest_correction(self) -> str:
        return "did you forget to parameterise the DataAccessObject subclass?"
