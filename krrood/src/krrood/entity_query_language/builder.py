from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing_extensions import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.query.query import Query


@dataclass
class ExpressionBuilder(ABC):
    """
    Base class for builder classes of symbolic expressions. This class collects meta-data about expressions to finally
    build the expression.
    """

    _built_expression: Optional[SymbolicExpression] = field(init=False, default=None)
    """
    The expression that is built from the metadata.
    """

    @property
    def expression(self) -> SymbolicExpression:
        """
        :return: The expression that is built from the metadata.
        """
        if self._built_expression is not None:
            return self._built_expression
        self._built_expression = self.build()
        return self._built_expression

    @abstractmethod
    def build(self) -> SymbolicExpression:
        """
        :return: The expression that is built from the metadata.
        """
        ...

    def __hash__(self) -> int:
        return hash((self.__class__, self.query))
