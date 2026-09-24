from __future__ import annotations

import numpy as np
from scipy.sparse import coo_array
from sortedcontainers import SortedSet
from typing_extensions import Iterable, List

from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import Layer
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.product_layer import (
    ProductLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.sum_layer import (
    SumLayer,
)
from probabilistic_model.probabilistic_circuit.tensorized.row_grouped_sparse_array import (
    RowGroupedSparseArray,
)


def product_of(variables: SortedSet, child_layers: List[Layer]) -> ProductLayer:
    """
    Create a product layer with a single node that multiplies one node of every child
    layer.

    :param variables: The variables of the circuit the layer belongs to.
    :param child_layers: The child layers, each contributing its first node.
    :return: The product layer.
    """
    edges = coo_array(
        (
            np.zeros(len(child_layers), dtype=np.int64),
            (np.arange(len(child_layers)), np.zeros(len(child_layers), dtype=np.int64)),
        ),
        shape=(len(child_layers), 1),
    )
    return ProductLayer(child_layers, edges)


def mixture_of(child_layers: List[Layer], log_weights: Iterable[float]) -> SumLayer:
    """
    Create a sum layer with a single node that mixes the first node of every child
    layer.

    :param child_layers: The child layers, each contributing its first node.
    :param log_weights: The logarithmic weight of every child layer.
    :return: The sum layer.
    """
    weights = list(log_weights)
    if len(weights) != len(child_layers):
        raise ValueError(
            "The number of weights has to match the number of child layers."
        )
    offsets = np.cumsum(
        [0] + [child_layer.number_of_nodes for child_layer in child_layers]
    )
    return SumLayer(
        child_layers,
        RowGroupedSparseArray.from_coordinates(
            np.array(weights, dtype=float),
            np.zeros(len(child_layers), dtype=np.int64),
            offsets[:-1],
            (1, int(offsets[-1])),
        ),
    )
