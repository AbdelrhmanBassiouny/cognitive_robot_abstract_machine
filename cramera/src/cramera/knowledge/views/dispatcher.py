"""
Dispatch a graph-panel tab name or a double-clicked node id to its view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing_extensions import Any, Dict, Optional

from cramera.knowledge.graph_payload import KnowledgeGraphPayload
from cramera.knowledge.knowledge_base import get_knowledge_base
from cramera.knowledge.subgraph import GraphPanelPayload
from cramera.knowledge.views.architecture import SubgraphViewPayload
from cramera.knowledge.views.chart import ChartViewPayload
from cramera.knowledge.views.kinematics import UrdfViewPayload
from cramera.knowledge.views.plan_tree import PlanViewPayload


@dataclass(kw_only=True)
class UnknownViewPayload(GraphPanelPayload):
    """
    The error payload returned for a graph-panel tab name that does not exist.
    """

    ok: bool = False
    """
    Always ``False``.
    """

    error: str = ""
    """
    Human-readable description of the unknown tab name.
    """

    def panel_options(self) -> Dict[str, Any]:
        """
        The error message; there is no graph to describe.
        """
        return {"error": self.error}


def view_payload(name: str) -> GraphPanelPayload:
    """
    One tab of the graph panel.

    ``knowledge`` is the entity graph (the default, with drill-down); the others are
    structural views of the same demo that the UI can overlay with live status from the
    bridge (see :mod:`cramera.live.http`, ``/plan`` and ``/chart``).

    Every view declares the tab it serves as :attr:`GraphPanelPayload.TAB`, so adding
    one is a matter of subclassing rather than of extending this function.

    :param name: Name of the requested tab.
    """
    for payload_type in GraphPanelPayload.__subclasses__():
        if payload_type.TAB == name:
            return payload_type.of_tab()
    return UnknownViewPayload(error="unknown view: %s" % name)


def expand_node(node_id: str) -> Optional[GraphPanelPayload]:
    """
    The inside view of a double-clicked node, or None if not drillable.

    :param node_id: Id of the double-clicked node.
    """
    knowledge_base = get_knowledge_base()
    if node_id == knowledge_base.robot.name:  # robot → full URDF kinematic tree
        return UrdfViewPayload.of_knowledge_base(knowledge_base)
    if node_id == "plan":  # → the executed plan tree
        return PlanViewPayload.of_tab()
    package = next(
        (entry for entry in knowledge_base.packages if entry.name == node_id), None
    )
    if package:
        return SubgraphViewPayload.for_package(knowledge_base, package)
    subpackage = next(
        (entry for entry in knowledge_base.subpackages if entry.name == node_id), None
    )
    if subpackage:
        return SubgraphViewPayload.for_subpackage(knowledge_base, subpackage)
    python_class = next(
        (entry for entry in knowledge_base.classes if entry.qualified_name == node_id),
        None,
    )
    if python_class:
        return SubgraphViewPayload.for_class(knowledge_base, python_class)
    return None
