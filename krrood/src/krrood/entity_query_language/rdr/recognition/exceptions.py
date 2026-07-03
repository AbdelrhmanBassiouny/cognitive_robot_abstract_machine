"""Exceptions raised by the recognition layer."""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Type


class RecognitionError(Exception):
    """Base class for recognition-layer errors."""


@dataclass
class CyclicDefinitionDependency(RecognitionError):
    """Raised when view definitions reference each other's conclusions cyclically."""

    cycle: List[Type]
    """The view types forming the cycle, in traversal order."""

    def __str__(self) -> str:
        return "Cyclic definition dependency: " + " -> ".join(
            view_type.__name__ for view_type in self.cycle
        )


@dataclass
class UnregisteredView(RecognitionError):
    """Raised when a view type has no registered generator and definition."""

    view_type: Type
    """The view type that has no registered recognizer."""

    def __str__(self) -> str:
        return f"No recognizer registered for {self.view_type.__name__}"
