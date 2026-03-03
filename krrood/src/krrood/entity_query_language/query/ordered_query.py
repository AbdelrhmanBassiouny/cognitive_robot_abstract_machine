from __future__ import annotations

from dataclasses import dataclass, field
from typing_extensions import Optional, Callable, Iterator, Any

from krrood.entity_query_language.core.base_expressions import (
    BinaryExpression,
    DerivedExpression,
    Selectable,
    SymbolicExpression,
    Bindings,
    OperationResult,
)
from krrood.entity_query_language.query.query import Query


@dataclass(eq=False, repr=False)
class OrderedQuery(Query):
    """
    Represents an ordered by clause in a query. This orders the results of query according to the values of the
    specified variable.
    """

    expression_to_order: Selectable = field(kw_only=True)
    """
    The expression that will have its results ordered.
    """
    ordered_by: Selectable = field(kw_only=True)
    """
    The variable to order by.
    """
    descending: bool = False
    """
    Whether to order the results in descending order.
    """
    key: Optional[Callable] = None
    """
    A function to extract the key from the variable value.
    """

    def _evaluate__(self, sources: Bindings) -> Iterator[OperationResult]:
        yield from sorted(
            self.query._evaluate_(sources, parent=self),
            key=self.apply_key,
            reverse=self.descending,
        )

    def apply_key(self, result: OperationResult) -> Any:
        """
        Apply the key function to the variable to extract the reference value to order the results by.
        """
        var = self.variable
        var_id = var._id_
        if var_id not in result.all_bindings:
            var_val_generator = var._evaluate_(result.all_bindings, self)
            variable_value = next(var_val_generator).value
            try:
                next(var_val_generator)
                raise ValueError(
                    f"Variable {var._name_} is not unique in the query result."
                )
            except StopIteration:
                pass
        else:
            variable_value = result.all_bindings[var_id]
        if self.key:
            return self.key(variable_value)
        else:
            return variable_value

    @property
    def _name_(self) -> str:
        return f"{self.__class__.__name__}({self.variable._name_})"
