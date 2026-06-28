"""
Arithmetic operators for the Entity Query Language.

An arithmetic node (see :mod:`krrood.entity_query_language.operators.arithmetic`) delegates its
computation to the :class:`MathOperator` it carries: each operator owns both its rendered symbol and the
Python callable that performs it, so the node stays decoupled from the concrete operation.
"""

from __future__ import annotations

import operator
from enum import Enum

from typing_extensions import Any, Callable


class MathOperator(Enum):
    """
    An arithmetic operator usable inside a query. Each member carries the symbol it renders as and the
    callable that computes it over already-resolved operand values.
    """

    ADD = ("add", "+", operator.add)
    SUBTRACT = ("subtract", "-", operator.sub)
    MULTIPLY = ("multiply", "*", operator.mul)
    DIVIDE = ("divide", "/", operator.truediv)
    FLOOR_DIVIDE = ("floor_divide", "//", operator.floordiv)
    MODULO = ("modulo", "%", operator.mod)
    POWER = ("power", "**", operator.pow)
    NEGATE = ("negate", "-", operator.neg)

    def __init__(
        self, identifier: str, symbol: str, function: Callable[..., Any]
    ) -> None:
        self._identifier = identifier
        """The unique identifier of the operator (keeps the enum values distinct)."""
        self.symbol = symbol
        """The mathematical symbol used when rendering the operator."""
        self.function = function
        """The callable that performs the operation over already-resolved operand values."""
