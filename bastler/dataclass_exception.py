"""
An exception whose message and correction a concrete subclass composes.

Generic rather than tied to any one failure's fields, so every dataclass-based exception
in :mod:`bastler` can share it instead of restating the composition.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DataclassException(Exception, ABC):
    """
    Base for a dataclass exception whose text a concrete subclass composes.
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
