"""
Conversion between the layered circuits and the circuits of the ``rx`` package.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

import numpy as np
import tqdm
from scipy.sparse import coo_array
from sortedcontainers import SortedSet
from typing_extensions import Dict, List, Optional, Tuple, Type

from probabilistic_model.distributions.distributions import UnivariateDistribution
from probabilistic_model.probabilistic_circuit.rx.probabilistic_circuit import (
    ProbabilisticCircuit,
    ProductUnit,
    SumUnit,
    Unit,
    leaf,
)
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import Layer
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.product_layer import (
    ProductLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.sum_layer import (
    SumLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.input_layer.base import (
    InputLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.input_layer.dirac_delta_layer import (
    DiracDeltaLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.input_layer.uniform_layer import (
    UniformLayer,
)

INPUT_LAYER_CLASSES: Tuple[Type[InputLayer], ...] = (DiracDeltaLayer, UniformLayer)
"""
The input layer classes a leaf of a rustworkx circuit can be converted into.
"""


def input_layer_class_of(distribution_class: Type) -> Type[InputLayer]:
    """
    Find the input layer class that holds distributions of a class.

    An exact match wins over an inherited one, because the distributions form their own
    hierarchy and a subclass of a distribution may need a layer of its own.

    :param distribution_class: The class of the distributions.
    :return: The matching input layer class.
    """
    for layer_class in INPUT_LAYER_CLASSES:
        if distribution_class in layer_class.get_generic_type_parameters():
            return layer_class

    for layer_class in INPUT_LAYER_CLASSES:
        if issubclass(
            distribution_class, tuple(layer_class.get_generic_type_parameters())
        ):
            return layer_class

    raise TypeError(f"Could not find an input layer class for {distribution_class}")


def input_layer_of_distributions(
    variable_index: int, distributions: List[UnivariateDistribution]
) -> InputLayer:
    """
    Create the input layer that holds a list of distributions of the same class.

    :param variable_index: The index of the variable of the distributions.
    :param distributions: The distributions, all of the same class.
    :return: The input layer.
    """
    layer_class = input_layer_class_of(type(distributions[0]))
    return layer_class.from_distributions(variable_index, distributions)


# %% from rustworkx


@dataclass
class LayerConverter:
    """
    Bookkeeping for the conversion of a circuit of the ``rx`` package into a layered
    one.
    """

    layer: Layer
    """
    The created layer.
    """

    nodes: List[Unit]
    """
    The units the layer was created from, in the order of its nodes.
    """

    hash_remap: Dict[int, int]
    """
    A map from the hash of a unit to the index of its node in the layer.
    """

    @classmethod
    def of_units(cls, layer: Layer, units: List[Unit]) -> LayerConverter:
        """
        :param layer: The layer created from the units.
        :param units: The units, in the order of the nodes of the layer.
        :return: The converter of the layer.
        """
        return cls(
            layer, units, {hash(unit): index for index, unit in enumerate(units)}
        )


def converter_of_leaves(
    units: List[Unit], progress_bar: bool = False
) -> LayerConverter:
    """
    Create an input layer from leaf units that share the class of their distribution and
    their variable.

    :param units: The leaf units.
    :param progress_bar: Whether to show a progress bar.
    :return: The converter of the created layer.
    """
    variable = units[0].variable
    iterator = (
        tqdm.tqdm(units, desc=f"Assembling input layer for {variable.name}")
        if progress_bar
        else units
    )
    layer = input_layer_of_distributions(
        units[0].probabilistic_circuit.variables.index(variable),
        [unit.distribution for unit in iterator],
    )
    return LayerConverter.of_units(layer, units)


def converter_of_sum_units(
    units: List[SumUnit],
    child_converters: List[LayerConverter],
    progress_bar: bool = False,
) -> LayerConverter:
    """
    Create a sum layer from sum units that share their scope.

    :param units: The sum units.
    :param child_converters: The converters of the layers created so far.
    :param progress_bar: Whether to show a progress bar.
    :return: The converter of the created layer.
    """
    variables = np.array(
        [
            units[0].probabilistic_circuit.variables.index(variable)
            for variable in units[0].variables
        ]
    )

    # only the layers with the same scope can be children of these sum units
    candidates = [
        child_converter
        for child_converter in child_converters
        if np.array_equal(child_converter.layer.variables, variables)
    ]

    child_layers = []
    log_weights = []
    for child_converter in candidates:
        rows, columns, values = [], [], []
        for index, unit in enumerate(
            tqdm.tqdm(units, desc="Assembling sum layer") if progress_bar else units
        ):
            for log_weight, subcircuit in unit.log_weighted_subcircuits:
                if hash(subcircuit) in child_converter.hash_remap:
                    rows.append(index)
                    columns.append(child_converter.hash_remap[hash(subcircuit)])
                    values.append(log_weight)

        # a candidate that none of these units points to is not a child layer
        if not rows:
            continue

        child_layers.append(child_converter.layer)
        log_weights.append(
            coo_array(
                (
                    np.array(values, dtype=float),
                    (np.array(rows, dtype=np.int64), np.array(columns, dtype=np.int64)),
                ),
                shape=(len(units), child_converter.layer.number_of_nodes),
            )
        )

    return LayerConverter.of_units(SumLayer(child_layers, log_weights), units)


def converter_of_product_units(
    units: List[ProductUnit],
    child_converters: List[LayerConverter],
    progress_bar: bool = False,
) -> LayerConverter:
    """
    Create a product layer from product units that share their scope.

    :param units: The product units.
    :param child_converters: The converters of the layers created so far.
    :param progress_bar: Whether to show a progress bar.
    :return: The converter of the created layer.
    """
    # only the candidates that at least one of these units points to become child
    # layers, so that the edge matrix has no empty rows
    used_child_converters: List[LayerConverter] = []
    row_of_child_converter: Dict[int, int] = {}

    rows, columns, values = [], [], []

    iterator = (
        tqdm.tqdm(units, desc="Assembling product layer") if progress_bar else units
    )
    for unit_index, unit in enumerate(iterator):
        subcircuit_hashes = {hash(subcircuit) for subcircuit in unit.subcircuits}
        for child_index, child_converter in enumerate(child_converters):
            for subcircuit_hash in subcircuit_hashes:
                if subcircuit_hash not in child_converter.hash_remap:
                    continue
                if child_index not in row_of_child_converter:
                    row_of_child_converter[child_index] = len(used_child_converters)
                    used_child_converters.append(child_converter)
                rows.append(row_of_child_converter[child_index])
                columns.append(unit_index)
                values.append(child_converter.hash_remap[subcircuit_hash])

    edges = coo_array(
        (
            np.array(values, dtype=np.int64),
            (np.array(rows, dtype=np.int64), np.array(columns, dtype=np.int64)),
        ),
        shape=(len(used_child_converters), len(units)),
    )
    layer = ProductLayer(
        [child_converter.layer for child_converter in used_child_converters], edges
    )
    return LayerConverter.of_units(layer, units)


def converter_of_units(
    units: List[Unit],
    child_converters: List[LayerConverter],
    progress_bar: bool = False,
) -> LayerConverter:
    """
    Create a layer from units of a rustworkx circuit that share their type and scope.

    :param units: The units.
    :param child_converters: The converters of the layers created so far.
    :param progress_bar: Whether to show a progress bar.
    :return: The converter of the created layer.
    """
    if units[0].is_leaf:
        return converter_of_leaves(units, progress_bar)
    if isinstance(units[0], SumUnit):
        return converter_of_sum_units(units, child_converters, progress_bar)
    return converter_of_product_units(units, child_converters, progress_bar)


def converters_of_level(
    units: List[Unit],
    child_converters: List[LayerConverter],
    progress_bar: bool = False,
) -> List[LayerConverter]:
    """
    Group one level of a rustworkx circuit into layers.

    :param units: The units that form one level of the rustworkx circuit.
    :param child_converters: The converters of the layers created so far.
    :param progress_bar: Whether to show a progress bar.
    :return: One converter per created layer.
    """
    # grouping is by exact type, not by ``isinstance``: a leaf whose distribution is a
    # subclass of another distribution would otherwise be pulled into the group of the
    # base class, whose layer cannot hold it
    groups: Dict[Tuple[Type, Tuple], List[Unit]] = {}
    for unit in units:
        unit_type = type(unit.distribution) if unit.is_leaf else type(unit)
        groups.setdefault((unit_type, tuple(unit.variables)), []).append(unit)

    return [
        converter_of_units(group, child_converters, progress_bar)
        for group in groups.values()
    ]


def root_layer_of_circuit(
    circuit: ProbabilisticCircuit, progress_bar: bool = False
) -> Layer:
    """
    Convert a circuit of the ``rx`` package into layers.

    :param circuit: The circuit to convert.
    :param progress_bar: Whether to show a progress bar.
    :return: The root layer of the converted circuit.
    :raises ValueError: If the circuit does not have exactly one root.
    """
    converters: List[LayerConverter] = []

    levels = list(circuit.layers)
    iterator = (
        tqdm.tqdm(reversed(levels), total=len(levels), desc="Creating layers")
        if progress_bar
        else reversed(levels)
    )

    for units in iterator:
        # every converter created so far is offered as a possible child, not only those
        # of the level directly below: the layering of the graph is by shortest distance
        # to the root, so an edge may skip levels
        converters = converters_of_level(units, converters, progress_bar) + converters

    root_converters = [
        converter for converter in converters if converter.nodes[0] is circuit.root
    ]
    if len(root_converters) != 1:
        raise ValueError("The circuit does not have exactly one root.")

    return root_converters[0].layer


# %% to rustworkx


@dataclass
class RustworkxCircuitBuilder:
    """
    Convert layers into the units of a circuit of the ``rx`` package, every layer once.
    """

    variables: SortedSet
    """
    The variables of the circuit, in the order the layers index them.
    """

    result: ProbabilisticCircuit = field(default_factory=ProbabilisticCircuit)
    """
    The circuit the units are created in.
    """

    progress_bar: Optional[tqdm.tqdm] = None
    """
    A progress bar that counts the converted nodes.
    """

    units_by_layer: Dict[int, List[Unit]] = field(default_factory=dict)
    """
    The units created for every layer converted so far, keyed by the id of the layer.
    """

    def units_of(self, layer: Layer) -> List[Unit]:
        """
        :param layer: The layer to convert.
        :return: One unit per node of the layer, in the order of its nodes.
        """
        if id(layer) not in self.units_by_layer:
            self.units_by_layer[id(layer)] = self.create_units(layer)
            if self.progress_bar:
                self.progress_bar.update(layer.number_of_nodes)
        return self.units_by_layer[id(layer)]

    @functools.singledispatchmethod
    def create_units(self, layer: Layer) -> List[Unit]:
        """
        Create one unit per node of a layer, together with the units of the layers
        below it.

        :param layer: The layer to convert.
        :return: The created units, in the order of the nodes of the layer.
        """
        raise TypeError(f"Could not convert a layer of type {type(layer)}")

    @create_units.register(SumLayer)
    def _create_sum_units(self, layer: SumLayer) -> List[Unit]:
        units = [
            SumUnit(probabilistic_circuit=self.result)
            for _ in range(layer.number_of_nodes)
        ]
        for log_weights, child_layer in layer.log_weighted_child_layers:
            child_units = self.units_of(child_layer)
            for node, child_node, log_weight in zip(
                log_weights.row, log_weights.col, log_weights.data
            ):
                units[node].add_subcircuit(child_units[child_node], float(log_weight))
        for unit in units:
            unit.normalize()
        return units

    @create_units.register(ProductLayer)
    def _create_product_units(self, layer: ProductLayer) -> List[Unit]:
        units = [
            ProductUnit(probabilistic_circuit=self.result)
            for _ in range(layer.number_of_nodes)
        ]
        child_units = [self.units_of(child_layer) for child_layer in layer.child_layers]
        for edge in layer.iterate_edges():
            units[edge.node].add_subcircuit(
                child_units[edge.child_layer_index][edge.child_node]
            )
        return units

    @create_units.register(InputLayer)
    def _create_leaf_units(self, layer: InputLayer) -> List[Unit]:
        return [
            leaf(distribution, self.result)
            for distribution in layer.node_distributions(self.variables[layer.variable])
        ]


def circuit_of_root_layer(
    root: Layer, variables: SortedSet, progress_bar: bool = False
) -> ProbabilisticCircuit:
    """
    Convert layers into a circuit of the ``rx`` package.

    :param root: The root layer to convert.
    :param variables: The variables of the circuit, in the order the layers index them.
    :param progress_bar: Whether to show a progress bar.
    :return: The converted circuit.
    """
    bar = (
        tqdm.tqdm(
            total=sum(layer.number_of_nodes for layer in root.all_layers()),
            desc="Converting to rx",
        )
        if progress_bar
        else None
    )
    builder = RustworkxCircuitBuilder(variables, progress_bar=bar)
    builder.units_of(root)
    return builder.result
