from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from random_events.interval import Bound, Interval
from random_events.variable import Variable
from sortedcontainers import SortedSet
from typing_extensions import List, Self, Tuple, Type

from probabilistic_model.distributions.distributions import DiracDeltaDistribution
from probabilistic_model.exceptions import ShapeMismatchError
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import Layer
from probabilistic_model.probabilistic_circuit.tensorized.input_layer.base import (
    AbstractContinuousLayer,
)


@dataclass(eq=False, repr=False)
class DiracDeltaLayer(AbstractContinuousLayer[DiracDeltaDistribution]):
    """
    A layer of Dirac delta distributions over one continuous variable.
    """

    location: npt.NDArray
    """
    The location of every node.
    """

    density_cap: npt.NDArray
    """
    The value that replaces the infinite density of every node.
    """

    tolerance: float = 1e-6
    """
    The tolerance with which a value is considered equal to the location.
    """

    def __post_init__(self):
        super().__post_init__()
        self.location = np.asarray(self.location, dtype=float).reshape(-1)
        self.density_cap = np.asarray(self.density_cap, dtype=float).reshape(-1)

    @property
    def number_of_nodes(self) -> int:
        return len(self.location)

    @property
    def number_of_own_parameters(self) -> int:
        return 2 * self.number_of_nodes

    def validate_own(self):
        if self.location.shape != self.density_cap.shape:
            raise ShapeMismatchError(self.location.shape, self.density_cap.shape)

    def node_distribution(
        self, index: int, variable: Variable
    ) -> DiracDeltaDistribution:
        return DiracDeltaDistribution(
            variable=variable,
            location=float(self.location[index]),
            density_cap=float(self.density_cap[index]),
            tolerance=self.tolerance,
        )

    @classmethod
    def from_distributions(
        cls, variable_index: int, distributions: List[DiracDeltaDistribution]
    ) -> Self:
        return cls(
            variable_index,
            np.array([distribution.location for distribution in distributions]),
            np.array([distribution.density_cap for distribution in distributions]),
            distributions[0].tolerance,
        )

    def select_nodes(self, mask: npt.NDArray) -> Self:
        return self.__class__(
            self.variable, self.location[mask], self.density_cap[mask], self.tolerance
        )

    @classmethod
    def concatenate(cls, layers: List[Self]) -> Self:
        return cls(
            layers[0].variable,
            np.concatenate([layer.location for layer in layers]),
            np.concatenate([layer.density_cap for layer in layers]),
            layers[0].tolerance,
        )

    def log_likelihood_of_nodes_from_column(self, x: npt.NDArray) -> npt.NDArray:
        column = np.asarray(x, dtype=float).reshape(-1, 1)
        hit = np.abs(column - self.location) < self.tolerance
        with np.errstate(divide="ignore"):
            return np.where(hit, np.log(self.density_cap), -np.inf)

    def cumulative_distribution_of_nodes_from_column(
        self, x: npt.NDArray
    ) -> npt.NDArray:
        column = np.asarray(x, dtype=float).reshape(-1, 1)
        return (column >= self.location - self.tolerance).astype(float)

    def moment_of_nodes_own(
        self, order: int, center: float, variable: Variable
    ) -> npt.NDArray:
        if order == 0:
            return np.ones(self.number_of_nodes)
        if order == 1:
            return self.location - center
        return np.zeros(self.number_of_nodes)

    def sample_of_node(
        self, node: int, amount: int, variables: SortedSet
    ) -> npt.NDArray:
        return np.full(amount, self.location[node])

    def type_of_truncated_layer(
        self, assignment: Interval, singleton_allowed: bool
    ) -> Type[Layer]:
        return self.__class__

    def log_truncated_of_assignment(
        self, assignment: Interval, singleton_allowed: bool
    ) -> Tuple[DiracDeltaLayer, npt.NDArray]:
        """
        Truncating a Dirac delta either keeps it unchanged or makes it impossible, so
        the whole layer is truncated by testing which locations the assignment contains.
        """
        inside = np.zeros(self.number_of_nodes, dtype=bool)
        for interval in assignment.simple_sets:
            left = (
                interval.lower <= self.location
                if interval.left == Bound.CLOSED
                else interval.lower < self.location
            )
            right = (
                self.location <= interval.upper
                if interval.right == Bound.CLOSED
                else self.location < interval.upper
            )
            inside |= left & right

        return self.__deepcopy__(), np.where(inside, 0.0, -np.inf)

    def log_conditional_of_value(
        self, value: float
    ) -> Tuple[DiracDeltaLayer, npt.NDArray]:
        log_likelihood = self.log_likelihood_of_nodes_from_column(np.array([value]))[0]
        conditioned = self.__class__(
            self.variable,
            np.full(self.number_of_nodes, float(value)),
            self.density_cap.copy(),
            self.tolerance,
        )
        return conditioned, log_likelihood

    def apply_translation_own(self, translation: npt.NDArray):
        self.location = self.location + translation[self.variable]

    def apply_scaling_own(self, scaling: npt.NDArray):
        self.location = self.location * scaling[self.variable]

    def __deepcopy__(self, memo=None) -> DiracDeltaLayer:
        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]
        result = self.__class__(
            self.variable,
            self.location.copy(),
            self.density_cap.copy(),
            self.tolerance,
        )
        memo[id(self)] = result
        return result
