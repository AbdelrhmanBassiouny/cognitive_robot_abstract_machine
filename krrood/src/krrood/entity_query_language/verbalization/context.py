from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from typing_extensions import Any

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.verbalization.microplanning.binding_scope import (
    BindingScope,
)
from krrood.entity_query_language.verbalization.microplanning.config import (
    RenderConfiguration,
)
from krrood.entity_query_language.verbalization.microplanning.microplan import (
    Microplan,
)
from krrood.entity_query_language.verbalization.microplanning.referring import (
    ReferringExpressions,
)

__all__ = ["MicroplanningServices"]


@dataclass
class MicroplanningServices:
    """
    The three microplanning services for one verbalization pass: the referring-expression
    service, the binding scope, and the render configuration.

    The split mirrors the microplanning subtasks of Reiter & Dale (2000).
    """

    referring: ReferringExpressions = field(default_factory=ReferringExpressions)
    """Coreference / article / disambiguation / pronoun service."""

    binding: BindingScope = field(default_factory=BindingScope)
    """Deferred-constraint frames and field-reference overrides."""

    configuration: RenderConfiguration = field(default_factory=RenderConfiguration)
    """Render-mode flags (query depth, compact predicates)."""

    microplan: Microplan = field(default_factory=Microplan)
    """The plan read model — each node's plan computed once and shared (lazy / memoised)."""

    @classmethod
    def from_expression(cls, expression: SymbolicExpression) -> MicroplanningServices:
        """
        Create a context with the disambiguation map pre-built for *expression*.

        :param expression: Root EQL expression or query to scan.
        :return: A fresh context whose referring service has its disambiguation map populated.
        """
        return cls(referring=ReferringExpressions.from_expression(expression))

    # ── Value lexicalisation ─────────────────────────────────────────────────

    def type_name_of_value(self, value: Any) -> str:
        """
        Render a Python value as a human-readable string.

        * A bare ``type`` → its ``__name__`` (``Apple`` → ``"Apple"``).
        * A tuple of types → ``"A or B or C"``.
        * A ``datetime`` with no time → ``"May 23, 2026"``; with a time →
          ``"May 23, 2026 at 14:30"``.
        * Anything else → ``repr(value)``.

        :param value: Python value from a literal node.
        :return: Human-readable string representation.
        """
        if isinstance(value, type):
            return value.__name__
        if isinstance(value, tuple) and all(
            isinstance(variable, type) for variable in value
        ):
            return " or ".join(variable.__name__ for variable in value)
        if isinstance(value, datetime.datetime):
            if value.time() == datetime.time.min:
                return value.strftime("%B %-d, %Y")
            return value.strftime("%B %-d, %Y at %H:%M")
        return repr(value)
