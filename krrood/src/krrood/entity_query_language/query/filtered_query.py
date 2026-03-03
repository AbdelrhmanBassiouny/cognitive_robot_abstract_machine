from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Iterable

from krrood.entity_query_language.core.base_expressions import (
    TruthValueOperator,
    SymbolicExpression,
    UnaryExpression,
    Bindings,
    OperationResult,
    BinaryExpression,
)
from krrood.entity_query_language.query.grouped_query import GroupedQuery
from krrood.entity_query_language.query.query import Query


@dataclass(eq=False, repr=False)
class FilteredQuery(Query, TruthValueOperator, ABC):
    """
    Data source that evaluates the truth value for each data point according to a condition expression and filters out
    the data points that do not satisfy the condition.
    """

    query: Query = field(kw_only=True)
    """
    The query that will be filtered.
    """

    condition: SymbolicExpression = field(kw_only=True)
    """
    The conditions expression that generates the valid bindings that satisfy the constraints.
    """

    def _evaluate__(
        self,
        sources: Bindings,
    ) -> Iterable[OperationResult]:
        yield from (
            OperationResult(
                result.bindings | truth_annotated_result.bindings,
                self._is_false_,
                self,
            )
            for result in self.query._evaluate_(sources, parent=self)
            for truth_annotated_result in self.condition._evaluate_(
                result.bindings, parent=self
            )
            if truth_annotated_result.is_true
        )

    @property
    def _name_(self):
        return self.__class__.__name__


@dataclass(eq=False, repr=False)
class Where(FilteredQuery):
    """
    A symbolic expression that represents the `where()` statement of `Query`. It is used to filter
    ungrouped data.
    """


@dataclass(eq=False, repr=False)
class Having(FilteredQuery):
    """
    A symbolic having expression that can be used to filter the grouped results of a query.
    Is constructed through the `QueryObjectDescriptor` using the `having()` method.
    """

    query: GroupedQuery
    """
    The grouped by expression that is used to group the results of the query. As the results need to be grouped before
     filtering using `Having`.
    """
