"""
The knowledge-graph overview: nodes, edges, details and presets for the UI.
"""

from __future__ import annotations

from typing_extensions import Any, Dict, List, Optional

from cram_viz.knowledge.knowledge_base import get_knowledge_base
from cram_viz.knowledge.presets import get_presets
from cram_viz.knowledge.scene_bundle import load_scene


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


def _count_plan_nodes(tree: Dict[str, Any]) -> int:
    """
    Number of nodes in a serialized plan tree.
    """
    return 1 + sum(_count_plan_nodes(child) for child in tree.get("children", []))


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
