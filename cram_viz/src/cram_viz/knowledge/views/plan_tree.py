"""
The executed-plan-tree drill-down/tab view.

Named ``plan_tree`` rather than ``plan`` to keep it distinct from coraplex's own
``Plan``/``PlanNode`` types: this module renders the serialized tree of plan nodes
recorded in a scene bundle, not a coraplex ``Plan`` itself.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from typing_extensions import Any, Dict, Optional, Tuple

from cram_viz.knowledge.scene_bundle import load_scene
from cram_viz.knowledge.views.base import _view


class PlanNodeGroup(str, Enum):
    """
    Node colour group of the plan view's graph panel.
    """

    EVENT = "event"
    ROBOT = "robot"
    GOAL = "goal"
    OBJECT = "object"
    OTHER = "ind"


@dataclass(frozen=True)
class PlanLegendEntry:
    """
    One row of the plan view's legend.
    """

    group: PlanNodeGroup
    """
    Node colour group this row explains.
    """

    label: str
    """
    Human-readable name shown next to the group's colour.
    """


#: plan-node kind → node colour group of the graph panel
PLAN_GROUPS: Dict[str, PlanNodeGroup] = {
    "ActionNode": PlanNodeGroup.EVENT,
    "MotionNode": PlanNodeGroup.ROBOT,
    "ConditionNode": PlanNodeGroup.GOAL,
    "AttachNode": PlanNodeGroup.OBJECT,
    "DetachNode": PlanNodeGroup.OBJECT,
}

#: legend rows of the plan view
PLAN_LEGEND: Tuple[PlanLegendEntry, ...] = (
    PlanLegendEntry(PlanNodeGroup.EVENT, "Action"),
    PlanLegendEntry(PlanNodeGroup.ROBOT, "Motion"),
    PlanLegendEntry(PlanNodeGroup.GOAL, "Condition"),
    PlanLegendEntry(PlanNodeGroup.OBJECT, "Attach / detach"),
    PlanLegendEntry(PlanNodeGroup.OTHER, "Other plan node"),
)


def shorten_action_label(label: str) -> str:
    """
    Drop the redundant ``Action`` suffix from a plan-node label.

    Only the suffix goes: a label that merely *contains* the word, such as
    ``ActionNode``, is left alone.
    """
    return label.removesuffix("Action") or label


def _plan_view() -> Dict[str, Any]:
    """
    The executed plan as a tree, one node per plan node the demo ran.

    The recorded statuses are thin on purpose: coraplex performs only the
    plan *root* (``Plan.perform`` → ``root.perform``), while
    ``ActionNode.notify`` merely expands its children into the merged motion
    statechart. So every inner node of a recorded tree reads ``CREATED``, and
    real per-step progress only shows up while the live bridge is attached
    (it derives it from the statechart life cycle).
    """
    scene, _ = load_scene()
    trees = scene.get("planTrees") or []
    nodes, edges, details, add = _view()
    counter = [0]

    def walk(tree: Dict[str, Any], parent: Optional[str]) -> None:
        """
        Add this plan node (with a freshly assigned id) and recurse into its children.
        """
        node_id = "pn%d" % counter[0]
        counter[0] += 1
        status = tree.get("status") or "CREATED"
        lines = ["a " + tree.get("kind", "PlanNode"), "status: " + status]
        if tree.get("arm"):
            lines.append("arm: " + tree["arm"])
        if tree.get("target"):
            lines.append("target: " + tree["target"])
        label = shorten_action_label(tree.get("label", "?"))
        add(
            node_id,
            label,
            PLAN_GROUPS.get(tree.get("kind"), PlanNodeGroup.OTHER),
            lines,
            status=status,
        )
        if parent:
            edges.append(
                {"from": parent, "to": node_id, "kind": "prop", "label": "has step"}
            )
        for child in tree.get("children", []):
            walk(child, node_id)

    for tree in trees:
        walk(tree, None)
    return {
        "ok": True,
        "crumb": "executed plan",
        "nodes": nodes,
        "edges": edges,
        "details": details,
        "legend": [asdict(entry) for entry in PLAN_LEGEND],
        "layout": "hier",
        "live": "plan",
        "statusLegend": True,
        "empty": "No plan tree in this bundle — re-run cram-viz-onboard.",
    }
