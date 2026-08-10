"""
Dispatch a graph-panel tab name or a double-clicked node id to its view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from typing_extensions import Any, Dict, Optional

from cramera.knowledge.graph_payload import KnowledgeGraphPayload, graph_payload
from cramera.knowledge.knowledge_base import get_knowledge_base
from cramera.knowledge.views.architecture import (
    ArchitectureViews,
    SubgraphViewPayload,
)
from cramera.knowledge.views.chart import ChartViewPayload, _chart_view
from cramera.knowledge.views.kinematics import UrdfViewPayload, _urdf_view
from cramera.knowledge.views.plan_tree import PlanViewPayload, _plan_view


@dataclass
class UnknownViewPayload:
    """
    The error payload returned for a graph-panel tab name that does not exist.
    """

    ok: bool
    """
    Always ``False``.
    """

    error: str
    """
    Human-readable description of the unknown tab name.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the frontend expects.
        """
        return {"ok": self.ok, "error": self.error}


#: any payload one of the graph-panel tabs or drill-down subgraphs can return
ViewPayload = Union[
    KnowledgeGraphPayload,
    ChartViewPayload,
    UrdfViewPayload,
    PlanViewPayload,
    SubgraphViewPayload,
]


def view_payload(name: str) -> Union[ViewPayload, UnknownViewPayload]:
    """
    One tab of the graph panel.

    ``knowledge`` is the entity graph (the default, with drill-down); the others are
    structural views of the same demo that the UI can overlay with live status from the
    bridge (see :mod:`cramera.live.http`, ``/plan`` and ``/chart``).

    :param name: Name of the requested tab.
    """
    knowledge_base = get_knowledge_base()
    if name == "knowledge":
        return graph_payload()
    if name == "kinematics":
        return _urdf_view(knowledge_base)
    if name == "plan":
        return _plan_view()
    if name == "chart":
        return _chart_view()
    return UnknownViewPayload(False, "unknown view: %s" % name)


def expand_node(node_id: str) -> Optional[ViewPayload]:
    """
    The inside view of a double-clicked node, or None if not drillable.

    :param node_id: Id of the double-clicked node.
    """
    knowledge_base = get_knowledge_base()
    if node_id == knowledge_base.robot.name:  # robot → full URDF kinematic tree
        return _urdf_view(knowledge_base)
    if node_id == "plan":  # → the executed plan tree
        return _plan_view()
    package = next(
        (entry for entry in knowledge_base.packages if entry.name == node_id), None
    )
    if package:
        return ArchitectureViews.package_view(knowledge_base, package)
    subpackage = next(
        (entry for entry in knowledge_base.subpackages if entry.name == node_id), None
    )
    if subpackage:
        return ArchitectureViews.subpackage_view(knowledge_base, subpackage)
    python_class = next(
        (entry for entry in knowledge_base.classes if entry.qualified_name == node_id),
        None,
    )
    if python_class:
        return ArchitectureViews.class_view(knowledge_base, python_class)
    return None
