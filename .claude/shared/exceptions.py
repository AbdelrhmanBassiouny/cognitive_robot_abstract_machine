"""
The failure an outside dependency reports, stated once for every tool that has one.

git and the GitHub API are the things this tooling depends on and does not control. What
a caller needs when either refuses is identical - naming the call, saying what went
wrong, and offering a correction if there is one - so the shape is stated here and each
concrete failure supplies its own three answers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExternalCallFailed(RuntimeError, ABC):
    """
    Base for a call to something outside this tooling that a caller depended on.

    Mirrors ``krrood``'s dataclass-exception idiom - typed context fields, abstract
    ``error_message``/``suggest_correction`` a concrete subclass supplies and ``__str__``
    composes - without importing it, since everything here is reachable from
    ``SessionStart`` and depends on the standard library alone.
    """

    status: int
    """
    The status the call came back with.
    """

    detail: str
    """
    What the far side said about it.
    """

    def __post_init__(self) -> None:
        """
        Refuse construction if a concrete subclass left any abstract method
        unimplemented.

        ``BaseException.__new__`` bypasses the usual ``ABCMeta`` instantiation check, so
        without this an incomplete subclass would build silently and fail only the first
        time something read the missing method.
        """
        if getattr(type(self), "__abstractmethods__", None):
            raise TypeError(
                f"Can't instantiate abstract class {type(self).__name__} without an "
                f"implementation for {', '.join(sorted(type(self).__abstractmethods__))}."
            )

    @property
    @abstractmethod
    def call(self) -> str:
        """
        :return: The call that failed, named the way its own caller named it.
        """

    @abstractmethod
    def error_message(self) -> str:
        """
        :return: What went wrong, in this failure's own words.
        """

    @abstractmethod
    def suggest_correction(self) -> str:
        """
        :return: Advice on how to fix the error, or an empty string if there is none.
        """

    def __str__(self) -> str:
        """
        :return: :meth:`error_message`, with :meth:`suggest_correction` appended as a
            trailing ``"Suggestion: ..."`` line when it has one.
        """
        message = self.error_message()
        correction = self.suggest_correction()
        if correction:
            message = f"{message}\nSuggestion: {correction}"
        return message


@dataclass
class GitCommandFailed(ExternalCallFailed):
    """
    Raised when a git command whose result was depended on fails.
    """

    arguments: tuple[str, ...] = ()
    """
    The git subcommand and its arguments, as invoked.
    """

    @property
    def call(self) -> str:
        """
        :return: The git command line, as invoked.
        """
        return f"git {' '.join(self.arguments)}"

    def error_message(self) -> str:
        """
        :return: The call, its status, and the reason given.
        """
        return f"{self.call} failed with {self.status}: {self.detail}"

    def suggest_correction(self) -> str:
        """
        :return: No git command carries generic advice yet.
        """
        return ""
