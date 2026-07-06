"""Exceptions raised by the recognition layer."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Type

from krrood.exceptions import DataclassException


class RecognitionError(DataclassException):
    """Abstract base for recognition-layer errors."""


@dataclass
class CyclicDefinitionDependency(RecognitionError):
    """Raised when view definitions reference each other's conclusions cyclically."""

    cycle: List[Type]
    """The view types forming the cycle, in traversal order."""

    def error_message(self) -> str:
        names = " -> ".join(view_type.__name__ for view_type in self.cycle)
        return f"Cyclic definition dependency: {names}"

    def suggest_correction(self) -> str:
        return (
            "A definition may reference another view's conclusion but must not form a "
            "loop; remove one of the referenced_conclusions edges."
        )


@dataclass
class UnregisteredView(RecognitionError):
    """Raised when a view type has no registered definition."""

    view_type: Type
    """The view type that has no registered recognizer."""

    def error_message(self) -> str:
        return f"No recognizer registered for {self.view_type.__name__}"

    def suggest_correction(self) -> str:
        return "Register it with DefinitionRegistry.register(view_type, definition)."
