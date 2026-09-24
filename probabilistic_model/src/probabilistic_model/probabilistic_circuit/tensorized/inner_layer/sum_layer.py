from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from random_events.product_algebra import Event, SimpleEvent
from random_events.variable import Variable
from scipy.sparse import coo_array
from sortedcontainers import SortedSet
from typing_extensions import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
)

from probabilistic_model.exceptions import ShapeMismatchError
from probabilistic_model.probabilistic_circuit.tensorized.utils import (
    embedded_logsumexp,
    remap_indices,
)
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import (
    Edge,
    ForwardSampleAssignment,
    InnerLayer,
    Layer,
    QueryCache,
    memoized,
)


@dataclass(eq=False, repr=False)
class SumLayer(InnerLayer):
    """
    A layer of sum units.

    All nodes of a sum layer have the same scope, which is the scope of its child
    layers.

    The weights are always stored sparsely: a sum node usually has few children, so
    the dense weight matrix of a layer with many nodes is mostly empty and can be far
    larger than the circuit itself.
    """

    log_weights: List[coo_array]
    """
    The logarithmic weights of the edges, grouped per child layer.

    The ``i``-th entry holds, for every node of this layer, the weights of the edges
    into the ``i``-th child layer, as a sparse block of shape (#nodes, #nodes of that
    child layer).
    """

    _edge_gather: Optional[npt.NDArray] = field(default=None, init=False, repr=False)
    """
    Cached index matrix of :attr:`edge_gather`.
    """

    _edges_are_contiguous: bool = field(default=False, init=False, repr=False)
    """
    Whether the edges are stored node by node with the same number of edges per node,
    filled together with :attr:`_edge_gather`.
    """

    _edge_targets: Optional[Tuple[npt.NDArray, npt.NDArray]] = field(
        default=None, init=False, repr=False
    )
    """
    Cached targets of :attr:`edge_targets`.
    """

    @property
    def variables(self) -> npt.NDArray:
        if self._variables_cache is None:
            self._variables_cache = self.child_layers[0].variables
        return self._variables_cache

    @property
    def number_of_nodes(self) -> int:
        return self.log_weights[0].shape[0]

    @property
    def number_of_own_parameters(self) -> int:
        return sum(log_weights.nnz for log_weights in self.log_weights)

    @property
    def log_weighted_child_layers(self) -> Iterator[Tuple[coo_array, Layer]]:
        """
        :return: The log-weights and the child layers, zipped together.
        """
        return zip(self.log_weights, self.child_layers)

    def validate_own(self):
        for log_weights in self.log_weights:
            if log_weights.shape[0] != self.number_of_nodes:
                raise ShapeMismatchError(self.number_of_nodes, log_weights.shape[0])

        for log_weights, child_layer in self.log_weighted_child_layers:
            if log_weights.shape[1] != child_layer.number_of_nodes:
                raise ShapeMismatchError(
                    child_layer.number_of_nodes, log_weights.shape[1]
                )

    # %% edges

    @property
    def concatenated_rows(self) -> npt.NDArray:
        """
        :return: The node of every edge, with the child layers concatenated in order.
        """
        return np.concatenate([log_weights.row for log_weights in self.log_weights])

    @property
    def concatenated_edge_log_weights(self) -> npt.NDArray:
        """
        :return: The weight of every edge, with the child layers concatenated in order.
        """
        return np.concatenate([log_weights.data for log_weights in self.log_weights])

    @property
    def edge_gather(self) -> npt.NDArray:
        """
        The positions of the edges of every node, as a rectangular index matrix of shape
        (#nodes, largest number of edges of a node).

        Rows of nodes with fewer edges are padded with the position one past the last
        edge, which the queries fill with ``-inf``. Gathering with this matrix turns the
        per-node reduction over a ragged set of edges into one reduction over the last
        axis of a rectangular array, which is what keeps the likelihood of a whole batch
        of events a handful of numpy calls instead of a loop over nodes or events.
        """
        if self._edge_gather is None:
            rows = self.concatenated_rows
            number_of_edges = len(rows)
            counts = np.bincount(rows, minlength=self.number_of_nodes)
            width = max(int(counts.max()) if len(counts) else 0, 1)

            gather = np.full(
                (self.number_of_nodes, width), number_of_edges, dtype=np.int64
            )
            # the position of every edge inside the row of its node
            order = np.argsort(rows, kind="stable")
            sorted_rows = rows[order]
            offsets = np.arange(number_of_edges) - np.repeat(
                np.concatenate([[0], np.cumsum(counts)[:-1]]), counts
            )
            gather[sorted_rows, offsets] = order
            self._edge_gather = gather

            # when every node has the same number of edges and the edges are already
            # stored node by node, grouping them is a reshape rather than a gather
            self._edges_are_contiguous = bool(
                number_of_edges == self.number_of_nodes * width
                and np.array_equal(
                    gather, np.arange(number_of_edges).reshape(-1, width)
                )
            )
        return self._edge_gather

    @property
    def edges_are_contiguous(self) -> bool:
        """
        :return: Whether :meth:`group_edges_by_node` can reshape instead of gather.
        """
        self.edge_gather  # fills the flag along with the gather matrix
        return self._edges_are_contiguous

    def group_edges_by_node(
        self, values: npt.NDArray, padding: float = -np.inf
    ) -> npt.NDArray:
        """
        Rearrange per-edge values into one row per node.

        :param values: Per-edge values with the edges in the last axis.
        :param padding: The value for nodes with fewer edges than the widest one.
        :return: The values with shape ``(..., #nodes, edges per node)``.
        """
        if self.edges_are_contiguous:
            return values.reshape(values.shape[:-1] + (self.number_of_nodes, -1))
        return self.pad_edges(values, padding)[..., self.edge_gather]

    def pad_edges(self, values: npt.NDArray, padding: float) -> npt.NDArray:
        """
        Append the slot that :attr:`edge_gather` pads with.

        :param values: Per-edge values with the edges in the last axis.
        :param padding: The value of the padding slot. ``-inf`` is neutral for a
            logarithmic reduction, ``0`` for a linear one.
        :return: The values with one extra entry in the last axis.
        """
        return np.concatenate(
            [values, np.full(values.shape[:-1] + (1,), padding)], axis=-1
        )

    @property
    def edge_targets(self) -> Tuple[npt.NDArray, npt.NDArray]:
        """
        :return: The index of the child layer and the index of the node in it that every
            edge points to, in the order of the concatenated edges.
        """
        if self._edge_targets is None:
            self._edge_targets = (
                np.concatenate(
                    [
                        np.full(log_weights.nnz, index, np.int64)
                        for index, log_weights in enumerate(self.log_weights)
                    ]
                ),
                np.concatenate([log_weights.col for log_weights in self.log_weights]),
            )
        return self._edge_targets

    def iterate_edges(self) -> Iterator[Edge]:
        for child_layer_index, log_weights in enumerate(self.log_weights):
            for node, child_node in zip(log_weights.row, log_weights.col):
                yield Edge(int(node), child_layer_index, int(child_node))

    # %% weights

    @property
    def log_normalization_constants(self) -> npt.NDArray:
        """
        :return: ``log(sum(exp(w)))`` over the weights of each node, shape (#nodes,).
        """
        gathered = self.group_edges_by_node(self.concatenated_edge_log_weights)
        return embedded_logsumexp(gathered, axis=-1)

    @property
    def normalized_edge_log_weights(self) -> npt.NDArray:
        """
        :return: The logarithmic weight of every edge, normalized per node, in the
            order of the concatenated edges.
        """
        return (
            self.concatenated_edge_log_weights
            - self.log_normalization_constants[self.concatenated_rows]
        )

    @property
    def normalized_edge_weights(self) -> npt.NDArray:
        """
        :return: The weight of every edge in linear space, normalized per node.
        """
        shifted = self.normalized_edge_log_weights
        # a node whose weights are all -inf normalizes to nan; it is impossible, and the
        # prune pass removes it, so its weights are simply zero here
        return np.where(np.isfinite(shifted), np.exp(shifted), 0.0)

    def normalize_own(self):
        normalization = self.log_normalization_constants
        for log_weights in self.log_weights:
            log_weights.data = log_weights.data - normalization[log_weights.row]

    # %% queries

    def _weighted_forward(self, child_results: List[npt.NDArray]) -> npt.NDArray:
        """
        Combine the results of the child layers of a linear (non-logarithmic) query
        whose results have the nodes in the last axis.

        The reduction runs over the stored edges rather than over a dense weight block,
        which would be mostly empty.

        :param child_results: The result per child layer, shape (..., #child nodes).
        :return: The result for the nodes of this layer, shape (..., #nodes).
        """
        values = np.concatenate(
            [
                child_result[..., log_weights.col]
                for log_weights, child_result in zip(self.log_weights, child_results)
            ],
            axis=-1,
        )
        values = values * self.normalized_edge_weights
        return self.group_edges_by_node(values, padding=0.0).sum(axis=-1)

    def _weighted_forward_over_nodes(
        self, child_results: List[npt.NDArray]
    ) -> npt.NDArray:
        """
        Combine the results of the child layers of a query whose results have the nodes
        in the first axis, such as the moments.

        :param child_results: The result per child layer, shape (#child nodes, ...).
        :return: The result for the nodes of this layer, shape (#nodes, ...).
        """
        values = np.concatenate(
            [
                child_result[log_weights.col]
                for log_weights, child_result in zip(self.log_weights, child_results)
            ],
            axis=0,
        )
        values = values * self.normalized_edge_weights[:, None]
        padded = np.concatenate([values, np.zeros((1, values.shape[1]))], axis=0)
        return padded[self.edge_gather].sum(axis=1)

    def weighted_child_values(
        self, log_weights: coo_array, child_result: npt.NDArray
    ) -> npt.NDArray:
        """
        Take the value of the child node of every edge and add the weight of that edge.

        :param log_weights: The weights of the edges into one child layer.
        :param child_result: The result of that child layer, child nodes last.
        :return: One value per edge, the edges last.
        """
        columns = log_weights.col
        # a sum layer usually points at every node of its child layer exactly once and in
        # order, in which case the gather is an identity copy of an array that has one
        # entry per event per node, and skipping it is worth the comparison
        if len(columns) == child_result.shape[-1] and np.array_equal(
            columns, np.arange(len(columns))
        ):
            return child_result + log_weights.data
        return child_result[..., columns] + log_weights.data

    def log_weighted_sum(self, child_results: List[npt.NDArray]) -> npt.NDArray:
        """
        Reduce the log-results of the child layers with the normalized log-weights.

        :param child_results: The log-results per child layer, with shape (..., #nodes
            of the child layer).
        :return: The log-result of the nodes of this layer with shape (..., #nodes).
        """
        values = np.concatenate(
            [
                self.weighted_child_values(log_weights, child_result)
                for log_weights, child_result in zip(self.log_weights, child_results)
            ],
            axis=-1,
        )
        gathered = self.group_edges_by_node(values)
        return embedded_logsumexp(gathered, axis=-1) - self.log_normalization_constants

    @memoized
    def log_likelihood_of_nodes(
        self, x: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        child_results = [
            child_layer.log_likelihood_of_nodes(x, cache=cache)
            for child_layer in self.child_layers
        ]
        return self.log_weighted_sum(child_results)

    @memoized
    def cumulative_distribution_of_nodes(
        self, x: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        child_results = [
            child_layer.cumulative_distribution_of_nodes(x, cache=cache)
            for child_layer in self.child_layers
        ]
        return self._weighted_forward(child_results)

    @memoized
    def probability_of_simple_event_of_nodes(
        self,
        event: SimpleEvent,
        variables: SortedSet,
        cache: Optional[QueryCache] = None,
    ) -> npt.NDArray:
        child_results = [
            child_layer.probability_of_simple_event_of_nodes(
                event, variables, cache=cache
            ).reshape(1, -1)
            for child_layer in self.child_layers
        ]
        return self._weighted_forward(child_results).reshape(-1)

    @memoized
    def support_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> List[Event]:
        child_supports = [
            child_layer.support_of_nodes(variables, cache=cache)
            for child_layer in self.child_layers
        ]

        result: List[Optional[Event]] = [None] * self.number_of_nodes
        for edge in self.iterate_edges():
            support = child_supports[edge.child_layer_index][edge.child_node]
            if result[edge.node] is None:
                result[edge.node] = support.__deepcopy__()
            else:
                result[edge.node] = result[edge.node] | support.__deepcopy__()

        return [Event() if support is None else support for support in result]

    @memoized
    def log_mode_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> Tuple[List[Event], npt.NDArray]:
        child_modes = [
            child_layer.log_mode_of_nodes(variables, cache=cache)
            for child_layer in self.child_layers
        ]
        child_layer_of_edge, child_node_of_edge = self.edge_targets

        best_value = np.full(self.number_of_nodes, -np.inf)
        candidates: List[List[Event]] = [[] for _ in range(self.number_of_nodes)]

        for node, log_weight, child_layer_index, child_node in zip(
            self.concatenated_rows,
            self.normalized_edge_log_weights,
            child_layer_of_edge,
            child_node_of_edge,
        ):
            child_events, child_values = child_modes[child_layer_index]
            value = log_weight + child_values[child_node]
            mode = child_events[child_node]
            if value > best_value[node]:
                best_value[node] = value
                candidates[node] = [mode]
            elif value == best_value[node]:
                candidates[node].append(mode)

        modes = []
        for events in candidates:
            if not events:
                modes.append(Event())
                continue
            mode = events[0].__deepcopy__()
            for event in events[1:]:
                mode |= event.__deepcopy__()
            modes.append(mode)

        return modes, best_value

    @memoized
    def moment_of_nodes(
        self,
        order: npt.NDArray,
        center: npt.NDArray,
        requested: npt.NDArray,
        variables: SortedSet,
        cache: Optional[QueryCache] = None,
    ) -> npt.NDArray:
        child_results = [
            child_layer.moment_of_nodes(
                order, center, requested, variables, cache=cache
            )
            for child_layer in self.child_layers
        ]
        return self._weighted_forward_over_nodes(child_results)

    def sample_forward(
        self,
        assignment: ForwardSampleAssignment,
        samples: npt.NDArray,
        variables: SortedSet,
    ):
        # the padding slot gets a weight of zero, so it is never drawn
        weights = np.append(self.normalized_edge_weights, 0.0)
        for node, rows_of_node in enumerate(assignment.rows_of(self)):
            if rows_of_node:
                self.route_rows_of_node(
                    node, np.concatenate(rows_of_node), weights, assignment
                )

    def route_rows_of_node(
        self,
        node: int,
        rows: npt.NDArray,
        weights: npt.NDArray,
        assignment: ForwardSampleAssignment,
    ):
        """
        Split the sample rows of one node among its children, in proportion to the
        weights of its edges.

        :param node: The index of the node.
        :param rows: The sample rows assigned to the node.
        :param weights: The normalized weight of every edge, followed by the zero weight
            of the padding slot of :attr:`edge_gather`.
        :param assignment: The assignment to route the rows into.
        """
        positions = self.edge_gather[node]
        probabilities = weights[positions]

        # guard against the accumulated floating point error of the normalization
        total = probabilities.sum()
        if total <= 0:
            return
        counts = np.random.multinomial(len(rows), pvals=probabilities / total)

        # shuffle so that the contiguous chunks handed to the children are an unbiased
        # partition of the rows
        np.random.shuffle(rows)
        chunks = np.split(rows, np.cumsum(counts)[:-1])

        child_layer_of_edge, child_node_of_edge = self.edge_targets
        for index in np.flatnonzero(counts):
            position = positions[index]
            assignment.assign(
                self.child_layers[child_layer_of_edge[position]],
                child_node_of_edge[position],
                chunks[index],
            )

    def is_deterministic_of_nodes(
        self, variables: SortedSet, cache: QueryCache
    ) -> npt.NDArray:
        """
        A sum node is deterministic if its children have pairwise disjoint supports.
        """
        supports = [
            child_layer.support_of_nodes(variables, cache=cache)
            for child_layer in self.child_layers
        ]

        supports_per_node: List[List[Event]] = [[] for _ in range(self.number_of_nodes)]
        for edge in self.iterate_edges():
            supports_per_node[edge.node].append(
                supports[edge.child_layer_index][edge.child_node]
            )

        return np.array(
            [
                self.are_pairwise_disjoint(node_supports)
                for node_supports in supports_per_node
            ],
            dtype=bool,
        )

    @staticmethod
    def are_pairwise_disjoint(events: List[Event]) -> bool:
        """
        :param events: The events to compare.
        :return: Whether no two of the events intersect.
        """
        return all(
            event.intersection_with(other).is_empty()
            for index, event in enumerate(events)
            for other in events[index + 1 :]
        )

    def __deepcopy__(self, memo=None) -> SumLayer:
        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]
        child_layers = [
            child_layer.__deepcopy__(memo) for child_layer in self.child_layers
        ]
        result = self.__class__(
            child_layers, [log_weights.copy() for log_weights in self.log_weights]
        )
        memo[id(self)] = result
        return result

    # %% structural

    def _structural_pass(
        self,
        child_results: List[Tuple[Layer, npt.NDArray]],
        log_probabilities: Dict[int, npt.NDArray],
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Update the weights of this layer with the log-probabilities of its children.

        The new weight of an edge is its old weight times the probability of the event
        under the child, and the probability of a node is the sum of its new weights.

        :param child_results: The new child layer and its node log-probabilities.
        :param log_probabilities: The map to record the result in.
        :return: The new layer and the log-probabilities of its nodes.
        """
        new_log_weights = []
        for log_weights, (_, child_log_probabilities) in zip(
            self.log_weights, child_results
        ):
            updated = log_weights.copy()
            updated.data = updated.data + child_log_probabilities[updated.col]
            new_log_weights.append(updated)

        result = self.__class__(
            [child_layer for child_layer, _ in child_results], new_log_weights
        )
        # the probability of a node is the sum of its updated weights
        own_log_probabilities = result.log_normalization_constants
        log_probabilities[id(result)] = own_log_probabilities
        return result, own_log_probabilities

    @memoized
    def log_truncated_of_simple_event(
        self,
        event: SimpleEvent,
        variables: SortedSet,
        singleton_allowed: bool,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        child_results = [
            child_layer.log_truncated_of_simple_event(
                event, variables, singleton_allowed, log_probabilities, cache=cache
            )
            for child_layer in self.child_layers
        ]
        return self._structural_pass(child_results, log_probabilities)

    @memoized
    def log_truncated_of_simple_events(
        self,
        events: List[SimpleEvent],
        variables: SortedSet,
        singleton_allowed: bool,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        number_of_events = len(events)
        number_of_nodes = self.number_of_nodes
        blocks = np.arange(number_of_events)

        new_child_layers = []
        new_log_weights = []
        for log_weights, child_layer in self.log_weighted_child_layers:
            new_child_layer, child_log_probabilities = (
                child_layer.log_truncated_of_simple_events(
                    events, variables, singleton_allowed, log_probabilities, cache=cache
                )
            )
            new_child_layers.append(new_child_layer)

            # the block of event k is the original sparsity pattern shifted into its own
            # rows and columns
            number_of_entries = log_weights.nnz
            rows = np.tile(log_weights.row, number_of_events) + np.repeat(
                blocks * number_of_nodes, number_of_entries
            )
            columns = np.tile(log_weights.col, number_of_events) + np.repeat(
                blocks * child_layer.number_of_nodes, number_of_entries
            )
            # the weight of an edge times the probability of the event under its child
            data = (
                np.tile(log_weights.data, number_of_events)
                + child_log_probabilities[columns]
            )

            new_log_weights.append(
                coo_array(
                    (data, (rows, columns)),
                    shape=(
                        number_of_events * number_of_nodes,
                        number_of_events * child_layer.number_of_nodes,
                    ),
                )
            )

        result = self.__class__(new_child_layers, new_log_weights)
        own_log_probabilities = result.log_normalization_constants
        log_probabilities[id(result)] = own_log_probabilities
        return result, own_log_probabilities

    @memoized
    def log_conditional_of_point(
        self,
        point: Dict[Variable, Any],
        variables: SortedSet,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        child_results = [
            child_layer.log_conditional_of_point(
                point, variables, log_probabilities, cache=cache
            )
            for child_layer in self.child_layers
        ]
        return self._structural_pass(child_results, log_probabilities)

    def live_entries(
        self,
        alive: npt.NDArray,
        log_weights: coo_array,
        child_layer: Layer,
        log_probabilities: Dict[int, npt.NDArray],
    ) -> npt.NDArray:
        """
        Determine the edges into one child layer that survive a prune.

        :param alive: The live nodes of this layer.
        :param log_weights: The weights of the edges into the child layer.
        :param child_layer: The child layer.
        :param log_probabilities: The per-layer log-probabilities of the structural
            pass.
        :return: A boolean mask over the stored weight entries.
        """
        mask = alive[log_weights.row] & (log_weights.data > -np.inf)
        child_log_probabilities = log_probabilities.get(id(child_layer))
        if child_log_probabilities is not None:
            mask = mask & (child_log_probabilities[log_weights.col] > -np.inf)
        return mask

    def required_child_nodes(
        self, alive: npt.NDArray, log_probabilities: Dict[int, npt.NDArray]
    ) -> List[Tuple[Layer, npt.NDArray]]:
        result = []
        for log_weights, child_layer in self.log_weighted_child_layers:
            mask = self.live_entries(alive, log_weights, child_layer, log_probabilities)
            needed = np.zeros(child_layer.number_of_nodes, dtype=bool)
            needed[log_weights.col[mask]] = True
            result.append((child_layer, needed))
        return result

    def rebuild(
        self,
        needed: Dict[int, npt.NDArray],
        rebuilt: Dict[int, Optional[Layer]],
    ) -> Optional[Layer]:
        alive = needed[id(self)]
        if not alive.any():
            return None

        node_remap, number_of_nodes = remap_indices(alive)

        new_child_layers = []
        new_log_weights = []
        for log_weights, child_layer in self.log_weighted_child_layers:
            pruned_child = rebuilt.get(id(child_layer))
            if pruned_child is None:
                continue
            child_needed = needed[id(child_layer)]
            mask = (
                alive[log_weights.row]
                & (log_weights.data > -np.inf)
                & child_needed[log_weights.col]
            )
            if not mask.any():
                continue
            child_remap, number_of_child_nodes = remap_indices(child_needed)
            new_child_layers.append(pruned_child)
            new_log_weights.append(
                coo_array(
                    (
                        log_weights.data[mask],
                        (
                            node_remap[log_weights.row[mask]],
                            child_remap[log_weights.col[mask]],
                        ),
                    ),
                    shape=(number_of_nodes, number_of_child_nodes),
                )
            )

        if not new_child_layers:
            return None

        return self.__class__(new_child_layers, new_log_weights)

    @memoized
    def marginal(
        self, kept: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> Optional[Layer]:
        new_child_layers = []
        new_log_weights = []
        for log_weights, child_layer in self.log_weighted_child_layers:
            marginal_child = child_layer.marginal(kept, cache=cache)
            if marginal_child is None:
                continue
            new_child_layers.append(marginal_child)
            new_log_weights.append(log_weights.copy())

        if not new_child_layers:
            return None
        return self.__class__(new_child_layers, new_log_weights)

    @memoized
    def simplify(self, cache: Optional[QueryCache] = None) -> Layer:
        simplified_children = [
            child_layer.simplify(cache=cache) for child_layer in self.child_layers
        ]
        result = self.__class__(
            simplified_children,
            [log_weights.copy() for log_weights in self.log_weights],
        )

        if result.is_identity():
            return simplified_children[0]
        return result

    def is_identity(self) -> bool:
        """
        :return: Whether this layer passes its single child layer through unchanged, so
            that it can be removed without changing the distribution.
        """
        if len(self.log_weights) != 1:
            return False
        log_weights = self.log_weights[0]
        if log_weights.shape[0] != log_weights.shape[1]:
            return False
        if log_weights.nnz != self.number_of_nodes:
            return False
        # every node points at the node with its own index, and at nothing else
        return bool(
            np.array_equal(log_weights.row, log_weights.col)
            and len(np.unique(log_weights.row)) == self.number_of_nodes
        )
