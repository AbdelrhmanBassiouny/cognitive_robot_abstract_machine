from __future__ import annotations

from dataclasses import dataclass

import numpy.typing as npt
from typing_extensions import TYPE_CHECKING, List, Type

from krrood.exceptions import DataclassException

if TYPE_CHECKING:
    from random_events.variable import Variable


@dataclass
class CircuitNotFittedError(DataclassException):
    """
    Raised when a RelationalProbabilisticCircuit is grounded before it has been fitted.
    """

    class_: Type
    """
    The domain class whose relational circuit has not been fitted yet.
    """

    def error_message(self) -> str:
        return (
            f"RelationalProbabilisticCircuit for {self.class_.__name__} must be fitted "
            f"before it can be grounded."
        )

    def suggest_correction(self) -> str:
        return "Call `fit` with training instances before calling `ground`."


@dataclass
class InvalidMonteCarloSampleCountError(DataclassException):
    """
    Raised when grounding must integrate out undetermined aggregation statistics but the
    configured Monte-Carlo sample count is not positive.
    """

    sample_count: int
    """
    The invalid, non-positive sample count.
    """

    def error_message(self) -> str:
        return (
            f"Integrating out undetermined aggregation statistics requires a positive "
            f"Monte-Carlo sample count, but got {self.sample_count}."
        )

    def suggest_correction(self) -> str:
        return "Set `monte_carlo_sample_count` to a positive integer."


@dataclass
class UndeterminedLatentsNotModeledError(DataclassException):
    """
    Raised when the conditioned class circuit does not model the undetermined
    aggregation statistics, so they cannot be sampled and integrated out.
    """

    undetermined_latents: List[Variable]
    """
    The undetermined latent variables that the conditioned circuit fails to model.
    """

    def error_message(self) -> str:
        names = ", ".join(latent.name for latent in self.undetermined_latents)
        return (
            f"The conditioned class circuit does not model the undetermined "
            f"aggregation statistics [{names}], so they cannot be integrated out."
        )

    def suggest_correction(self) -> str:
        return (
            "Ensure the class circuit is fitted with these aggregation statistics "
            "as latent variables before grounding."
        )


@dataclass
class NotAProbabilityDistributionError(DataclassException):
    """
    Raised when an array meant to hold a probability distribution has negative entries,
    or does not sum to 1 along its last axis.
    """

    name: str
    """
    The name of the invalid field (e.g. ``"starting_distribution"``).
    """

    values: npt.NDArray
    """
    The offending array.
    """

    def error_message(self) -> str:
        return (
            f"{self.name} is not a valid probability distribution: every entry must "
            f"be non-negative and it must sum to 1 along its last axis, but got "
            f"{self.values}."
        )

    def suggest_correction(self) -> str:
        return f"Ensure {self.name} contains non-negative entries summing to 1."


@dataclass
class EmptyMarkovChainError(DataclassException):
    """
    Raised when a ``MarkovChainDistributionTemplate`` is grounded with no parts.
    """

    def error_message(self) -> str:
        return "Cannot ground a Markov chain template with zero parts."

    def suggest_correction(self) -> str:
        return "Pass at least one part to `ground`."
