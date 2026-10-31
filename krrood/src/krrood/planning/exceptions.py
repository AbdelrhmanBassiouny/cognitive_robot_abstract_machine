"""
Errors raised while building states.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any

from krrood.entity_query_language.ground_term import GroundTerm
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.exceptions import DataclassException

# %% facts


@dataclass
class ConditionIsNotAFact(DataclassException):
    """
    A condition that does not fix the value of a fluent was given as a fact.
    """

    condition: Any
    """
    The condition that was given.
    """

    def error_message(self) -> str:
        return f"{self.condition} does not fix the value of a fluent."

    def suggest_correction(self) -> str:
        return (
            "State a fact as 'expression == value' for an attribute, index or call, as a "
            "predicate for it to hold, or as not_(predicate) for it not to hold."
        )


@dataclass
class ComparisonIsNotAnEquality(ConditionIsNotAFact):
    """
    A fact compares a fluent by other than equality, which constrains its value without
    fixing it.
    """

    condition: Comparator
    """
    The comparison that was given.
    """

    def error_message(self) -> str:
        return (
            f"{self.condition} compares with '{self.condition._name_}', which does not "
            "fix the value of the fluent; only '==' does."
        )

    def suggest_correction(self) -> str:
        return (
            "Compare the fluent with '==' to give it a value. To state that the "
            "comparison holds, write it as the body of a predicate and state the "
            "predicate: that assigns the predicate itself, not the values it compares."
        )


@dataclass
class FactValueIsNotConstant(DataclassException):
    """
    A fact compares a fluent with an expression instead of with a value.
    """

    condition: Any
    """
    The fact whose value is an expression.
    """

    def error_message(self) -> str:
        return f"The value {self.condition} gives its fluent is not a constant."

    def suggest_correction(self) -> str:
        return "Compare the fluent with a plain value."


@dataclass
class MissingFluent(DataclassException):
    """
    A fact gives a value to a fluent that does not exist, such as an attribute the
    instance does not have.
    """

    term: GroundTerm
    """
    The fluent that does not exist.
    """

    def error_message(self) -> str:
        return f"{self.term} has no value, so a fact cannot assign it."

    def suggest_correction(self) -> str:
        return "Assign only attributes the instance has and keys the container stores."
