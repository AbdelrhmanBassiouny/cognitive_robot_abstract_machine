"""
The scene robot's URDF kinematic-tree drill-down/tab view.
"""

from __future__ import annotations

from typing_extensions import TYPE_CHECKING, Any, Dict

from cram_viz.knowledge.scene_bundle import load_scene, load_urdf
from cram_viz.knowledge.views.base import _view

if TYPE_CHECKING:
    from cram_viz.knowledge.knowledge_base import EpisodeKnowledgeBase

#: the one URDF joint type that cannot move
FIXED_JOINT_TYPE = "fixed"


def _is_movable(joint: Dict[str, str]) -> bool:
    """
    Whether a URDF joint can move (every type except ``fixed``).
    """
    return joint["type"] != FIXED_JOINT_TYPE


def _urdf_view(knowledge_base: EpisodeKnowledgeBase) -> Dict[str, Any]:
    """
    The scene robot's URDF as a kinematic tree.

    Every link is a node, every joint an edge (parent → child); movable joints are solid
    edges, fixed ones dashed. Links are coloured by robot part from the recorded
    annotation.
    """
    links, joints = load_urdf()
    nodes, edges, details, add = _view()
    if not links:
        return {
            "ok": True,
            "crumb": knowledge_base.robot.name + " · URDF (not found)",
            "nodes": [],
            "edges": [],
            "details": {},
        }

    scene, _ = load_scene()
    parts = (scene.get("robot") or {}).get("parts") or {}
    link_to_part = {
        link: part for part, part_links in parts.items() for link in part_links
    }

    def chain_group(link_name: str) -> str:
        """
        The visual group (colour) a kinematic-chain link is bucketed into.
        """
        part = link_to_part.get(link_name, "").lower()
        if "gripper" in part or "hand" in part or "effector" in part:
            return "object"  # grippers (teal)
        if "left" in part:
            return "robot"  # left arm (pink)
        if "right" in part:
            return "event"  # right arm (purple)
        lowered = link_name.lower()
        if any(
            keyword in lowered
            for keyword in ("head", "stereo", "sensor", "kinect", "camera", "laser")
        ):
            return "goal"  # head / sensors (amber)
        return "concept"  # base, torso, casters (green)

    # which joint drives each link (child link → its parent joint), for tooltips
    parent_joint = {joint["child"]: joint for joint in joints}
    for link in links:
        joint = parent_joint.get(link)
        lines = ["a URDF Link"]
        if joint:
            lines.append("joint: %s (%s)" % (joint["name"], joint["type"]))
            lines.append("parent link: " + joint["parent"])
        else:
            lines.append("root link")
        add("urdf:" + link, link, chain_group(link), lines)
    for joint in joints:
        if ("urdf:" + joint["parent"]) in details and (
            "urdf:" + joint["child"]
        ) in details:
            edges.append(
                {
                    "from": "urdf:" + joint["parent"],
                    "to": "urdf:" + joint["child"],
                    "kind": "prop" if _is_movable(joint) else "type",
                    "label": "%s (%s)" % (joint["name"], joint["type"]),
                }
            )
    movable_count = sum(1 for joint in joints if _is_movable(joint))
    details["urdf:" + links[0]]["lines"].append(
        "%d links · %d joints (%d movable)" % (len(links), len(joints), movable_count)
    )
    legend = [
        {"group": "concept", "label": "Base / torso"},
        {"group": "robot", "label": "Left arm"},
        {"group": "event", "label": "Right arm"},
        {"group": "object", "label": "Grippers"},
        {"group": "goal", "label": "Head / sensors"},
    ]
    # force-directed, not hierarchical: the chains read better when the arms and
    # the sensor head spread out around the base than as one wide LR tree
    return {
        "ok": True,
        "crumb": knowledge_base.robot.name + " · URDF",
        "nodes": nodes,
        "edges": edges,
        "details": details,
        "legend": legend,
    }
