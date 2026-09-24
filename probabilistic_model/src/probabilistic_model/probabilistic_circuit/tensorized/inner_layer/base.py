from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from krrood.adapters import json_serializer
from krrood.adapters.json_serializer import SubclassJSONSerializer
from random_events.product_algebra import Event, SimpleEvent
from random_events.variable import Variable
from sortedcontainers import SortedSet
from typing_extensions import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Self,
    Tuple,
)

from probabilistic_model.probabilistic_circuit.tensorized.forward_sample_assignment import (
    ForwardSampleAssignment,
)
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.inner_layer_edge import (
    InnerLayerEdge,
)
from probabilistic_model.probabilistic_circuit.tensorized.layer_with_depth import (
    LayerWithDepth,
)
from probabilistic_model.probabilistic_circuit.tensorized.query_cache import (
    QueryCache,
    memoized,
)


class Layer(SubclassJSONSerializer, ABC):
    """
    Abstract base class for the layers of a layered probabilistic circuit.

    A layer groups nodes that have the same scope and stores their parameters in
    arrays, so that every query is evaluated for all nodes of the layer at once.
    Variables are referred to by their index in the variables of the circuit.
    """

    # %% structure

    child_layers: List[Layer]
    """
    The layers that the nodes of this layer point to.
    """

    @property
    @abstractmethod
    def variables(self) -> npt.NDArray:
        """
        :return: The sorted indices of the variables in the scope of this layer.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def number_of_nodes(self) -> int:
        """
        :return: The number of nodes in this layer.
        """
        raise NotImplementedError

    @property
    def number_of_parameters(self) -> int:
        """
        :return: The number of parameters of the circuit rooted at this layer.
        """
        return sum(layer.number_of_own_parameters for layer in self.all_layers())

    @property
    @abstractmethod
    def number_of_own_parameters(self) -> int:
        """
        :return: The number of parameters stored in this layer alone.
        """
        raise NotImplementedError

    def validate(self):
        """
        Check that the parameter arrays of this layer and all its descendants have
        consistent shapes.

        :raises ShapeMismatchError: If a shape is inconsistent.
        """
        for layer in self.all_layers():
            layer.validate_own()

    @abstractmethod
    def validate_own(self):
        """
        Check the shapes of the parameters stored in this layer alone.

        :raises ShapeMismatchError: If a shape is inconsistent.
        """
        raise NotImplementedError

    def all_layers(self) -> List[Layer]:
        """
        :return: Every layer of the circuit rooted here, each exactly once, and every
            layer after all of its parents.
        """
        postorder: List[Layer] = []
        self._append_in_postorder(postorder, set())
        return postorder[::-1]

    def _append_in_postorder(self, result: List[Layer], visited: set):
        """
        Append the layers of the circuit rooted here to ``result``, every layer after
        all of its descendants and each exactly once.

        Reversed, this order has every layer after all of its parents, which a
        breadth-first or a pre-order traversal does not guarantee for a layer that
        several parents share.

        :param result: The list to append to.
        :param visited: The ids of the layers already visited.
        """
        if id(self) in visited:
            return
        visited.add(id(self))
        for child_layer in self.child_layers:
            child_layer._append_in_postorder(result, visited)
        result.append(self)

    def all_layers_with_depth(self, depth: int = 0) -> List[LayerWithDepth]:
        """
        :param depth: The depth to report for this layer.
        :return: Every layer of the circuit rooted here with its depth. Layers that are
            reachable along several paths appear once per path.
        """
        result = [LayerWithDepth(depth, self)]
        for child_layer in self.child_layers:
            result.extend(child_layer.all_layers_with_depth(depth + 1))
        return result

    # %% queries

    @abstractmethod
    def log_likelihood_of_nodes(
        self, events: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        """
        Calculate the log-likelihood of every node of this layer.

        :param events: The events with shape (#events, #variables of the circuit).
        :param cache: The shared cache of the current query.
        :return: The log-likelihoods with shape (#events, #nodes).
        """
        raise NotImplementedError

    @abstractmethod
    def cumulative_distribution_of_nodes(
        self, events: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> npt.NDArray:
        """
        Calculate the cumulative distribution function of every node of this layer.

        :param events: The events with shape (#events, #variables of the circuit).
        :param cache: The shared cache of the current query.
        :return: The values with shape (#events, #nodes).
        """
        raise NotImplementedError

    @abstractmethod
    def probability_of_simple_event_of_nodes(
        self,
        event: SimpleEvent,
        variables: SortedSet,
        cache: Optional[QueryCache] = None,
    ) -> npt.NDArray:
        """
        Calculate the probability of a simple event for every node of this layer.

        :param event: The simple event.
        :param variables: The variables of the circuit.
        :param cache: The shared cache of the current query.
        :return: The probabilities with shape (#nodes,).
        """
        raise NotImplementedError

    @abstractmethod
    def support_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> List[Event]:
        """
        Calculate the support of every node of this layer.

        :param variables: The variables of the circuit.
        :param cache: The shared cache of the current query.
        :return: One event per node.
        """
        raise NotImplementedError

    @abstractmethod
    def log_mode_of_nodes(
        self, variables: SortedSet, cache: Optional[QueryCache] = None
    ) -> Tuple[List[Event], npt.NDArray]:
        """
        Calculate the mode of every node of this layer.

        :param variables: The variables of the circuit.
        :param cache: The shared cache of the current query.
        :return: One event per node and the log-likelihoods of the modes.
        """
        raise NotImplementedError

    @abstractmethod
    def moment_of_nodes(
        self,
        order: npt.NDArray,
        center: npt.NDArray,
        requested: npt.NDArray,
        variables: SortedSet,
        cache: Optional[QueryCache] = None,
    ) -> npt.NDArray:
        """
        Calculate the moment of every node of this layer.

        :param order: The order per variable of the circuit.
        :param center: The center per variable of the circuit.
        :param requested: A boolean mask of the variables the moment is requested for.
        :param cache: The shared cache of the current query.
        :return: The moments with shape (#nodes, #variables of the circuit).
        """
        raise NotImplementedError

    @abstractmethod
    def sample_forward(
        self,
        assignment: ForwardSampleAssignment,
        samples: npt.NDArray,
        variables: SortedSet,
    ):
        """
        Route the sample rows that the parents of this layer assigned to its nodes.

        :param assignment: The rows assigned to every node of every layer so far.
        :param samples: The array the input layers write their samples into.
        :param variables: The variables of the circuit.
        """
        raise NotImplementedError

    def is_decomposable_of_nodes(self) -> npt.NDArray:
        """
        Only a product node can violate decomposability, so every other layer reports
        all of its nodes as decomposable.

        :return: Whether every node of this layer is decomposable, shape (#nodes,).
        """
        return np.ones(self.number_of_nodes, dtype=bool)

    def is_decomposable(self) -> bool:
        """
        :return: Whether every node of the circuit rooted here is decomposable.
        """
        return all(
            layer.is_decomposable_of_nodes().all() for layer in self.all_layers()
        )

    def is_deterministic_of_nodes(
        self, variables: SortedSet, cache: QueryCache
    ) -> npt.NDArray:
        """
        Only a sum node can violate determinism, so every other layer reports all of its
        nodes as deterministic.

        :param variables: The variables of the circuit.
        :param cache: The shared cache of the supports computed so far.
        :return: Whether every node of this layer is deterministic, shape (#nodes,).
        """
        return np.ones(self.number_of_nodes, dtype=bool)

    def is_deterministic(self, variables: SortedSet) -> bool:
        """
        :param variables: The variables of the circuit.
        :return: Whether every node of the circuit rooted here is deterministic.
        """
        cache = QueryCache()
        return all(
            layer.is_deterministic_of_nodes(variables, cache).all()
            for layer in self.all_layers()
        )

    # %% structural

    @abstractmethod
    def log_truncated_of_simple_event(
        self,
        event: SimpleEvent,
        variables: SortedSet,
        singleton_allowed: bool,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Truncate every node of this layer to a simple event.

        The returned layer has exactly as many nodes, in the same order, as this layer,
        so that the edges of the parents stay valid. Nodes that became impossible are
        reported with a log-probability of ``-inf`` and are removed by the following
        :meth:`prune` pass.

        :param event: The simple event to truncate to.
        :param variables: The variables of the circuit.
        :param singleton_allowed: Whether singletons are allowed in the event.
        :param log_probabilities: The map the per-node log-probabilities of the new
            layers are written into, keyed by the id of the new layer.
        :param cache: The shared cache of the current query.
        :return: The truncated layer and the log-probabilities of its nodes.
        """
        raise NotImplementedError

    def can_truncate_in_one_batch(
        self, events: List[SimpleEvent], variables: SortedSet, singleton_allowed: bool
    ) -> bool:
        """
        Only an input layer can change its type when it is truncated, so every other
        layer can be truncated in one batch.

        :param events: The simple events to truncate to.
        :param variables: The variables of the circuit.
        :param singleton_allowed: Whether singletons are allowed in the events.
        :return: Whether :meth:`log_truncated_of_simple_events` can truncate this layer
            to all the events at once.
        """
        return True

    @abstractmethod
    def log_truncated_of_simple_events(
        self,
        events: List[SimpleEvent],
        variables: SortedSet,
        singleton_allowed: bool,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Truncate this layer to several simple events at once.

        The result holds one copy of every node per event: the node ``i`` truncated to the
        ``k``-th event sits at index ``k * self.number_of_nodes + i``. Truncating to an
        event with many simple sets this way keeps the number of *layers* constant and
        grows the parameter blocks instead, where truncating once per simple set and
        mixing the results produces one set of layers per simple set and takes the layered
        representation apart.

        Only valid if :meth:`can_truncate_in_one_batch` holds for every layer below.

        :param events: The simple events to truncate to.
        :param variables: The variables of the circuit.
        :param singleton_allowed: Whether singletons are allowed in the events.
        :param log_probabilities: The map the per-node log-probabilities are written to.
        :param cache: The shared cache of the current query.
        :return: The truncated layer and the log-probabilities of its nodes.
        """
        raise NotImplementedError

    @abstractmethod
    def log_conditional_of_point(
        self,
        point: Dict[Variable, Any],
        variables: SortedSet,
        log_probabilities: Dict[int, npt.NDArray],
        cache: Optional[QueryCache] = None,
    ) -> Tuple[Layer, npt.NDArray]:
        """
        Condition every node of this layer on a partial point.

        See :meth:`log_truncated_of_simple_event` for the contract of the result.

        :param point: The partial point.
        :param variables: The variables of the circuit.
        :param log_probabilities: The map the per-node log-probabilities are written to.
        :param cache: The shared cache of the current query.
        :return: The conditioned layer and the log-probabilities of its nodes.
        """
        raise NotImplementedError

    def alive_own(self, log_probabilities: Dict[int, npt.NDArray]) -> npt.NDArray:
        """
        Read back which nodes of this layer a structural query left possible.

        A structural pass such as :meth:`log_truncated_of_simple_event` keeps the node
        count of every layer it rewrites, so that the edges of the parents stay valid,
        and reports the nodes that became impossible with a log-probability of ``-inf``.
        A node of this layer is therefore still possible if its recorded log-probability
        is above ``-inf``. A layer that the pass recorded nothing for is one it did not
        rewrite, so none of its nodes became impossible.

        :param log_probabilities: The per-layer log-probabilities of the structural pass
            that created this layer, keyed by the id of the layer.
        :return: A boolean mask of the nodes of this layer that are still possible.
        """
        own = log_probabilities.get(id(self))
        if own is None:
            return np.ones(self.number_of_nodes, dtype=bool)
        return own > -np.inf

    def required_child_nodes(
        self, alive: npt.NDArray, log_probabilities: Dict[int, npt.NDArray]
    ) -> List[Tuple[Layer, npt.NDArray]]:
        """
        Determine which nodes of the direct children a set of live nodes still needs.

        :param alive: A boolean mask of the live nodes of this layer.
        :param log_probabilities: The per-layer log-probabilities of the structural
            pass.
        :return: One ``(child layer, mask)`` pair per child layer.
        """
        return []

    @abstractmethod
    def rebuild(
        self,
        needed: Dict[int, npt.NDArray],
        rebuilt: Dict[int, Optional[Layer]],
    ) -> Optional[Layer]:
        """
        Create the pruned version of this layer.

        :param needed: The live node mask of every layer, keyed by layer id.
        :param rebuilt: The already pruned child layers, keyed by the id of the original
            layer. A value of ``None`` marks a layer that lost all of its nodes.
        :return: The pruned layer, or ``None`` if no node survives.
        """
        raise NotImplementedError

    def prune(self, log_probabilities: Dict[int, npt.NDArray]) -> Optional[Layer]:
        """
        Remove every impossible and every unreachable node of the circuit rooted here.

        The pass first propagates liveness downwards, parents before children, so that
        a layer shared by several parents is pruned once against the union of what its
        parents need, and then rebuilds the layers bottom-up.

        :param log_probabilities: The per-layer log-probabilities of the structural pass
            that created this circuit.
        :return: The pruned circuit, or ``None`` if the root became impossible.
        """
        order = self.all_layers()

        needed: Dict[int, npt.NDArray] = {
            id(self): np.ones(self.number_of_nodes, dtype=bool)
        }
        for layer in order:
            alive = needed.get(
                id(layer), np.zeros(layer.number_of_nodes, dtype=bool)
            ) & layer.alive_own(log_probabilities)
            needed[id(layer)] = alive
            for child_layer, mask in layer.required_child_nodes(
                alive, log_probabilities
            ):
                if id(child_layer) in needed:
                    needed[id(child_layer)] = needed[id(child_layer)] | mask
                else:
                    needed[id(child_layer)] = mask

        rebuilt: Dict[int, Optional[Layer]] = {}
        for layer in reversed(order):
            rebuilt[id(layer)] = layer.rebuild(needed, rebuilt)

        return rebuilt[id(self)]

    @abstractmethod
    def marginal(
        self, kept: npt.NDArray, cache: Optional[QueryCache] = None
    ) -> Optional[Layer]:
        """
        Restrict this layer to a subset of the variables.

        :param kept: A boolean mask over the variables of the circuit.
        :param cache: The shared cache of the current pass.
        :return: The marginalized layer, or ``None`` if this layer models none of the
            kept variables.
        """
        raise NotImplementedError

    @abstractmethod
    def remap_variables(self, remap: npt.NDArray, cache: Optional[QueryCache] = None):
        """
        Rewrite the variable indices of this layer in-place.

        :param remap: An array that maps the old variable index to the new one.
        :param cache: The shared cache of the current pass.
        """
        raise NotImplementedError

    def simplify(self, cache: Optional[QueryCache] = None) -> Layer:
        """
        Remove layers that have no effect on the represented distribution.

        This collapses the identity sum and product layers that the structural queries
        introduce. Nested layers of the same type are left alone: merging them would
        have to fuse the parameter blocks of layers with different numbers of nodes.

        :param cache: The shared cache of the current pass.
        :return: The simplified layer.
        """
        return self

    def normalize(self):
        """
        Normalize the weights of every sum layer of the circuit rooted here in-place.
        """
        for layer in self.all_layers():
            layer.normalize_own()

    def normalize_own(self):
        """
        Normalize the parameters stored in this layer alone in-place.
        """

    def apply_translation(self, translation: npt.NDArray):
        """
        Translate the circuit rooted here in-place.

        :param translation: The translation per variable of the circuit.
        """
        for layer in self.all_layers():
            layer.apply_translation_own(translation)

    def apply_translation_own(self, translation: npt.NDArray):
        """
        Translate the parameters of this layer alone in-place.
        """

    def apply_scaling(self, scaling: npt.NDArray):
        """
        Scale the circuit rooted here in-place.

        :param scaling: The scaling per variable of the circuit.
        """
        for layer in self.all_layers():
            layer.apply_scaling_own(scaling)

    def apply_scaling_own(self, scaling: npt.NDArray):
        """
        Scale the parameters of this layer alone in-place.
        """

    @abstractmethod
    def __deepcopy__(self, memo=None) -> Layer:
        raise NotImplementedError

    def __repr__(self):
        return f"{self.__class__.__name__}({self.number_of_nodes})"

    # %% serialization

    @classmethod
    def serialized_fields(cls) -> List[dataclasses.Field]:
        """
        :return: The dataclass fields that describe a layer, which are the ones its
            constructor takes. The caches a layer fills in on its own are declared with
            ``init=False`` and are left out.
        """
        return [field_ for field_ in dataclasses.fields(cls) if field_.init]

    def to_json(self, **kwargs) -> Dict[str, Any]:
        """
        Serialize this layer through the fields it declares.

        The parameter arrays, the child layers and the sparse edge and weight blocks are
        all types that :mod:`krrood.adapters.json_serializer` serializes generically, so
        a layer type is serializable by declaring its fields and none of them has to
        write a method per field.

        :param kwargs: Keyword arguments to hand on to the nested ``to_json`` calls.
        :return: The JSON dict.
        """
        result = super().to_json(**kwargs)
        for field_ in self.serialized_fields():
            result[field_.name] = json_serializer.to_json(
                getattr(self, field_.name), **kwargs
            )
        return result

    @classmethod
    def _from_json(cls, data: Dict[str, Any], **kwargs) -> Self:
        return cls(
            **{
                field_.name: json_serializer.from_json(data[field_.name], **kwargs)
                for field_ in cls.serialized_fields()
                if field_.name in data
            }
        )


@dataclass(eq=False, repr=False)
class InnerLayer(Layer, ABC):
    """
    Abstract base class for the layers that have child layers.
    """

    child_layers: List[Layer]
    """
    The child layers of this layer.

    The list is not copied.
    """

    _variables_cache: Optional[npt.NDArray] = field(
        default=None, init=False, repr=False
    )
    """
    Cached indices of the variables in the scope of this layer.
    """

    def reset_variables(self):
        """
        Drop the cached scope of this layer so that it is recomputed on the next access.
        """
        self._variables_cache = None

    @memoized
    def remap_variables(self, remap: npt.NDArray, cache: Optional[QueryCache] = None):
        for child_layer in self.child_layers:
            child_layer.remap_variables(remap, cache=cache)
        self.reset_variables()

    @abstractmethod
    def iterate_edges(self) -> Iterator[InnerLayerEdge]:
        """
        :return: Yields every edge from a node of this layer to a node of one of its
            child layers.
        """
        raise NotImplementedError
