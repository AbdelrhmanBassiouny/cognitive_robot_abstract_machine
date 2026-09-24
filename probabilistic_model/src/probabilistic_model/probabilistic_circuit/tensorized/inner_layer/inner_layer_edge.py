from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InnerLayerEdge:
    """
    One edge of an inner layer: a node of that layer, and the node of one of its child
    layers that it points at.
    """

    node: int
    """
    The index of the node inside the layer the edge belongs to.
    """

    child_layer_index: int
    """
    The index of the child layer the edge points into, within
    :attr:`InnerLayer.child_layers`.
    """

    child_node: int
    """
    The index of the node inside that child layer.
    """
