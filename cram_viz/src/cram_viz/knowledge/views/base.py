"""
Shared accumulator for building one drill-down/graph-panel subgraph view.
"""

from __future__ import annotations

from typing_extensions import Any, List


def _view() -> tuple:
    """
    Fresh (nodes, edges, details, add) accumulators for one subgraph.
    """
    nodes, edges, details = [], [], {}

    def add(
        node_id: str, label: str, group: str, lines: List[str], **extra: Any
    ) -> None:
        """
        Append one graph node (plus arbitrary extra fields) and its detail entry.
        """
        node = {
            "id": node_id,
            "label": label,
            "group": group,
            "title": "\n".join([label] + lines),
        }
        node.update(extra)
        nodes.append(node)
        details[node_id] = {"label": label, "group": group, "lines": lines}

    return nodes, edges, details, add
