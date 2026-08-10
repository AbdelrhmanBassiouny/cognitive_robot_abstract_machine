"""
The knowledge-graph overview: nodes, edges, details and presets for the UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from typing_extensions import Any, Dict, List, Optional

from coraplex.datastructures.enums import Arms
from semantic_digital_twin.spatial_types import Point3

from cramera.knowledge.enums import EdgeKind, NodeGroup
from cramera.knowledge.knowledge_base import get_knowledge_base
from cramera.knowledge.presets import Preset, get_presets
from cramera.knowledge.scene_bundle import load_scene
from cramera.knowledge.subgraph import (
    DetailEntry,
    GraphEdge,
    GraphNode,
    SubgraphAccumulator,
)


@dataclass
class KnowledgeGraphPayload:
    """
    The knowledge-graph overview: nodes, edges, details and presets.
    """

    ok: bool
    """
    Always ``True`` — this view has no failure mode.
    """

    status: str
    """
    Human-readable summary line shown above the graph panel.
    """

    nodes: List[GraphNode]
    """
    Every node in this view.
    """

    edges: List[GraphEdge]
    """
    Every edge in this view.
    """

    details: Dict[str, DetailEntry]
    """
    Detail-panel entry per node id.
    """

    presets: List[Preset]
    """
    Ready-made EQL queries for the EQL panel.
    """

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the frontend's graph panel expects.
        """
        return {
            "ok": self.ok,
            "status": self.status,
            "nodes": [node.to_payload() for node in self.nodes],
            "edges": [edge.to_payload() for edge in self.edges],
            "details": {
                node_id: asdict(entry) for node_id, entry in self.details.items()
            },
            "presets": [asdict(preset) for preset in self.presets],
        }


def _measurement_line(
    label: str, value: Optional[float], number_format: str
) -> List[str]:
    """
    A detail line for a measurement in metres, or nothing when it was not recorded.

    Showing a fabricated number would read as a fact about the scene.

    :param label: Label the measurement is shown under.
    :param value: The recorded measurement in metres, or None if it was not recorded.
    :param number_format:``%``-style format applied to ``value``.
    """
    if value is None:
        return []
    return ["%s: %s m" % (label, number_format % value)]


def _side_label(side: Optional[Arms]) -> str:
    """
    Lower-case display name of an arm side, or ``unknown`` when it could not be
    inferred.

    :param side: The arm side to label.
    """
    return side.name.lower() if side is not None else "unknown"


def _position_label(position: Point3) -> str:
    """
    A position's coordinates, formatted to two decimal places.

    :class:`Point3` has no plain-value ``__repr__`` of its own (it is a CasADi-symbolic
    type), so the coordinates are read out explicitly.

    :param position: The position to format.
    """
    return "(%.2f, %.2f, %.2f)" % tuple(position.to_np().tolist()[:3])


def _count_plan_nodes(tree: Dict[str, Any]) -> int:
    """
    Number of nodes in a serialized plan tree.

    :param tree: The serialized plan tree to count.
    """
    return 1 + sum(_count_plan_nodes(child) for child in tree.get("children", []))


def graph_payload() -> KnowledgeGraphPayload:
    """
    The knowledge-graph overview: nodes, edges, details and presets.
    """
    knowledge_base = get_knowledge_base()
    view = SubgraphAccumulator()

    robot_name = knowledge_base.robot.name
    view.add(
        robot_name,
        robot_name,
        NodeGroup.ROBOT,
        [
            "a Robot",
            "%d arm%s"
            % (
                knowledge_base.robot.arm_count,
                "" if knowledge_base.robot.arm_count == 1 else "s",
            ),
            "double-click: full URDF tree",
        ],
    )
    for arm in knowledge_base.arms:
        view.add(
            arm.name,
            arm.name.replace("_", " "),
            NodeGroup.ROBOT,
            [
                "an Arm",
                "side: " + _side_label(arm.side),
                "gripper: " + arm.gripper.name,
            ],
        )
        view.add_edge(robot_name, arm.name, EdgeKind.PROPERTY, "has part")
        view.add(
            arm.gripper.name,
            arm.gripper.name.replace("_", " "),
            NodeGroup.ROBOT,
            ["a Gripper", "side: " + _side_label(arm.gripper.side)]
            + _measurement_line("opening", arm.gripper.opening_metres, "%.3f"),
        )
        view.add_edge(arm.name, arm.gripper.name, EdgeKind.PROPERTY, "has part")

    for bench_object in knowledge_base.objects:
        view.add(
            bench_object.name,
            bench_object.label,
            NodeGroup.OBJECT,
            [
                "a BenchObject",
                "kind: " + bench_object.kind,
                "position: " + _position_label(bench_object.position),
            ]
            + _measurement_line("height", bench_object.height_metres, "%.2f"),
        )

    previous = None
    for episode in knowledge_base.episodes:
        view.add(
            episode.name,
            episode.name,
            NodeGroup.EVENT,
            [
                "an ActionEpisode",
                "frames %d–%d" % (episode.start_frame, episode.end_frame),
                "duration: %.1f s" % episode.duration_seconds,
            ]
            + (["picks: " + episode.picks.name] if episode.picks else [])
            + (["places at: " + episode.places_at.name] if episode.places_at else []),
        )
        if previous:
            view.add_edge(previous, episode.name, EdgeKind.TYPE, "precedes")
        previous = episode.name
        # the robot performs the episode (with its arm); don't wire the episode
        # straight to the arm — the arm hangs off the robot, so the chain reads
        # transport_milk → pr2 → left_arm → left_gripper
        if episode.performed_by:
            view.add_edge(
                episode.name,
                episode.performed_by.robot,
                EdgeKind.PROPERTY,
                "performed by",
            )
        if episode.picks:
            view.add_edge(episode.name, episode.picks.name, EdgeKind.PROPERTY, "picks")
        if episode.places_at:
            view.add_edge(
                episode.name, episode.places_at.name, EdgeKind.PROPERTY, "places at"
            )

    # the CRAM architecture cluster: repo root → packages, plus import edges
    if knowledge_base.packages:
        view.add(
            "cram",
            "CRAM architecture",
            NodeGroup.ROOT,
            [
                "~/cognitive_robot_abstract_machine",
                "%d packages · %d Python classes"
                % (len(knowledge_base.packages), len(knowledge_base.classes)),
            ],
        )
        for package in knowledge_base.packages:
            view.add(
                package.name,
                package.name,
                NodeGroup.CONCEPT,
                [
                    "a Package",
                    package.description,
                    "%d modules · %d classes"
                    % (package.module_count, package.class_count),
                    "double-click to open",
                ],
            )
            view.add_edge("cram", package.name, EdgeKind.PROPERTY, "contains")
        for subpackage in knowledge_base.subpackages:
            view.add(
                subpackage.name,
                subpackage.name.split(".", 1)[1],
                NodeGroup.SUBPACKAGE,
                [
                    "a SubPackage of " + subpackage.package,
                    "%d modules · %d classes"
                    % (subpackage.module_count, subpackage.class_count),
                    "double-click to open",
                ],
            )
            view.add_edge(
                subpackage.package, subpackage.name, EdgeKind.PROPERTY, "contains"
            )
        for dependency in knowledge_base.package_dependencies:
            view.add_edge(
                dependency.source, dependency.target, EdgeKind.TYPE, "imports"
            )

        # ground the demo in the architecture at the SUBPACKAGE that actually
        # realises each part (only wire to a node that exists in this view)
        def link(source: str, target: str, label: str) -> None:
            """
            Add an edge, but only if target is actually a node in this view.

            :param source: Id of the edge's source node.
            :param target: Id of the edge's target node; the edge is dropped if this
                  node is not in the view.
            :param label: Label shown on the edge.
            """
            if any(node.id == target for node in view.nodes):
                view.add_edge(source, target, EdgeKind.TYPE, label)

        # anchor one representative manipulation episode (they share the stack)
        anchor = next(
            (episode.name for episode in knowledge_base.episodes if episode.picks), None
        )
        if anchor:
            link(anchor, "coraplex.plans", "planned by")  # plan / designator layer
            link(anchor, "giskardpy.motion_statechart", "motion by")  # motion execution
        # every physical thing in the scene is modelled in the semantic digital twin
        link(robot_name, "semantic_digital_twin", "modelled in")
        for bench_object in knowledge_base.objects:
            link(bench_object.name, "semantic_digital_twin", "modelled in")

    # the executed plan tree (captured from the real PlanNode graph)
    scene = load_scene().scene
    if scene.get("planTrees"):
        node_count = sum(_count_plan_nodes(tree) for tree in scene["planTrees"])
        view.add(
            "plan",
            "executed plan",
            NodeGroup.GOAL,
            [
                "the plan tree the demo actually executed",
                "%d nodes" % node_count,
                "double-click to open",
            ],
        )
        view.add_edge("plan", robot_name, EdgeKind.PROPERTY, "executed by")
        for episode in knowledge_base.episodes:
            view.add_edge("plan", episode.name, EdgeKind.TYPE, "spans")

    status = "EQL ready · %d graph nodes · %d joints · %d CRAM classes" % (
        len(view.nodes),
        len(knowledge_base.joints),
        len(knowledge_base.classes),
    )
    return KnowledgeGraphPayload(
        True, status, view.nodes, view.edges, view.details, get_presets()
    )
