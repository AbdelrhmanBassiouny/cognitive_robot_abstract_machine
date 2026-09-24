from __future__ import annotations

from dataclasses import dataclass

import numpy.typing as npt
from typing_extensions import TYPE_CHECKING, Dict, Iterable, List, Self

if TYPE_CHECKING:
    from probabilistic_model.probabilistic_circuit.tensorized.inner_layer.base import (
        Layer,
    )


@dataclass
class ForwardSampleAssignment:
    """
    Bookkeeping for a top-down sampling pass over a circuit.

    A layer routes the output rows assigned to each of its nodes to the nodes of its
    child layers; a child layer that is shared by several parents accumulates rows from
    each of them before it is its own turn to route them further.
    """

    rows_by_node: Dict[int, List[List[npt.NDArray]]]
    """
    For every layer, indexed by its id, the row-index arrays assigned to each of its
    nodes so far.
    """

    @classmethod
    def for_layers(cls, layers: Iterable[Layer]) -> Self:
        """
        :param layers: Every layer that will be visited during the pass.
        :return: An assignment with an empty bucket for every node of every layer.
        """
        return cls(
            {id(layer): [[] for _ in range(layer.number_of_nodes)] for layer in layers}
        )

    def assign(self, layer: Layer, node: int, rows: npt.NDArray) -> None:
        """
        Route output rows to one node of a layer.

        :param layer: The layer the node belongs to.
        :param node: The index of the node within that layer.
        :param rows: The output rows drawn from that node.
        """
        self.rows_by_node[id(layer)][node].append(rows)

    def rows_of(self, layer: Layer) -> List[List[npt.NDArray]]:
        """
        :param layer: The layer to read the assignment of.
        :return: The row-index arrays assigned to every node of that layer so far, one
            list per node.
        """
        return self.rows_by_node[id(layer)]
