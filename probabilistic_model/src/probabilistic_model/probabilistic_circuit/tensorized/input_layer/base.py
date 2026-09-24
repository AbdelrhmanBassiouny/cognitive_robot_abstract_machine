from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from random_events.interval import Interval
from random_events.product_algebra import Event, SimpleEvent, VariableMap
from random_events.sigma_algebra import AbstractCompositeSet
from random_events.variable import Variable
from sortedcontainers import SortedSet
from typing_extensions import (
    Any,
    Dict,
    List,
    Optional,
    Self,
    Tuple,
    Type,
)

from probabilistic_model.distributions.distributions import UnivariateDistribution
from probabilistic_model.probabilistic_circuit.tensorized.forward_sample_assignment import (
    ForwardSampleAssignment,
)
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import Layer
from probabilistic_model.probabilistic_circuit.tensorized.query_cache import (
    QueryCache,
    memoized,
)


@dataclass(eq=False, repr=False)
class InputLayer(Layer, ABC):
    """
    Abstract base class for the input layers of a layered circuit.

    An input layer holds univariate distributions of one single type over one single
    variable, so that the likelihood of all of its nodes is evaluated without any
    branching.
    """

    variable: int
    """
    The index of the variable of this layer.
    """

    def __post_init__(self):
        self.variable = int(self.variable)

    @property
    def child_layers(self) -> List[Layer]:
        """
        :return: An empty list. An input layer is a leaf of the layer graph.
        """
        return []

    @property
    def variables(self) -> npt.NDArray:
        return np.array([self.variable], dtype=np.int64)

    @memoized
    def remap_variables(self, remap: npt.NDArray, cache: Optional[QueryCache] = None):
        self.variable = int(remap[self.variable])

    def column_of(self, x: npt.NDArray) -> npt.NDArray:
        """
        Select the column of the variable of this layer from an event array.

        :param x: The events with shape (#events, #variables of the circuit).
        :return: The column of this layer's variable.
        """
        return x[:, self.variable]

    # %% per node view

    @abstractmethod
    def node_distribution(
        self, index: int, variable: Variable
    ) -> UnivariateDistribution:
        """
        Materialize one node of this layer as a univariate distribution.

        :param index: The index of the node.
        :param variable: The variable of this layer.
        :return: The distribution of that node.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_distributions(
        cls, variable_index: int, distributions: List[UnivariateDistribution]
    ) -> Self:
        """
        Create a layer from a list of distributions of the type of this layer.

        :param variable_index: The index of the variable of the distributions.
        :param distributions: The distributions.
        :return: The layer.
        """
        raise NotImplementedError

    @abstractmethod
    def select_nodes(self, mask: npt.NDArray) -> Self:
        """
        Create a layer that only holds the nodes selected by a mask.

        :param mask: A boolean mask over the nodes of this layer.
        :return: The reduced layer.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def concatenate(cls, layers: List[Self]) -> Self:
        """
        Join layers of this type over the same variable into one layer.

        The nodes keep the order of the layers, so the nodes of ``layers[k]`` occupy one
        contiguous block. Only layers that were truncated from the same layer are
        concatenated, which is why the shared parameters may be taken from the first one.

        :param layers: The layers to join.
        :return: The joined layer.
        """
        raise NotImplementedError

    def node_distributions(self, variable: Variable) -> List[UnivariateDistribution]:
        """
        :param variable: The variable of this layer.
        :return: Every node of this layer as a univariate distribution.
        """
        return [
            self.node_distribution(index, variable)
            for index in range(self.number_of_nodes)
        ]

    # %% queries

    @memoized
    def support_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> List[Event]:
        variable = variables[self.variable]
        return [
            distribution.support for distribution in self.node_distributions(variable)
        ]

    @memoized
    def log_mode_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> Tuple[List[Event], npt.NDArray]:
        variable = variables[self.variable]
        modes = [
            distribution.log_mode()
            for distribution in self.node_distributions(variable)
        ]
        return [mode for mode, _ in modes], np.array(
            [value for _, value in modes], dtype=float
        )

    @memoized
    def moment_of_nodes(
        self,
        order: npt.NDArray,
        center: npt.NDArray,
        requested: npt.NDArray,
        variables: SortedSet,
        cache: Optional[QueryCache] = None,
    ) -> npt.NDArray:
        result = np.zeros((self.number_of_nodes, len(order)))
        if not requested[self.variable]:
            return result
        result[:, self.variable] = self.moment_of_nodes_own(
            int(order[self.variable]),
            float(center[self.variable]),
            variables[self.variable],
        )
        return result

    def moment_of_nodes_own(
        self, order: int, center: float, variable: Variable
    ) -> npt.NDArray:
        """
        Calculate the moment of the variable of this layer for every node.

        The fallback evaluates the nodes one by one through their distributions. Layers
        whose moment has a closed form that numpy can evaluate for all nodes at once
        override this.

        :param order: The order of the moment.
        :param center: The center of the moment.
        :param variable: The variable of this layer.
        :return: The moments with shape (#nodes,).
        """
        order_map = VariableMap({variable: order})
        center_map = VariableMap({variable: center})
        return np.array(
            [
                distribution.moment(order_map, center_map)[variable]
                for distribution in self.node_distributions(variable)
            ],
            dtype=float,
        )

    def sample_forward(
        self,
        assignment: ForwardSampleAssignment,
        samples: npt.NDArray,
        variables: SortedSet,
    ):
        own_assignment = assignment.rows_of(self)
        for node, rows_of_node in enumerate(own_assignment):
            if not rows_of_node:
                continue
            rows = np.concatenate(rows_of_node)
            samples[rows, self.variable] = self.sample_of_node(
                node, len(rows), variables
            )

    def sample_of_node(
        self, node: int, amount: int, variables: SortedSet
    ) -> npt.NDArray:
        """
        Draw samples from a single node of this layer.

        :param node: The index of the node.
        :param amount: The number of samples.
        :param variables: The variables of the circuit.
        :return: The samples with shape (amount,).
        """
        distribution = self.node_distribution(node, variables[self.variable])
        return distribution.sample(amount)[:, 0]

    # %% structural

    @abstractmethod
    def log_truncated_of_assignment(
        self, assignment: AbstractCompositeSet, singleton_allowed: bool
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Truncate every node of this layer to the assignment of its variable at once.

        :param assignment: The assignment of the variable of this layer.
        :param singleton_allowed: Whether singletons are allowed.
        :return: The truncated layer, with as many nodes as this one, and the
            log-probabilities of its nodes.
        """
        raise NotImplementedError

    @abstractmethod
    def type_of_truncated_layer(
        self, assignment: AbstractCompositeSet, singleton_allowed: bool
    ) -> Type[Layer]:
        """
        :param assignment: The assignment of the variable of this layer.
        :param singleton_allowed: Whether singletons are allowed.
        :return: The type of the layer :meth:`log_truncated_of_assignment` returns for
            that assignment.
        """
        raise NotImplementedError

    @memoized
    def log_truncated_of_simple_event(
        self,
        event: SimpleEvent,
        variables: SortedSet,
        singleton_allowed: bool,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        layer, node_log_probabilities = self.log_truncated_of_assignment(
            event[variables[self.variable]], singleton_allowed
        )
        log_probabilities[id(layer)] = node_log_probabilities
        return layer, node_log_probabilities

    def can_truncate_in_one_batch(
        self, events: List[SimpleEvent], variables: SortedSet, singleton_allowed: bool
    ) -> bool:
        """
        The truncations to the events are joined with :meth:`concatenate`, which needs
        them all to be input layers of one type.
        """
        variable = variables[self.variable]
        types = {
            self.type_of_truncated_layer(event[variable], singleton_allowed)
            for event in events
        }
        return len(types) == 1 and issubclass(types.pop(), InputLayer)

    @memoized
    def log_truncated_of_simple_events(
        self,
        events: List[SimpleEvent],
        variables: SortedSet,
        singleton_allowed: bool,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        variable = variables[self.variable]
        truncated = [
            self.log_truncated_of_assignment(event[variable], singleton_allowed)
            for event in events
        ]
        layers = [layer for layer, _ in truncated]
        layer = type(layers[0]).concatenate(layers)
        node_log_probabilities = np.concatenate(
            [log_probability for _, log_probability in truncated]
        )
        log_probabilities[id(layer)] = node_log_probabilities
        return layer, node_log_probabilities

    @abstractmethod
    def log_conditional_of_value(self, value: Any) -> Tuple[Layer, npt.NDArray]:
        """
        Condition every node of this layer on a value of its variable at once.

        :param value: The value.
        :return: The conditioned layer, with as many nodes as this one, and the
            log-likelihoods of the value under its nodes.
        """
        raise NotImplementedError

    @memoized
    def log_conditional_of_point(
        self,
        point: Dict[Variable, Any],
        variables: SortedSet,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        variable = variables[self.variable]
        if variable not in point:
            layer = self.__deepcopy__()
            node_log_probabilities = np.zeros(self.number_of_nodes)
        else:
            layer, node_log_probabilities = self.log_conditional_of_value(
                point[variable]
            )
        log_probabilities[id(layer)] = node_log_probabilities
        return layer, node_log_probabilities

    def rebuild(
        self,
        needed: Dict[int, npt.NDArray],
        rebuilt: Dict[int, Optional[Layer]],
    ) -> Optional[Layer]:
        alive = needed[id(self)]
        if not alive.any():
            return None
        return self.select_nodes(alive)

    def marginal(
        self, kept: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> Optional[Layer]:
        if not kept[self.variable]:
            return None
        return self.__deepcopy__()


@dataclass(eq=False, repr=False)
class AbstractContinuousLayer(InputLayer, ABC):
    """
    Abstract base class for the input layers of continuous univariate distributions.
    """

    @memoized
    def log_likelihood_of_nodes(
        self, x: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        return self.log_likelihood_of_nodes_from_column(self.column_of(x))

    @abstractmethod
    def log_likelihood_of_nodes_from_column(self, x: npt.NDArray) -> npt.NDArray:
        """
        Calculate the log-likelihood of every node for a column of values of the
        variable of this layer.

        :param x: The values with shape (#events,).
        :return: The log-likelihoods with shape (#events, #nodes).
        """
        raise NotImplementedError

    @memoized
    def probability_of_simple_event_of_nodes(
        self,
        event: SimpleEvent,
        variables: SortedSet,
        cache: Optional[QueryCache] = None,
    ) -> npt.NDArray:
        interval: Interval = event[variables[self.variable]]
        result = np.zeros(self.number_of_nodes)
        for simple_interval in interval.simple_sets:
            values = self.cumulative_distribution_of_nodes_from_column(
                np.array([simple_interval.lower, simple_interval.upper], dtype=float)
            )
            result += values[1] - values[0]
        return result

    @memoized
    def cumulative_distribution_of_nodes(
        self, x: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        return self.cumulative_distribution_of_nodes_from_column(self.column_of(x))

    @abstractmethod
    def cumulative_distribution_of_nodes_from_column(
        self, x: npt.NDArray
    ) -> npt.NDArray:
        """
        Calculate the cumulative distribution function of every node for a column of
        values of the variable of this layer.

        :param x: The values with shape (#events,).
        :return: The values with shape (#events, #nodes).
        """
        raise NotImplementedError
