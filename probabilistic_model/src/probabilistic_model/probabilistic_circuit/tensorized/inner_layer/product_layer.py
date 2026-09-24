from __future__ import annotations

from dataclasses import (
    dataclass,
)

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
from probabilistic_model.probabilistic_circuit.tensorized.utils import remap_indices
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import (
    Edge,
    ForwardSampleAssignment,
    InnerLayer,
    Layer,
    QueryCache,
    memoized,
)


@dataclass(eq=False, repr=False)
class ProductLayer(InnerLayer):
    """
    A layer of product units.

    Every node multiplies at most one node of each child layer, so the scope of a node
    is the union of the scopes of its child layers and its likelihood is the sum of
    their log-likelihoods.
    """

    edges: coo_array
    """
    The edges as a sparse integer matrix of shape (#child layers, #nodes).

    The value of the entry ``(l, n)`` is the index of the node in the ``l``-th child
    layer that the ``n``-th node of this layer multiplies. A node of a child layer may
    be referenced by several nodes of this layer. A stored ``0`` is an edge to the first
    node of the child layer, not a missing entry.
    """

    @property
    def number_of_nodes(self) -> int:
        return self.edges.shape[1]

    @property
    def variables(self) -> npt.NDArray:
        if self._variables_cache is None:
            self._variables_cache = np.unique(
                np.concatenate(
                    [child_layer.variables for child_layer in self.child_layers]
                )
            )
        return self._variables_cache

    @property
    def number_of_own_parameters(self) -> int:
        # the edges of a product layer are structure, not parameters
        return 0

    def validate_own(self):
        if self.edges.shape != (len(self.child_layers), self.number_of_nodes):
            raise ShapeMismatchError(
                (len(self.child_layers), self.number_of_nodes), self.edges.shape
            )

    def is_decomposable_of_nodes(self) -> npt.NDArray:
        """
        A product node is decomposable if no variable is in the scope of more than one
        of its factors.
        """
        factors_of_node = np.zeros(
            (len(self.child_layers), self.number_of_nodes), dtype=np.int64
        )
        np.add.at(factors_of_node, (self.edges.row, self.edges.col), 1)
        scope_of_child_layer = np.array(
            [
                np.isin(self.variables, child_layer.variables)
                for child_layer in self.child_layers
            ],
            dtype=np.int64,
        )
        # how many factors of every node have every variable in their scope
        occurrences = factors_of_node.T @ scope_of_child_layer
        return occurrences.max(axis=1, initial=0) <= 1

    # %% queries

    def edges_of_child_layer(
        self, child_layer_index: int
    ) -> Tuple[npt.NDArray, npt.NDArray, bool]:
        """
        The edges into one child layer.

        :param child_layer_index: The index of the child layer.
        :return: The nodes of this layer, the nodes of the child layer they point to,
            and whether every node appears at most once. A decomposable product has at
            most one factor in each child layer, so the fast path is the normal one; the
            check keeps the reduction correct for a circuit that is not decomposable.
        """
        mask = self.edges.row == child_layer_index
        nodes = self.edges.col[mask]
        child_nodes = self.edges.data[mask].astype(np.int64)
        unique = len(np.unique(nodes)) == len(nodes)
        return nodes, child_nodes, unique

    def _gather_and_add(
        self, child_results: List[npt.NDArray], fill: float
    ) -> npt.NDArray:
        """
        Sum, per node, the results of the child nodes the edges point to.

        :param child_results: The result per child layer with the child nodes last.
        :param fill: The value of a node without any edge.
        :return: The summed result with the nodes of this layer last.
        """
        leading_shape = child_results[0].shape[:-1]
        result = np.zeros(leading_shape + (self.number_of_nodes,))
        touched = np.zeros(self.number_of_nodes, dtype=bool)

        for child_layer_index, child_result in enumerate(child_results):
            nodes, child_nodes, unique = self.edges_of_child_layer(child_layer_index)
            if len(nodes) == 0:
                continue
            gathered = child_result[..., child_nodes]
            if unique:
                result[..., nodes] += gathered
            else:
                np.add.at(result, (Ellipsis, nodes), gathered)
            touched[nodes] = True

        if not touched.all():
            result[..., ~touched] = fill
        return result

    @memoized
    def log_likelihood_of_nodes(
        self, x: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        child_results = [
            child_layer.log_likelihood_of_nodes(x, cache=cache)
            for child_layer in self.child_layers
        ]
        return self._gather_and_add(child_results, fill=0.0)

    @memoized
    def cumulative_distribution_of_nodes(
        self, x: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        child_results = [
            child_layer.cumulative_distribution_of_nodes(x, cache=cache)
            for child_layer in self.child_layers
        ]
        return self._gather_and_multiply(child_results)

    def _gather_and_multiply(self, child_results: List[npt.NDArray]) -> npt.NDArray:
        leading_shape = child_results[0].shape[:-1]
        result = np.ones(leading_shape + (self.number_of_nodes,))
        for child_layer_index, child_result in enumerate(child_results):
            nodes, child_nodes, unique = self.edges_of_child_layer(child_layer_index)
            if len(nodes) == 0:
                continue
            gathered = child_result[..., child_nodes]
            if unique:
                result[..., nodes] *= gathered
            else:
                np.multiply.at(result, (Ellipsis, nodes), gathered)
        return result

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
        return self._gather_and_multiply(child_results).reshape(-1)

    @memoized
    def support_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> List[Event]:
        child_supports = [
            child_layer.support_of_nodes(variables, cache=cache)
            for child_layer in self.child_layers
        ]

        own_variables = {variables[index] for index in self.variables}
        result: List[Optional[Event]] = [None] * self.number_of_nodes

        for edge in self.iterate_edges():
            support = child_supports[edge.child_layer_index][
                edge.child_node
            ].__deepcopy__()
            if result[edge.node] is None:
                support.fill_missing_variables(own_variables)
                result[edge.node] = support
            else:
                result[edge.node] = result[edge.node] & support

        return [Event() if support is None else support for support in result]

    @memoized
    def log_mode_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> Tuple[List[Event], npt.NDArray]:
        child_modes = [
            child_layer.log_mode_of_nodes(variables, cache=cache)
            for child_layer in self.child_layers
        ]

        own_variables = {variables[index] for index in self.variables}
        events: List[Optional[Event]] = [None] * self.number_of_nodes
        values = np.zeros(self.number_of_nodes)

        for edge in self.iterate_edges():
            child_event = child_modes[edge.child_layer_index][0][
                edge.child_node
            ].__deepcopy__()
            values[edge.node] += child_modes[edge.child_layer_index][1][edge.child_node]
            if events[edge.node] is None:
                child_event.fill_missing_variables(own_variables)
                events[edge.node] = child_event
            else:
                events[edge.node] = events[edge.node].intersection_with(child_event)

        return [Event() if event is None else event for event in events], values

    def iterate_edges(self) -> Iterator[Edge]:
        for child_layer_index, node, child_node in zip(
            self.edges.row, self.edges.col, self.edges.data
        ):
            yield Edge(int(node), int(child_layer_index), int(child_node))

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
        # the moments of a decomposable product are the moments of the factor that owns
        # the variable, so summing the (zero padded) child moments is the right reduction
        result = np.zeros((self.number_of_nodes, len(order)))
        for child_layer_index, child_result in enumerate(child_results):
            nodes, child_nodes, unique = self.edges_of_child_layer(child_layer_index)
            if len(nodes) == 0:
                continue
            if unique:
                result[nodes] += child_result[child_nodes]
            else:
                np.add.at(result, nodes, child_result[child_nodes])
        return result

    def sample_forward(
        self,
        assignment: ForwardSampleAssignment,
        samples: npt.NDArray,
        variables: SortedSet,
    ):
        own_assignment = assignment.rows_of(self)

        rows_per_node = [
            np.concatenate(rows) if rows else None for rows in own_assignment
        ]

        for edge in self.iterate_edges():
            rows = rows_per_node[edge.node]
            if rows is None:
                continue
            child_layer = self.child_layers[edge.child_layer_index]
            assignment.assign(child_layer, edge.child_node, rows)

    # %% structural

    def _structural_pass(
        self,
        child_results: List[Tuple[Layer, npt.NDArray]],
        log_probabilities: Dict[int, npt.NDArray],
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Accumulate the log-probabilities of the children of every node.

        :param child_results: The new child layer and its node log-probabilities.
        :param log_probabilities: The map to record the result in.
        :return: The new layer and the log-probabilities of its nodes.
        """
        result = self.__class__(
            [child_layer for child_layer, _ in child_results], self.edges.copy()
        )

        own_log_probabilities = np.zeros(self.number_of_nodes)
        for child_layer_index, (_, child_log_probabilities) in enumerate(child_results):
            nodes, child_nodes, unique = self.edges_of_child_layer(child_layer_index)
            if len(nodes) == 0:
                continue
            if unique:
                own_log_probabilities[nodes] += child_log_probabilities[child_nodes]
            else:
                np.add.at(
                    own_log_probabilities, nodes, child_log_probabilities[child_nodes]
                )

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
        number_of_entries = self.edges.nnz
        blocks = np.arange(number_of_events)

        new_child_layers = []
        child_log_probabilities = []
        for child_layer in self.child_layers:
            new_child_layer, child_log_probability = (
                child_layer.log_truncated_of_simple_events(
                    events, variables, singleton_allowed, log_probabilities, cache=cache
                )
            )
            new_child_layers.append(new_child_layer)
            child_log_probabilities.append(child_log_probability)

        # every edge is repeated once per event, pointing into that event's block of the
        # child layer
        node_counts = np.array(
            [child_layer.number_of_nodes for child_layer in self.child_layers]
        )
        rows = np.tile(self.edges.row, number_of_events)
        columns = np.tile(self.edges.col, number_of_events) + np.repeat(
            blocks * number_of_nodes, number_of_entries
        )
        data = np.tile(self.edges.data.astype(np.int64), number_of_events) + np.repeat(
            blocks, number_of_entries
        ) * np.tile(node_counts[self.edges.row], number_of_events)

        edges = coo_array(
            (data, (rows, columns)),
            shape=(len(self.child_layers), number_of_events * number_of_nodes),
        )
        result = self.__class__(new_child_layers, edges)

        own_log_probabilities = np.zeros(number_of_events * number_of_nodes)
        for child_layer_index, child_log_probability in enumerate(
            child_log_probabilities
        ):
            mask = rows == child_layer_index
            np.add.at(
                own_log_probabilities,
                columns[mask],
                child_log_probability[data[mask]],
            )
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

    def required_child_nodes(
        self, alive: npt.NDArray, log_probabilities: Dict[int, npt.NDArray]
    ) -> List[Tuple[Layer, npt.NDArray]]:
        kept_edges = alive[self.edges.col]
        result = []
        for child_layer_index, child_layer in enumerate(self.child_layers):
            mask = kept_edges & (self.edges.row == child_layer_index)
            needed = np.zeros(child_layer.number_of_nodes, dtype=bool)
            needed[self.edges.data[mask].astype(np.int64)] = True
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
        kept_edges = alive[self.edges.col]

        new_child_layers = []
        new_rows = []
        new_columns = []
        new_data = []

        for child_layer_index, child_layer in enumerate(self.child_layers):
            mask = kept_edges & (self.edges.row == child_layer_index)
            if not mask.any():
                continue

            pruned_child = rebuilt.get(id(child_layer))
            if pruned_child is None:
                # a factor of the product became impossible, so every node that
                # references it is impossible as well
                return None

            child_remap, _ = remap_indices(needed[id(child_layer)])
            new_rows.append(np.full(mask.sum(), len(new_child_layers), dtype=np.int64))
            new_columns.append(node_remap[self.edges.col[mask]])
            new_data.append(child_remap[self.edges.data[mask].astype(np.int64)])
            new_child_layers.append(pruned_child)

        if not new_child_layers:
            return None

        edges = coo_array(
            (
                np.concatenate(new_data),
                (np.concatenate(new_rows), np.concatenate(new_columns)),
            ),
            shape=(len(new_child_layers), number_of_nodes),
        )
        return self.__class__(new_child_layers, edges)

    @memoized
    def marginal(
        self, kept: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> Optional[Layer]:
        new_child_layers = []
        new_rows = []
        new_columns = []
        new_data = []

        for child_layer_index, child_layer in enumerate(self.child_layers):
            marginal_child = child_layer.marginal(kept, cache=cache)
            if marginal_child is None:
                continue
            mask = self.edges.row == child_layer_index
            new_rows.append(np.full(mask.sum(), len(new_child_layers), dtype=np.int64))
            new_columns.append(self.edges.col[mask])
            new_data.append(self.edges.data[mask])
            new_child_layers.append(marginal_child)

        if not new_child_layers:
            return None

        edges = coo_array(
            (
                np.concatenate(new_data),
                (np.concatenate(new_rows), np.concatenate(new_columns)),
            ),
            shape=(len(new_child_layers), self.number_of_nodes),
        )
        return self.__class__(new_child_layers, edges)

    @memoized
    def simplify(self, cache: Optional[QueryCache] = None) -> Layer:
        simplified_children = [
            child_layer.simplify(cache=cache) for child_layer in self.child_layers
        ]
        result = self.__class__(simplified_children, self.edges.copy())

        if result.is_identity():
            return simplified_children[0]
        return result

    def is_identity(self) -> bool:
        """
        :return: Whether this layer forwards its single child layer unchanged.
        """
        if len(self.child_layers) != 1:
            return False
        if self.edges.nnz != self.number_of_nodes:
            return False
        if self.child_layers[0].number_of_nodes != self.number_of_nodes:
            return False
        # every node multiplies only the node of the child layer with its own index
        return bool(
            np.array_equal(self.edges.data.astype(np.int64), self.edges.col)
            and len(np.unique(self.edges.col)) == self.number_of_nodes
        )

    def __deepcopy__(self, memo=None) -> ProductLayer:
        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]
        child_layers = [
            child_layer.__deepcopy__(memo) for child_layer in self.child_layers
        ]
        result = self.__class__(child_layers, self.edges.copy())
        memo[id(self)] = result
        return result
