"""
The recorded demo scene as an EQL (Entity Query Language) knowledge base.

EQL is krrood's pythonic relational query language. This package models the recorded
coraplex/giskardpy episode — bench objects, robot parts, action episodes, per-joint
motion — as plain dataclasses and exposes:

fresh_namespace()  -> dict for evaluating one EQL query (fresh variables)
run_query(code)    -> execute an EQL query string, return JSON-able result
graph_payload()    -> nodes/edges/details/presets for the UI knowledge graph
view_payload(name) -> one of the graph-panel tabs (knowledge / kinematics / plan /
chart)

krrood is imported lazily: without it the static viewer still works, only the EQL panel
is unavailable. Scene bundles are read from paths.scenes_dir().
"""

from __future__ import annotations

import logging

from typing_extensions import Any, Dict, List, Optional

from cram_viz.knowledge.architecture_entities import (
    Package as Package,
    PythonClass as PythonClass,
)
from cram_viz.knowledge.eql_session import run_query
from cram_viz.knowledge.knowledge_base import (
    EpisodeKnowledgeBase,
    get_knowledge_base,
    reset_knowledge_base as reset_knowledge_base,
)
from cram_viz.knowledge.presets import get_presets
from cram_viz.knowledge.scene_bundle import load_scene, load_urdf
from cram_viz.knowledge.views.architecture import (
    CLASS_CAP as CLASS_CAP,
    SUBCLASS_CAP as SUBCLASS_CAP,
    _class_id,
    _package_view,
    _subpackage_view,
    _class_view,
)
from cram_viz.knowledge.views.base import _view
from cram_viz.knowledge.views.plan import (
    _plan_view,
    shorten_action_label as shorten_action_label,
)


def _measurement_line(
    label: str, value: Optional[float], number_format: str
) -> List[str]:
    """
    A detail line for a measurement in metres, or nothing when it was not recorded.

    Showing a fabricated number would read as a fact about the scene.
    """
    if value is None:
        return []
    return ["%s: %s m" % (label, number_format % value)]


# %% the UI graph
def graph_payload() -> Dict[str, Any]:
    """
    The knowledge-graph overview: nodes, edges, details and presets.
    """
    kb = get_knowledge_base()
    nodes, edges, details = [], [], {}

    def add(node_id: str, label: str, group: str, lines: List[str]) -> None:
        """
        Append one graph node and its detail-panel entry.
        """
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "group": group,
                "title": "\n".join([label] + lines),
            }
        )
        details[node_id] = {"label": label, "group": group, "lines": lines}

    rob = kb.robot.name
    add(
        rob,
        rob,
        "robot",
        [
            "a Robot",
            "%d arm%s" % (kb.robot.arm_count, "" if kb.robot.arm_count == 1 else "s"),
            "double-click: full URDF tree",
        ],
    )
    for arm in kb.arms:
        add(
            arm.name,
            arm.name.replace("_", " "),
            "robot",
            ["an Arm", "side: " + arm.side, "gripper: " + arm.gripper.name],
        )
        edges.append({"from": rob, "to": arm.name, "kind": "prop", "label": "has part"})
        add(
            arm.gripper.name,
            arm.gripper.name.replace("_", " "),
            "robot",
            ["a Gripper", "side: " + arm.gripper.side]
            + _measurement_line("opening", arm.gripper.opening_m, "%.3f"),
        )
        edges.append(
            {
                "from": arm.name,
                "to": arm.gripper.name,
                "kind": "prop",
                "label": "has part",
            }
        )

    for bench_object in kb.objects:
        add(
            bench_object.name,
            bench_object.label,
            "object",
            [
                "a BenchObject",
                "kind: " + bench_object.kind,
                "position: " + repr(bench_object.position),
            ]
            + _measurement_line("height", bench_object.height_m, "%.2f"),
        )

    previous = None
    for episode in kb.episodes:
        add(
            episode.name,
            episode.name,
            "event",
            [
                "an ActionEpisode",
                "frames %d–%d" % (episode.start_frame, episode.end_frame),
                "duration: %.1f s" % episode.duration_s,
            ]
            + (["picks: " + episode.picks.name] if episode.picks else [])
            + (["places at: " + episode.places_at.name] if episode.places_at else []),
        )
        if previous:
            edges.append(
                {
                    "from": previous,
                    "to": episode.name,
                    "kind": "type",
                    "label": "precedes",
                }
            )
        previous = episode.name
        # the robot performs the episode (with its arm); don't wire the episode
        # straight to the arm — the arm hangs off the robot, so the chain reads
        # transport_milk → pr2 → left_arm → left_gripper
        if episode.performed_by:
            edges.append(
                {
                    "from": episode.name,
                    "to": episode.performed_by.robot,
                    "kind": "prop",
                    "label": "performed by",
                }
            )
        if episode.picks:
            edges.append(
                {
                    "from": episode.name,
                    "to": episode.picks.name,
                    "kind": "prop",
                    "label": "picks",
                }
            )
        if episode.places_at:
            edges.append(
                {
                    "from": episode.name,
                    "to": episode.places_at.name,
                    "kind": "prop",
                    "label": "places at",
                }
            )

    # the CRAM architecture cluster: repo root → packages, plus import edges
    if kb.packages:
        add(
            "cram",
            "CRAM architecture",
            "root",
            [
                "~/cognitive_robot_abstract_machine",
                "%d packages · %d Python classes" % (len(kb.packages), len(kb.classes)),
            ],
        )
        for package in kb.packages:
            add(
                package.name,
                package.name,
                "concept",
                [
                    "a Package",
                    package.description,
                    "%d modules · %d classes"
                    % (package.module_count, package.class_count),
                    "double-click to open",
                ],
            )
            edges.append(
                {
                    "from": "cram",
                    "to": package.name,
                    "kind": "prop",
                    "label": "contains",
                }
            )
        for subpackage in kb.subpackages:
            add(
                subpackage.name,
                subpackage.name.split(".", 1)[1],
                "klass",
                [
                    "a SubPackage of " + subpackage.package,
                    "%d modules · %d classes"
                    % (subpackage.module_count, subpackage.class_count),
                    "double-click to open",
                ],
            )
            edges.append(
                {
                    "from": subpackage.package,
                    "to": subpackage.name,
                    "kind": "prop",
                    "label": "contains",
                }
            )
        for source, target in kb.package_deps:
            edges.append(
                {"from": source, "to": target, "kind": "type", "label": "imports"}
            )

        # ground the demo in the architecture at the SUBPACKAGE that actually
        # realises each part (only wire to a node that exists in this view)
        def link(source: str, target: str, label: str) -> None:
            """
            Add an edge, but only if target is actually a node in this view.
            """
            if any(n["id"] == target for n in nodes):
                edges.append(
                    {"from": source, "to": target, "kind": "type", "label": label}
                )

        # anchor one representative manipulation episode (they share the stack)
        anchor = next((episode.name for episode in kb.episodes if episode.picks), None)
        if anchor:
            link(anchor, "coraplex.plans", "planned by")  # plan / designator layer
            link(anchor, "giskardpy.motion_statechart", "motion by")  # motion execution
        # every physical thing in the scene is modelled in the semantic digital twin
        link(rob, "semantic_digital_twin", "modelled in")
        for bench_object in kb.objects:
            link(bench_object.name, "semantic_digital_twin", "modelled in")

    # the executed plan tree (captured from the real PlanNode graph)
    scene, _ = load_scene()
    if scene.get("planTrees"):
        node_count = sum(_count_plan_nodes(tree) for tree in scene["planTrees"])
        add(
            "plan",
            "executed plan",
            "goal",
            [
                "the plan tree the demo actually executed",
                "%d nodes" % node_count,
                "double-click to open",
            ],
        )
        edges.append(
            {"from": "plan", "to": rob, "kind": "prop", "label": "executed by"}
        )
        for episode in kb.episodes:
            edges.append(
                {"from": "plan", "to": episode.name, "kind": "type", "label": "spans"}
            )

    status = "EQL ready · %d graph nodes · %d joints · %d CRAM classes" % (
        len(nodes),
        len(kb.joints),
        len(kb.classes),
    )
    return {
        "ok": True,
        "status": status,
        "nodes": nodes,
        "edges": edges,
        "details": details,
        "presets": get_presets(),
    }


# %% drill-down subgraphs
# Double-clicking a node in the UI asks for its inside view: package → its
# subpackages + top-level classes, subpackage → its classes (with inheritance
# edges), class → its base classes and every subclass in the repo.


# %% the graph-panel tabs
def view_payload(name: str) -> Dict[str, Any]:
    """
    One tab of the graph panel.

    ``knowledge`` is the entity graph (the default, with drill-down); the others are
    structural views of the same demo that the UI can overlay with live status from the
    bridge (see :mod:`cram_viz.live.http`, ``/plan`` and ``/chart``).
    """
    kb = get_knowledge_base()
    if name == "knowledge":
        return graph_payload()
    if name == "kinematics":
        return _urdf_view(kb)
    if name == "plan":
        return _plan_view()
    if name == "chart":
        return _chart_view()
    return {"ok": False, "error": "unknown view: %s" % name}


def _chart_view() -> Dict[str, Any]:
    """
    The (live-only) statechart tab.

    Motion statecharts only exist while giskardpy executes them: one is
    compiled per merged motion group and thrown away afterwards, and nothing
    of it is recorded into the bundle — the UI fills this view from the
    bridge's ``/chart`` while attached.
    """
    return {
        "ok": True,
        "crumb": "motion statechart",
        "nodes": [],
        "edges": [],
        "details": {},
        "layout": "hier",
        "live": "chart",
        "empty": "Motion statecharts are built and ticked at execution time. "
        "Start the demo with cram-viz-live and press ◉ Live — "
        "the statechart of the running motion group appears here, "
        "coloured by its node life cycle.",
    }


def _count_plan_nodes(tree: Dict[str, Any]) -> int:
    """
    Number of nodes in a serialized plan tree.
    """
    return 1 + sum(_count_plan_nodes(child) for child in tree.get("children", []))


def expand_node(node_id: str) -> Optional[Dict[str, Any]]:
    """
    The inside view of a double-clicked node, or None if not drillable.
    """
    kb = get_knowledge_base()
    if node_id == kb.robot.name:  # robot → full URDF kinematic tree
        return _urdf_view(kb)
    if node_id == "plan":  # → the executed plan tree
        return _plan_view()
    package = next((entry for entry in kb.packages if entry.name == node_id), None)
    if package:
        return _package_view(kb, package)
    subpackage = next(
        (entry for entry in kb.subpackages if entry.name == node_id), None
    )
    if subpackage:
        return _subpackage_view(kb, subpackage)
    python_class = next(
        (entry for entry in kb.classes if _class_id(entry) == node_id), None
    )
    if python_class:
        return _class_view(kb, python_class)
    return None


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


if __name__ == "__main__":
    # smoke test: run every preset against the active scene
    logging.basicConfig(level=logging.INFO)
    for preset in get_presets():
        try:
            result = run_query(preset["code"])
            logging.info("OK   %-32s -> %d rows", preset["text"], result["count"])
        except Exception as error:
            logging.error(
                "FAIL %-32s -> %s: %s", preset["text"], type(error).__name__, error
            )
