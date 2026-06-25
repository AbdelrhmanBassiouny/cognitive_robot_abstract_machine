"""
Global configuration for the Entity Query Language.

The configuration is a singleton (mirroring :class:`~krrood.symbol_graph.symbol_graph.SymbolGraph`) so a
user can change EQL-wide behaviour once and have every subsequent query observe it. Currently it
selects the backend used to evaluate symbolic arithmetic operations.
"""

from __future__ import annotations

from dataclasses import dataclass

from krrood.entity_query_language.operators.math_operations import (
    MathBackend,
    MathOperations,
    math_operations_for,
)
from krrood.singleton import SingletonMeta


@dataclass
class EqlConfiguration(metaclass=SingletonMeta):
    """
    The single, user-settable configuration object for the Entity Query Language.

    Set the backend with ``EqlConfiguration().math_backend = MathBackend.SYMBOLIC``.
    """

    math_backend: MathBackend = MathBackend.PYTHON
    """The backend used to evaluate symbolic arithmetic operations."""

    @property
    def math_operations(self) -> MathOperations:
        """
        :return: The math-operations implementation for the active backend.
        """
        return math_operations_for(self.math_backend)
