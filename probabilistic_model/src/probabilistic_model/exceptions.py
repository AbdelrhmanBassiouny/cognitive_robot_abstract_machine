from __future__ import annotations
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from probabilistic_model.probabilistic_model import ProbabilisticModel


@dataclass
class IntractableError(DataclassException):
    """
    Exception raised when an inference is intractable for a model.

    For instance, the mode of a non-deterministic model.
    """

    model: ProbabilisticModel

    def error_message(self) -> str:
        return f"Inference is intractable for {self.model}."

    def suggest_correction(self) -> str:
        return ""


@dataclass
class UndefinedOperationError(DataclassException):
    """
    Exception raised when an operation is not defined for a model.

    For instance, invoking the CDF of a model that contains symbolic variables.
    """

    model: ProbabilisticModel

    def error_message(self) -> str:
        return f"Operation is not defined for {self.model}."

    def suggest_correction(self) -> str:
        return ""


@dataclass
class ShapeMismatchError(DataclassException, ValueError):
    """
    Exception raised when the shape of two objects does not match.
    """

    received_shape: Any
    """
    The first object to compare.
    """

    expected_shape: Any
    """
    The second object to compare.
    """

    def error_message(self) -> str:
        return f"Expected shape {self.expected_shape}, received shape {self.received_shape}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class NumberOfWeightsMismatchError(DataclassException, ValueError):
    """
    Exception raised when a mixture does not get exactly one weight per component.
    """

    number_of_weights: int
    """
    The number of weights given.
    """

    number_of_components: int
    """
    The number of components to mix.
    """

    def error_message(self) -> str:
        return (
            f"Got {self.number_of_weights} weights for "
            f"{self.number_of_components} components."
        )

    def suggest_correction(self) -> str:
        return "Pass exactly one weight per component."
