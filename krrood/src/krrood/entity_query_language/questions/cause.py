from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Tuple

from krrood.entity_query_language.core.base_expressions import (
    Bindings,
    SymbolicExpression,
)


@dataclass
class Cause:
    """One explanatory condition together with the bindings under which it held."""

    condition: SymbolicExpression
    """The condition expression that was satisfied while the instance was inferred."""

    bindings: Bindings
    """The variable bindings under which :attr:`condition` held."""


@dataclass
class CauseSet:
    """The explanatory conditions that produced an inferred instance.

    Denotationally this is the answer to a ``why`` question: the conditions (with bindings) whose
    satisfaction caused the instance to be inferred.
    """

    instance: Any
    """The inferred instance being explained."""

    causes: Tuple[Cause, ...]
    """The conditions, with bindings, that explain why :attr:`instance` was inferred."""

    @property
    def is_empty(self) -> bool:
        """:return: Whether no explanatory condition backs the inference."""
        return not self.causes
