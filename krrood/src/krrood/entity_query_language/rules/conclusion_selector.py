"""
Conclusion selection operators for the Entity Query Language.

This module provides operators that control which conclusions from operands propagate, such as ExceptIf,
Alternative, and Next.
"""

from __future__ import annotations

import typing
from abc import ABC
from dataclasses import dataclass
from typing_extensions import Optional, Iterable

from .conclusion import Conclusion
from ..operators.set_operations import Union as EQLUnion
from ..operators.core_logical_operators import LogicalBinaryOperator, OR
from ..core.base_expressions import (
    Bindings,
    OperationResult,
    SymbolicExpression,
    TruthValueOperator,
)


@dataclass(eq=False)
class ConclusionSelector(TruthValueOperator, ABC):
    """
    Base class for operators that selects the conclusions to pass through from it's operands' conclusions.
    """


@dataclass(eq=False)
class ExceptIf(LogicalBinaryOperator, ConclusionSelector):
    """
    Conditional branch that yields left unless the right side produces values.

    This encodes an "except if" behavior: when the right condition matches,
    the left branch's conclusions/outputs are excluded; otherwise, left flows through.
    """

    def _evaluate__(
        self,
        sources: Optional[Bindings] = None,
    ) -> Iterable[OperationResult]:
        """
        Evaluate the ExceptIf condition and yield the results.
        """

        # constrain left values by available sources
        left_values = self.left._evaluate_(sources, parent=self)
        for left_value in left_values:

            self._is_false_ = left_value.is_false
            if self._is_false_:
                yield left_value
                continue

            right_yielded = False
            for right_value in self.right._evaluate_(left_value.bindings, parent=self):
                if right_value.is_false:
                    continue
                right_yielded = True
                yield from self.yield_and_update_conclusion(
                    right_value, self.right._conclusion_
                )
            if not right_yielded:
                yield from self.yield_and_update_conclusion(
                    left_value, self.left._conclusion_
                )

    def yield_and_update_conclusion(
        self, result: OperationResult, conclusion: typing.Set[Conclusion]
    ) -> Iterable[OperationResult]:
        self._conclusion_.update(conclusion)
        yield OperationResult(result.bindings, self._is_false_, self)
        self._conclusion_.clear()


@dataclass(eq=False)
class Alternative(OR, ConclusionSelector):
    """
    A conditional branch that behaves like an "else if" clause where the left branch
    is selected if it is true, otherwise the right branch is selected if it is true else
    none of the branches are selected.
    """

    def _evaluate__(
        self,
        sources: Bindings,
    ) -> Iterable[OperationResult]:
        for output in OR._evaluate__(self, sources):
            if output.is_true:
                self._conclusion_.update(
                    output.previous_operation_result.operand._conclusion_
                )
            yield output
            self._conclusion_.clear()


@dataclass(eq=False)
class Next(EQLUnion, ConclusionSelector):
    """
    A Union conclusion selector that always evaluates all its operands and combines their results.
    """

    def _evaluate__(
        self,
        sources: Bindings,
    ) -> Iterable[OperationResult]:
        for output in EQLUnion._evaluate__(self, sources):
            if output.is_true:
                self._conclusion_.update(
                    output.previous_operation_result.operand._conclusion_
                )
            yield output
            self._conclusion_.clear()

    def add_child(self, child: SymbolicExpression) -> None:
        """
        Adds a child operand to the union operator.

        :param child: The child operand to add.
        """
        self._operation_children_ = self._operation_children_ + (child,)
        child._parent_ = self
