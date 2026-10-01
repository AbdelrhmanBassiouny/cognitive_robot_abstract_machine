"""
Values that are no expression themselves but take the place of one, each through an
extension point the language states as an interface rather than as a list of the kinds
it already knows.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, Type

from krrood.entity_query_language.core.base_expressions import (
    MatchAssignedValue,
    Operand,
    SymbolicExpression,
)
from krrood.entity_query_language.core.mapped_variable import (
    CanBehaveLikeAVariable,
    HasSymbolicOperations,
)


@dataclass(eq=False)
class ExpressionStandIn(Operand):
    """
    A value that contributes a given expression wherever an operand is expected.
    """

    expression: SymbolicExpression
    """
    The expression this contributes.
    """

    @property
    def _symbolic_expression_(self) -> SymbolicExpression:
        return self.expression


@dataclass(eq=False)
class AssignedVariableStandIn(MatchAssignedValue):
    """
    A value that, assigned to an attribute in a match pattern, stands for a given
    variable, and records the type of the attribute it was assigned to.
    """

    variable: SymbolicExpression
    """
    The variable this stands for in the pattern.
    """

    attribute_type: Optional[Type] = None
    """
    The type of the attribute this was last assigned to.
    """

    def _as_assigned_variable_(
        self, attribute_type: Optional[Type]
    ) -> SymbolicExpression:
        self.attribute_type = attribute_type
        return self.variable


@dataclass(eq=False)
class ValueStandInWithUnreadableProperty(HasSymbolicOperations[int]):
    """
    A value that builds its symbolic operations on a given variable, and declares a
    property whose value cannot be read.
    """

    variable: CanBehaveLikeAVariable[int]
    """
    The variable every symbolic operation on this is built on.
    """

    @property
    def _symbolic_expression_(self) -> CanBehaveLikeAVariable[int]:
        return self.variable

    @property
    def _type_(self) -> Type[int]:
        return int

    @property
    def _unreadable_(self) -> int:
        """
        A property of this stand-in that fails to produce its value.
        """
        raise AttributeError("the value this property reads is missing")
