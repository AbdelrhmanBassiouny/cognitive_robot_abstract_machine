"""
This module defines some custom exception types used by the entity_query_language package.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field

from typing_extensions import TYPE_CHECKING, Type, Any, List

from ..utils import DataclassException

if TYPE_CHECKING:
    from .symbolic import (
        SymbolicExpression,
        ResultQuantifier,
        Variable,
        Selectable,
        QueryObjectDescriptor,
        Aggregator,
    )
    from .match import Match


@dataclass
class QuantificationNotSatisfiedError(DataclassException, ABC):
    """
    Represents a custom exception where the quantification constraints are not satisfied.

    This exception is used to indicate errors related to the quantification
    of the query results.
    """

    expression: ResultQuantifier
    """
    The result quantifier expression where the error occurred.
    """
    expected_number: int
    """
    Expected number of solutions (i.e, quantification constraint value).
    """


@dataclass
class GreaterThanExpectedNumberOfSolutions(QuantificationNotSatisfiedError):
    """
    Represents an error when the number of solutions exceeds the
    expected threshold.
    """

    def __post_init__(self):
        self.message = f"More than {self.expected_number} solutions found for the expression {self.expression}."
        super().__post_init__()


@dataclass
class LessThanExpectedNumberOfSolutions(QuantificationNotSatisfiedError):
    """
    Represents an error that occurs when the number of solutions found
    is lower than the expected number.
    """

    found_number: int
    """
    The number of solutions found.
    """

    def __post_init__(self):
        self.message = (
            f"Found {self.found_number} solutions which is less than the expected {self.expected_number} "
            f"solutions for the expression {self.expression}."
        )
        super().__post_init__()


@dataclass
class MultipleSolutionFound(GreaterThanExpectedNumberOfSolutions):
    """
    Raised when a query unexpectedly yields more than one solution where a single
    result was expected.
    """

    expected_number: int = 1


@dataclass
class NoSolutionFound(LessThanExpectedNumberOfSolutions):
    """
    Raised when a query does not yield any solution.
    """

    expected_number: int = 1
    found_number: int = 0


@dataclass
class LogicalError(DataclassException):
    """
    Raised when there is an error in the logical structure/evaluation of the query.
    """


@dataclass
class VariableCannotBeEvaluated(DataclassException):
    """
    Raised when a variable cannot be evaluated due to missing or invalid information in the variable.
    """

    variable: Variable

    def __post_init__(self):
        self.message = (
            f"Variable {self.variable} cannot be evaluated because of missing or invalid information."
            f"The variable couldn't be identified as one of (already bound, has a domain, or is inferred,"
            f"Check that the variable is correctly defined and that all required information is provided."
        )
        super().__post_init__()


@dataclass
class UsageError(DataclassException):
    """
    Raised when there is an incorrect usage of the entity query language API.
    """

    ...


@dataclass
class NoConditionsProvidedToWhereStatementOfDescriptor(UsageError):
    """
    Raised when no conditions are provided to the where statement of a query descriptor.
    """

    descriptor: QueryObjectDescriptor
    """
    The query object descriptor that has no conditions in its where statement.
    """

    def __post_init__(self):
        self.message = f"No conditions were provided to the where statement of the descriptor {self.descriptor}"
        super().__post_init__()


@dataclass
class AggregationUsageError(UsageError): ...


@dataclass
class NonAggregatedSelectedVariablesError(AggregationUsageError):
    """
    Raised when a non-aggregated and not grouped_by variable(s) is selected along with an aggregated variable.
    """

    non_aggregated_variables: List[Selectable]
    """
    The non-aggregated selected variables.
    """
    aggregated_variables: List[Selectable]
    """
    The aggregated variables.
    """
    group_by_variables: List[Selectable] = field(default_factory=list)
    """
    The grouped by variables, if any.
    """

    def __post_init__(self):
        self.message = (
            f"The variabls {self.non_aggregated_variables} are neither aggregated nor grouped by, they cannot be selected"
            f"along with the aggregated variables {self.aggregated_variables}. You can only select variables that are"
            f" either aggregated or are in the grouped by variables {self.group_by_variables}."
        )
        super().__post_init__()


@dataclass
class AggregatorWithNonAggregatorInWhereConditionError(AggregationUsageError):
    """
    Raised when an aggregator is used in a where condition with non-aggregators.
    """

    descriptor: QueryObjectDescriptor
    """
    The query object descriptor that contains the aggregators and non-aggregators.
    """
    aggregators: List[Aggregator]
    """
    The aggregators in the where condition.
    """
    non_aggregators: List[Selectable]
    """
    The non-aggregators in the where condition.
    """

    def __post_init__(self):
        self.message = f"The where condition of the descriptor {self.descriptor} contains aggregators {self.aggregators} and non-aggregators {self.non_aggregators}."
        super().__post_init__()


@dataclass
class NoKwargsInMatchVar(UsageError):
    """
    Raised when a match_variable is used without any keyword arguments.
    """

    match_variable: Match

    def __post_init__(self):
        self.message = (
            f"The match variable {self.match_variable} was used without any keyword arguments."
            f"If you don't want to specify keyword arguments use variable() instead"
        )
        super().__post_init__()


@dataclass
class WrongSelectableType(UsageError):
    """
    Raised when a wrong variable type is given to the select() statement.
    """

    wrong_variable_type: Type
    expected_types: List[Type]

    def __post_init__(self):
        self.message = f"Select expects one of {self.expected_types}, instead {self.wrong_variable_type} was given."
        super().__post_init__()


@dataclass
class LiteralConditionError(UsageError):
    """
    Raised when a literal (i.e. a non-variable) condition is given to the query.
    Example:
        >>> a = True
        >>> body = let(Body, None)
        >>> query = an(entity(body, a))
    This could also happen when you are using a predicate or a symbolic_function and all the given arguments are literals.
    Example:
        >>> predicate = HasType(Body("Body1"), Body)
        >>> query = an(entity(let(Body, None), predicate))
    So make sure that at least one of the arguments to the predicate or symbolic function are variables.
    """

    query_descriptor: QueryObjectDescriptor
    """
    The query object descriptor that contains the literal condition.
    """
    literal_conditions: List[Any]
    """
    The literal conditions that are given to the query.
    """

    def __post_init__(self):
        self.message = (
            f"The following Literal {self.literal_conditions} was given to the descriptor {self.query_descriptor}."
            f"Literal conditions are not allowed in queries, as they are always"
            f"either True or False, independent on any other values/bindings in the query"
        )
        super().__post_init__()


@dataclass
class CannotProcessResultOfGivenChildType(UsageError):
    """
    Raised when the entity query language API cannot process the results of a given child type during evaluation.
    """

    unsupported_child_type: Type
    """
    The unsupported child type.
    """

    def __post_init__(self):
        self.message = (
            f"The child type {self.unsupported_child_type} cannot have its results processed"
            f" during evaluation because it doesn't implement the `_process_result_` method."
        )
        super().__post_init__()


@dataclass
class NonPositiveLimitValue(UsageError):
    """
    Raised when a limit value for the query results is not positive.
    """

    wrong_limit_value: int

    def __post_init__(self):
        self.message = (
            f"Quantifier limit value must be a positive integer (i.e., greater than 0),"
            f" instead got {self.wrong_limit_value}"
        )
        super().__post_init__()


@dataclass
class UnsupportedOperation(UsageError):
    """
    Raised when an operation is not supported by the entity query language API.
    """

    ...


@dataclass
class UnSupportedOperand(UnsupportedOperation):
    """
    Raised when an operand is not supported by the operation.
    """

    operation: Type[SymbolicExpression]
    """
    The operation used.
    """
    unsupported_operand: Any
    """
    The operand that is not supported by the operation.
    """

    def __post_init__(self):
        self.message = f"{self.unsupported_operand} cannot be used as an operand for {self.operation} operations."
        super().__post_init__()


@dataclass
class UnsupportedNegation(UnsupportedOperation):
    """
    Raised when negating quantifiers.
    """

    operation_type: Type[SymbolicExpression]
    """
    The type of the operation that is being negated.
    """

    def __post_init__(self):
        self.message = (
            f"Symbolic NOT operations on {self.operation_type} types"
            f" operands are not allowed, you can negate the conditions instead,"
            f" as negating them is most likely not what you want"
            f" because it is ambiguous and can be very expensive to compute."
            f"To Negate Conditions do:"
            f" `not_(condition)` instead of `not_(an(entity(..., condition)))`."
        )
        super().__post_init__()


@dataclass
class QuantificationSpecificationError(UsageError):
    """
    Raised when the quantification constraints specified on the query results are invalid or inconsistent.
    """


@dataclass
class QuantificationConsistencyError(QuantificationSpecificationError):
    """
    Raised when the quantification constraints specified on the query results are inconsistent.
    """

    ...


@dataclass
class NegativeQuantificationError(QuantificationConsistencyError):
    """
    Raised when the quantification constraints specified on the query results have a negative value.
    """

    message: str = f"ResultQuantificationConstraint must be a non-negative integer."


@dataclass
class InvalidChildType(UsageError):
    """
    Raised when an invalid entity type is given to the quantification operation.
    """

    invalid_child_type: Type
    """
    The invalid child type.
    """
    correct_child_types: List[Type]
    """
    The list of valid child types.
    """

    def __post_init__(self):
        self.message = f"The child type {self.invalid_child_type} is not valid. It must be a subclass of {self.correct_child_types}"
        super().__post_init__()


@dataclass
class InvalidEntityType(InvalidChildType):
    """
    Raised when an invalid entity type is given to the quantification operation.
    """

    ...


@dataclass
class ClassDiagramError(DataclassException):
    """
    An error related to the class diagram.
    """


@dataclass
class NoneWrappedFieldError(ClassDiagramError):
    """
    Raised when a field of a class is not wrapped by a WrappedField.
    """

    clazz: Type
    attr_name: str

    def __post_init__(self):
        self.message = f"Field '{self.attr_name}' of class '{self.clazz.__name__}' is not wrapped by a WrappedField."
        super().__post_init__()
