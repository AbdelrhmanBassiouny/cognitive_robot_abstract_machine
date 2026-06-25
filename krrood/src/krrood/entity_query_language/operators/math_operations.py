"""
Backends for evaluating arithmetic operators in the Entity Query Language.

An arithmetic node (see :mod:`krrood.entity_query_language.operators.arithmetic`) does not know how to
compute its result; it delegates to a :class:`MathOperations` backend.  The default backend computes
with Python's numeric operators; the symbolic backend builds :mod:`krrood.symbolic_math` expressions.
This keeps the node decoupled from the computation (Dependency Inversion).
"""

from __future__ import annotations

import operator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from typing_extensions import Any, Callable, ClassVar, Dict, Tuple


class MathOperator(Enum):
    """
    An arithmetic operator that can be represented symbolically inside a query.
    """

    ADD = ("add", "+")
    SUBTRACT = ("subtract", "-")
    MULTIPLY = ("multiply", "*")
    DIVIDE = ("divide", "/")
    FLOOR_DIVIDE = ("floor_divide", "//")
    MODULO = ("modulo", "%")
    POWER = ("power", "**")
    NEGATE = ("negate", "-")

    def __init__(self, identifier: str, symbol: str) -> None:
        self._identifier = identifier
        """The unique identifier of the operator (keeps the enum values distinct)."""
        self.symbol = symbol
        """The mathematical symbol used when rendering the operator."""


class MathBackend(Enum):
    """
    The available backends for evaluating symbolic arithmetic operations.
    """

    PYTHON = "python"
    SYMBOLIC = "symbolic"


@dataclass
class MathOperations(ABC):
    """
    Abstract backend that evaluates a :class:`MathOperator` over already-resolved operand values.

    The operator functions are shared; backends differ only in how they adapt the operands before the
    operator is applied, so a new operator is added in one place (Open/Closed).
    """

    _operations: ClassVar[Dict[MathOperator, Callable[..., Any]]] = {
        MathOperator.ADD: operator.add,
        MathOperator.SUBTRACT: operator.sub,
        MathOperator.MULTIPLY: operator.mul,
        MathOperator.DIVIDE: operator.truediv,
        MathOperator.FLOOR_DIVIDE: operator.floordiv,
        MathOperator.MODULO: operator.mod,
        MathOperator.POWER: operator.pow,
        MathOperator.NEGATE: operator.neg,
    }
    """
    Maps each operator to the callable that performs it. The symbolic backend reuses these because
    :class:`~krrood.symbolic_math.symbolic_math.Scalar` overloads the same Python operators.
    """

    def apply(self, math_operator: MathOperator, operands: Tuple[Any, ...]) -> Any:
        """
        Evaluate ``math_operator`` over ``operands`` using this backend.

        :param math_operator: The operator to apply.
        :param operands: The resolved operand values (two for binary operators, one for negation).
        :return: The result of the operation.
        """
        return self._operations[math_operator](*self._prepare_operands_(operands))

    @abstractmethod
    def _prepare_operands_(self, operands: Tuple[Any, ...]) -> Tuple[Any, ...]:
        """
        Adapt the operand values to this backend before the operator callable is applied.

        :param operands: The resolved operand values.
        :return: The operands as this backend needs them.
        """
        ...


@dataclass
class PythonMathOperations(MathOperations):
    """
    Evaluates arithmetic with Python's built-in numeric operators. This is the default backend.
    """

    def _prepare_operands_(self, operands: Tuple[Any, ...]) -> Tuple[Any, ...]:
        return operands


@dataclass
class SymbolicMathOperations(MathOperations):
    """
    Evaluates arithmetic as :mod:`krrood.symbolic_math` expressions.

    .. note::
        :mod:`krrood.symbolic_math` is imported lazily so that importing the Entity Query Language
        never requires ``casadi``; the dependency is only needed when this backend is actually used.
    """

    def _prepare_operands_(self, operands: Tuple[Any, ...]) -> Tuple[Any, ...]:
        from krrood.symbolic_math.symbolic_math import Scalar

        first, *rest = operands
        return Scalar(first), *rest


def math_operations_for(backend: MathBackend) -> MathOperations:
    """
    Resolve the math-operations backend for the given selection.

    :param backend: The configured backend.
    :return: The matching :class:`MathOperations` implementation.
    """
    if backend is MathBackend.SYMBOLIC:
        return SymbolicMathOperations()
    return PythonMathOperations()
