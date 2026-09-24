from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from random_events.interval import Bound, Interval, SimpleInterval
from typing_extensions import Dict, List, Optional, Self, Tuple, Type

from probabilistic_model.exceptions import ShapeMismatchError
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import Layer
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.sum_layer import (
    SumLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.input_layer.base import (
    AbstractContinuousLayer,
    InputLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.row_grouped_sparse_array import (
    RowGroupedSparseArray,
)
from probabilistic_model.probabilistic_circuit.tensorized.input_layer.dirac_delta_layer import (
    DiracDeltaLayer,
)


@dataclass(eq=False, repr=False)
class ContinuousLayerWithDensity(AbstractContinuousLayer, ABC):
    """
    Abstract base class for the input layers of continuous distributions that have a
    density.

    A node of such a layer truncated to a composite interval becomes a mixture of its
    truncations to the simple intervals, and a node conditioned on a value or truncated
    to a singleton becomes a Dirac delta.
    """

    @abstractmethod
    def log_truncated_of_non_singleton_interval(
        self, interval: SimpleInterval
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Truncate every node of this layer to a simple interval that is not a singleton.

        :param interval: The simple interval.
        :return: The truncated layer and the log-probabilities of its nodes.
        """
        raise NotImplementedError

    def type_of_layer_truncated_to_interval(
        self, interval: SimpleInterval
    ) -> Type[Layer]:
        """
        :param interval: A simple interval that is not a singleton.
        :return: The type of the layer :meth:`log_truncated_of_non_singleton_interval`
            returns for that interval.
        """
        return self.__class__

    def type_of_truncated_layer(
        self, assignment: Interval, singleton_allowed: bool
    ) -> Type[Layer]:
        if len(assignment.simple_sets) > 1:
            return SumLayer
        if not assignment.simple_sets:
            return self.__class__
        [interval] = assignment.simple_sets
        if singleton_allowed and interval.is_singleton():
            return DiracDeltaLayer
        return self.type_of_layer_truncated_to_interval(interval)

    def log_truncated_of_assignment(
        self, assignment: Interval, singleton_allowed: bool
    ) -> Tuple[Layer, npt.NDArray]:
        pieces = [
            self.log_truncated_of_simple_interval(interval, singleton_allowed)
            for interval in assignment.simple_sets
        ]
        if not pieces:
            return self.__deepcopy__(), np.full(self.number_of_nodes, -np.inf)
        if len(pieces) == 1:
            return pieces[0]
        return self.mixture_of_pieces(pieces)

    def log_truncated_of_simple_interval(
        self, interval: SimpleInterval, singleton_allowed: bool
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Truncate every node of this layer to a simple interval.

        :param interval: The simple interval.
        :param singleton_allowed: Whether a singleton interval truncates to a Dirac delta
            rather than to an impossible node.
        :return: The truncated layer and the log-probabilities of its nodes.
        """
        if not (singleton_allowed and interval.is_singleton()):
            return self.log_truncated_of_non_singleton_interval(interval)
        log_likelihood = self.log_likelihood_of_nodes_from_column(
            np.array([interval.lower])
        )[0]
        dirac_delta_layer = DiracDeltaLayer(
            self.variable,
            np.full(self.number_of_nodes, float(interval.lower)),
            np.ones(self.number_of_nodes),
        )
        return dirac_delta_layer, log_likelihood

    def mixture_of_pieces(
        self, pieces: List[Tuple[Layer, npt.NDArray]]
    ) -> Tuple[SumLayer, npt.NDArray]:
        """
        Mix the truncations of this layer to the simple intervals of a composite
        interval.

        Node ``i`` of the result mixes node ``i`` of every piece, weighted by the
        probability of that piece. Pieces of the same type are joined into one child
        layer, so the number of layers does not grow with the number of simple
        intervals.

        :param pieces: The truncated layer and the log-probabilities of its nodes, per
            simple interval.
        :return: The mixture and the log-probabilities of its nodes.
        """
        number_of_nodes = self.number_of_nodes
        pieces_by_type: Dict[Type[Layer], List[Tuple[InputLayer, npt.NDArray]]] = {}
        for layer, log_probabilities in pieces:
            pieces_by_type.setdefault(type(layer), []).append(
                (layer, log_probabilities)
            )

        child_layers = []
        log_probabilities_per_child_layer = []
        for layer_type, typed_pieces in pieces_by_type.items():
            child_layers.append(
                layer_type.concatenate([layer for layer, _ in typed_pieces])
            )
            log_probabilities_per_child_layer.extend(
                log_probabilities for _, log_probabilities in typed_pieces
            )

        # the pieces are the columns in order, and node i of every piece sits in row i
        number_of_pieces = len(pieces)
        log_weights = RowGroupedSparseArray.from_coordinates(
            np.concatenate(log_probabilities_per_child_layer),
            np.tile(np.arange(number_of_nodes), number_of_pieces),
            np.arange(number_of_pieces * number_of_nodes),
            (number_of_nodes, number_of_pieces * number_of_nodes),
        )

        node_log_probabilities = np.logaddexp.reduce(
            [log_probabilities for _, log_probabilities in pieces], axis=0
        )
        return SumLayer(child_layers, log_weights), node_log_probabilities

    def log_conditional_of_value(
        self, value: float
    ) -> Tuple[DiracDeltaLayer, npt.NDArray]:
        log_likelihood = self.log_likelihood_of_nodes_from_column(np.array([value]))[0]
        dirac_delta_layer = DiracDeltaLayer(
            self.variable,
            np.full(self.number_of_nodes, float(value)),
            np.exp(log_likelihood),
        )
        return dirac_delta_layer, log_likelihood


@dataclass(eq=False, repr=False)
class ContinuousLayerWithFiniteSupport(ContinuousLayerWithDensity, ABC):
    """
    Abstract base class for continuous input layers whose nodes have a finite support.
    """

    interval: npt.NDArray
    """
    The support of every node as an array of shape (#nodes, 2).

    The first column holds the lower bounds, the second the upper bounds.
    """

    # keyword-only so that a subclass can add required positional fields (such as
    # location and scale) after ``interval`` without violating dataclass field
    # ordering, which does not allow a required field to follow one that has a default
    bounds: Optional[npt.NDArray] = field(default=None, kw_only=True)
    """
    The kind of every bound as an array of shape (#nodes, 2) holding
    :class:`random_events.interval.Bound` values.

    Keeping the kind of every bound, rather than treating every interval as open, lets
    a layer describe exactly the same support as the distributions it was created from.
    """

    def __post_init__(self):
        super().__post_init__()
        self.interval = np.asarray(self.interval, dtype=float).reshape(-1, 2)
        if self.bounds is None:
            self.bounds = np.full(self.interval.shape, int(Bound.OPEN), dtype=np.int64)
        self.bounds = np.asarray(self.bounds, dtype=np.int64).reshape(-1, 2)

    @property
    def lower(self) -> npt.NDArray:
        """
        :return: The lower bounds of the supports of the nodes.
        """
        return self.interval[:, 0]

    @property
    def upper(self) -> npt.NDArray:
        """
        :return: The upper bounds of the supports of the nodes.
        """
        return self.interval[:, 1]

    @property
    def left_closed(self) -> npt.NDArray:
        """
        :return: Whether the lower bound of every node is included.
        """
        return self.bounds[:, 0] == int(Bound.CLOSED)

    @property
    def right_closed(self) -> npt.NDArray:
        """
        :return: Whether the upper bound of every node is included.
        """
        return self.bounds[:, 1] == int(Bound.CLOSED)

    @property
    def number_of_nodes(self) -> int:
        return len(self.interval)

    def simple_interval_of(self, index: int) -> SimpleInterval:
        """
        :param index: The index of a node.
        :return: The support of that node as simple interval.
        """
        return SimpleInterval.from_data(
            float(self.interval[index, 0]),
            float(self.interval[index, 1]),
            Bound(int(self.bounds[index, 0])),
            Bound(int(self.bounds[index, 1])),
        )

    def validate_own(self):
        if self.interval.shape != self.bounds.shape:
            raise ShapeMismatchError(self.interval.shape, self.bounds.shape)

    def included_condition(self, x: npt.NDArray) -> npt.NDArray:
        """
        Check whether values lie inside the support of every node.

        :param x: The values with shape (#events,).
        :return: A boolean array of shape (#events, #nodes).
        """
        column = np.asarray(x, dtype=float).reshape(-1, 1)

        # these arrays hold one entry per event per node, so the homogeneous cases get
        # their own path rather than evaluating both comparisons and selecting between
        # them
        left_closed = self.left_closed
        if left_closed.all():
            left = self.lower <= column
        elif not left_closed.any():
            left = self.lower < column
        else:
            left = np.where(left_closed, self.lower <= column, self.lower < column)

        right_closed = self.right_closed
        if right_closed.all():
            right = column <= self.upper
        elif not right_closed.any():
            right = column < self.upper
        else:
            right = np.where(right_closed, column <= self.upper, column < self.upper)

        return left & right

    def select_nodes(self, mask: npt.NDArray) -> Self:
        return self.__class__(
            self.variable, self.interval[mask], bounds=self.bounds[mask]
        )

    @classmethod
    def concatenate(cls, layers: List[Self]) -> Self:
        return cls(
            layers[0].variable,
            np.concatenate([layer.interval for layer in layers]),
            bounds=np.concatenate([layer.bounds for layer in layers]),
        )

    def apply_translation_own(self, translation: npt.NDArray):
        self.interval = self.interval + translation[self.variable]

    def apply_scaling_own(self, scaling: npt.NDArray):
        self.interval = self.interval * scaling[self.variable]

    def __deepcopy__(self, memo=None) -> Self:
        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]
        result = self.__class__(
            self.variable, self.interval.copy(), bounds=self.bounds.copy()
        )
        memo[id(self)] = result
        return result
