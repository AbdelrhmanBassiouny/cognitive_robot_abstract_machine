"""
Turn a coraplex demo into a self-contained web-viewer scene.

Runs the demo file *unmodified* under instrumentation and emits a scene bundle
into :func:`cram_viz.paths.scenes_dir`::

    <scenes dir>/<name>/
        scene.json         models, robot parts, objects, segments, targets
        trajectory.json    per-tick joints + robot base + object world poses
        <model>.urdf       package:// resolved & rewritten
        meshes/...         all meshes + textures the scene needs

What the hooks capture while the demo runs:
  - every package:// asset resolution and every URDF/STL the world loads
  - per-tick positions of all movable connections (giskardpy Executor.tick)
  - world pose of the robot base and of every loose (STL) object
  - one segment per executed plan ActionNode, with nesting depth
  - the robot's semantic annotation: base body, arms, end-effector link sets

Usage (the interpreter needs the CRAM stack on it)::

    cram-viz-onboard path/to/demo.py --name pr2_kitchen
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import math
import os
import runpy
import shutil
import sys
import time
from pathlib import Path

from semantic_digital_twin.world_description.connections import ActiveConnection1DOF
from typing_extensions import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
    Sequence,
    TYPE_CHECKING,
)

from cram_viz import paths
from cram_viz.body_geometry import BodyExtent
from cram_viz.live.bridge import ROBOT_BASE_KEY
from cram_viz.onboard.bundle_urdf import bundle_urdf
from cram_viz.palette import ObjectPalette

if TYPE_CHECKING:
    from coraplex.plans.executables import Executable
    from coraplex.plans.plan_node import ActionNode
    from giskardpy.executor import Executor
    from semantic_digital_twin.adapters.urdf import URDFParser
    from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)

#: when this process started, so progress lines can show elapsed recording time
_STARTED_AT = time.time()

#: decimal places poses and joint positions are rounded to in the bundle
POSE_PRECISION = 5

#: how many recorded frames pass between progress lines
FRAME_LOG_INTERVAL = 2000

#: upper bound on the plan nodes written into a bundle
MAX_SERIALIZED_PLAN_NODES = 400

#: frame rate assumed when the controller does not report its timestep
FALLBACK_FRAMES_PER_SECOND = 50.0

#: the slowest playback the viewer is given, however hard the recording is downsampled
MINIMUM_FRAMES_PER_SECOND = 10

#: how far below the lowest recorded place pose the place marker is drawn, in metres
PLACE_TARGET_DROP = 0.02

#: half-extent of the draggable place area around the recorded place poses, in metres
PLACE_BOUNDS_MARGIN = 0.55

#: extra room in front of the place area, so a target can be dragged towards the robot
PLACE_BOUNDS_FRONT_MARGIN = 0.65

#: how far beyond the objects' spawn poses they may be dragged, in metres
DRAG_BOUNDS_MARGIN_X = 0.35
DRAG_BOUNDS_MARGIN_Y = 0.6

#: how many of a model's links are probed to find its prefix in the composed world
PREFIX_PROBE_LINKS = 12

#: frame count a bundle is downsampled towards when no explicit step is given
TARGET_BUNDLE_FRAMES = 1500

#: how many unresolved assets the summary lists before truncating
MISSING_ASSETS_LOGGED = 10


@runtime_checkable
class NamesAWorldEntity(Protocol):
    """
    Anything carrying a world-entity name, such as a body a designator refers to.
    """

    name: Any


@runtime_checkable
class DescribesAnAction(Protocol):
    """
    A plan node carrying the designator that describes what it does.
    """

    designator: Any


@runtime_checkable
class ReportsAStatus(Protocol):
    """
    A plan node carrying its own execution status.
    """

    status: Any


@runtime_checkable
class HasChildren(Protocol):
    """
    A plan node with a child list to descend into.
    """

    children: Any


@runtime_checkable
class HasAParent(Protocol):
    """
    A plan node that can be walked upwards to its tree's root.
    """

    parent: Any


@runtime_checkable
class HasBodies(Protocol):
    """
    A robot part exposing the bodies it is made of.
    """

    bodies: Any


@runtime_checkable
class HasAnEndEffector(Protocol):
    """
    A manipulator carrying an end effector, which not every arm annotation does.
    """

    end_effector: Any


def log(*parts: object) -> None:
    """
    Emit a progress line prefixed with the elapsed recording time.
    """
    logger.info(
        "[%6.1fs] %s",
        time.time() - _STARTED_AT,
        " ".join(str(part) for part in parts),
    )


# %% recorder
class Recorder:
    """
    Records one demo run: assets, per-tick motion and the executed plan.

    .. note:: The CRAM-stack imports inside the ``install_*`` hook methods are
       intentionally local. A hook must patch the class *before* the demo
       imports it, and this module is imported by the ``cram-viz-onboard``
       console script, which has to stay importable without the CRAM stack
       installed. This is one of the documented exceptions to the
       imports-at-top rule.
    """

    def __init__(self) -> None:
        self.resolutions: Dict[str, str] = {}
        """
        ``package://`` URI to the path it resolved to while the demo ran.
        """

        self.urdf_sources: List[str] = []
        """
        URDF/xacro files the world was built from, in load order.
        """

        self.mesh_sources: List[str] = []
        """
        Mesh files of the loose objects, in load order.
        """

        self.frames: List[Dict[str, float]] = []
        """
        Per-tick joint positions, keyed by prefixed connection name.
        """

        self.base_frames: List[Optional[List[float]]] = []
        """
        Per-tick robot base pose as ``[x, y, z, qx, qy, qz, qw]``.
        """

        self.object_frames: List[Dict[str, List[float]]] = []
        """
        Per-tick world pose of every tracked object, keyed by mesh basename.
        """

        self.actions: List[Dict[str, Any]] = []
        """
        One entry per parsed action: its class, arm and target object.
        """

        self.plan_nodes: List[Any] = []
        """
        The plan nodes the demo parsed, used to serialize the executed plan tree.
        """

        self.world: Optional[Any] = None
        """
        The executing world, captured on the first tick.
        """

        self.robot: Optional[Any] = None
        """
        The robot annotation of :attr:`world`.
        """

        self.control_dt: Optional[float] = None
        """
        The controller's timestep, from which the recording's frame rate follows.
        """

        self._connections: Optional[List[Any]] = None
        """
        Connections whose position is recorded; None until the first tick binds.
        """

        self._bodies: Optional[Dict[str, Any]] = None
        """
        Recorded bodies by mesh basename, plus :data:`ROBOT_BASE_KEY`.
        """

    # %% asset hooks
    def install_asset_hooks(self) -> None:
        """
        Record every asset resolution so the bundler can copy the files.
        """
        from semantic_digital_twin.adapters.mesh import STLParser
        from semantic_digital_twin.adapters.package_resolver import PackageUriResolver
        from semantic_digital_twin.adapters.urdf import URDFParser

        recorder = self

        original_resolve = PackageUriResolver.resolve

        def resolve(self: PackageUriResolver, uri: str) -> str:
            """
            Resolve as usual, but remember the uri -> path mapping.
            """
            resolved = original_resolve(self, uri)
            recorder.resolutions[uri] = resolved
            return resolved

        PackageUriResolver.resolve = resolve

        original_from_file = URDFParser.from_file.__func__

        def from_file(cls: Any, file_path: str, **kwargs: Any) -> URDFParser:
            """
            Parse as usual, but remember this URDF/xacro source file.
            """
            if file_path not in recorder.urdf_sources:
                recorder.urdf_sources.append(file_path)
            return original_from_file(cls, file_path, **kwargs)

        URDFParser.from_file = classmethod(from_file)

        original_init = STLParser.__init__

        def initialize(
            self: STLParser, file_path: str, *args: Any, **kwargs: Any
        ) -> None:
            """
            Initialize as usual, but remember this loose object's mesh file.
            """
            if file_path not in recorder.mesh_sources:
                recorder.mesh_sources.append(file_path)
            return original_init(self, file_path, *args, **kwargs)

        STLParser.__init__ = initialize

    # %% trajectory hook
    def install_tick_hook(self) -> None:
        """
        Wrap Executor.tick so every simulation step is snapshotted.
        """
        from giskardpy.executor import Executor

        recorder = self
        original_tick = Executor.tick

        def tick(self: Executor, *args: Any, **kwargs: Any) -> None:
            """
            Run the real tick, then record its resulting world state.
            """
            result = original_tick(self, *args, **kwargs)
            recorder.record_frame(self)
            return result

        Executor.tick = tick

    def bind_to_executor(self, executor: Executor) -> None:
        """
        Locate the world, robot and recordable objects of a running executor.

        Deferred until the first tick, because the world does not exist any earlier.
        """
        from semantic_digital_twin.robots.robot_parts import AbstractRobot

        self.world = executor.context.world
        self.control_dt = executor.context.qp_controller_config.control_dt
        robots = self.world.get_semantic_annotations_by_type(AbstractRobot)
        self.robot = robots[0] if robots else None
        self._bodies = {}
        if self.robot is not None:
            self._bodies[ROBOT_BASE_KEY] = self.robot.root
        for mesh_source in self.mesh_sources:
            name = os.path.basename(mesh_source)
            body = self.world.get_body_by_name(name)
            if body is not None:
                self._bodies[name] = body
        self._connections = [
            connection
            for connection in self.world.connections or []
            if isinstance(connection, ActiveConnection1DOF)
        ]
        log(
            "bound: robot=%s, %d movable connections, objects=%s"
            % (
                type(self.robot).__name__ if self.robot else None,
                len(self._connections),
                [key for key in self._bodies if key != ROBOT_BASE_KEY],
            )
        )

    @staticmethod
    def _pose_as_position_quaternion(body: Body) -> List[float]:
        """
        A body's world pose as ``[x, y, z, qx, qy, qz, qw]``.
        """
        pose = body.global_pose
        translation = pose.to_position().to_np().flatten()
        quaternion = pose.to_quaternion().to_np().flatten()
        return [
            round(float(value), POSE_PRECISION)
            for value in (*translation[:3], *quaternion[:4])
        ]

    def record_frame(self, executor: Executor) -> None:
        """
        Append one frame: every movable connection's position, the robot base pose
        and every tracked object's pose.
        """
        if self._connections is None:
            self.bind_to_executor(executor)
        self.frames.append(
            {
                str(connection.name): round(float(connection.position), POSE_PRECISION)
                for connection in self._connections
            }
        )
        self.base_frames.append(
            self._pose_as_position_quaternion(self._bodies[ROBOT_BASE_KEY])
            if ROBOT_BASE_KEY in self._bodies
            else None
        )
        self.object_frames.append(
            {
                name: self._pose_as_position_quaternion(body)
                for name, body in self._bodies.items()
                if name != ROBOT_BASE_KEY
            }
        )
        if len(self.frames) % FRAME_LOG_INTERVAL == 0:
            log("... %d frames" % len(self.frames))

    # %% action metadata hook
    # Plans compile all actions into merged motion statecharts, so there is no
    # per-action call boundary at execution time. ``ActionNode.parse`` does fire
    # once per action (in plan order) — the action class, its arm and its target
    # object are recorded there, and the segment *timing* is derived afterwards
    # from the recorded data (object attach/detach + first base motion).
    def _target_of(self, designator: Any) -> Optional[str]:
        """
        The recorded object a designator refers to, matched by mesh basename.
        """
        basenames = {os.path.basename(path) for path in self.mesh_sources}
        for value in vars(designator).values():
            if not isinstance(value, NamesAWorldEntity):
                continue
            basename = str(value.name).split("/")[-1]
            if basename in basenames:
                return basename
        return None

    @staticmethod
    def _arm_of(designator: Any) -> Optional[str]:
        """
        The arm a designator names, whether it calls the field ``arm`` or ``arms``.
        """
        fields = vars(designator)
        arm = fields.get("arm") or fields.get("arms")
        return str(arm) if arm is not None else None

    def install_segment_hook(self) -> None:
        """
        Wrap ActionNode.parse to record each action's class, arm and target as
        it is parsed (in plan order).
        """
        from coraplex.plans.plan_node import ActionNode

        recorder = self
        original_parse = ActionNode.parse

        def parse(node: ActionNode, *args: Any, **kwargs: Any) -> Executable:
            """
            Record this action's designator before letting it parse normally.
            """
            designator = node.designator
            recorder.actions.append(
                {
                    "action": type(designator).__name__,
                    "arm": recorder._arm_of(designator),
                    "target": recorder._target_of(designator),
                }
            )
            recorder.plan_nodes.append(node)
            log(
                "action parsed:",
                recorder.actions[-1]["action"],
                "->",
                recorder.actions[-1]["target"] or "-",
            )
            return original_parse(node, *args, **kwargs)

        ActionNode.parse = parse

    # %% the executed plan tree, serialized from the real PlanNode graph
    def serialize_plans(
        self, max_nodes: int = MAX_SERIALIZED_PLAN_NODES
    ) -> List[Dict[str, Any]]:
        """
        The executed plan trees, deduplicated by root, as nested dicts.

        :param max_nodes: Upper bound on the total node count across all trees; the
            recording stops descending once it is reached.
        """
        roots: List[Any] = []
        seen_roots = set()
        for node in self.plan_nodes:
            root = node
            while isinstance(root, HasAParent) and root.parent is not None:
                root = root.parent
            if id(root) not in seen_roots:
                seen_roots.add(id(root))
                roots.append(root)
        serialized_count = itertools.count()

        def serialize(node: Any) -> Optional[Dict[str, Any]]:
            """
            One plan node and its children as a dict, or None past ``max_nodes``.
            """
            if next(serialized_count) >= max_nodes:
                return None
            designator = (
                node.designator if isinstance(node, DescribesAnAction) else None
            )
            status = node.status if isinstance(node, ReportsAStatus) else None
            entry = {
                "kind": type(node).__name__,
                "label": (
                    type(designator).__name__
                    if designator is not None
                    else type(node).__name__
                ),
                "status": status.name if status is not None else "",
            }
            if designator is not None:
                target = self._target_of(designator)
                if target:
                    entry["target"] = target
                arm = self._arm_of(designator)
                if arm is not None:
                    entry["arm"] = arm
            children = node.children if isinstance(node, HasChildren) else ()
            entry["children"] = [
                child
                for child in (serialize(child) for child in children or ())
                if child
            ]
            return entry

        return [tree for tree in (serialize(root) for root in roots) if tree]


# %% post-processing the recording
#: how far a pose must travel to count as moved at all, in metres
MOVEMENT_TOLERANCE = 0.02

#: how far an object must travel over the whole run to count as transported, in metres
TRANSPORT_TOLERANCE = 0.03

#: how far the robot base must travel to count as having driven off, in metres
BASE_MOTION_TOLERANCE = 0.05


def moved(
    first: Sequence[float],
    second: Sequence[float],
    eps: float = MOVEMENT_TOLERANCE,
) -> bool:
    """
    Whether two poses are more than ``eps`` apart (planar distance plus height).

    :param eps: Tolerance in metres, so sensor jitter does not read as movement.
    """
    return (
        math.hypot(first[0] - second[0], first[1] - second[1])
        + abs(first[2] - second[2])
        > eps
    )


def object_windows(rec: Recorder) -> List[Dict[str, Any]]:
    """
    The attach..detach frame window of every object that travelled overall.

    An object whose first and last pose differ was transported; the window spans from
    the first frame that differs from where it started to just past the last frame
    that differs from where it ended up.
    """
    object_frames = rec.object_frames
    frame_count = len(object_frames)
    windows = []
    for name in object_frames[0]:
        spawn = object_frames[0].get(name)
        final = object_frames[frame_count - 1].get(name)
        if not spawn or not final or not moved(spawn, final, TRANSPORT_TOLERANCE):
            continue
        attach = next(
            (
                index
                for index in range(frame_count)
                if name in object_frames[index]
                and moved(object_frames[index][name], spawn)
            ),
            frame_count - 1,
        )
        detach = (
            next(
                (
                    index
                    for index in range(frame_count - 1, -1, -1)
                    if name in object_frames[index]
                    and moved(object_frames[index][name], final)
                ),
                0,
            )
            + 1
        )
        if attach < detach:
            windows.append(
                {
                    "object": name,
                    "attach": attach,
                    "detach": detach,
                    "place": final[:3],
                }
            )
    windows.sort(key=lambda window: window["attach"])
    return windows


def first_base_motion(rec: Recorder, before: int) -> int:
    """
    The first frame before ``before`` at which the robot base left its spawn.

    :return: That frame's index, or ``before`` if the base never moved.
    """
    spawn = rec.base_frames[0]
    for index in range(min(before, len(rec.base_frames))):
        pose = rec.base_frames[index]
        if not pose or not spawn:
            continue
        if math.hypot(pose[0] - spawn[0], pose[1] - spawn[1]) > BASE_MOTION_TOLERANCE:
            return index
    return before


def derive_segments(rec: Recorder) -> List[Dict[str, Any]]:
    """Segments = data-driven windows, labelled from the parsed action list."""
    n = len(rec.frames)
    wins = object_windows(rec)
    manip_acts = [a for a in rec.actions if a.get("target")]
    lead_acts = []
    for a in rec.actions:
        if a.get("target"):
            break
        lead_acts.append(a)

    segments = []
    prev = 0
    if wins:
        lead_end = first_base_motion(rec, wins[0]["attach"])
        if lead_end > 10:
            label = (
                lead_acts[0]["action"].replace("Action", "").lower()
                if len(lead_acts) == 1
                else "prepare"
            )
            segments.append(
                {
                    "step": label,
                    "action": ",".join(x["action"] for x in lead_acts) or None,
                    "arm": None,
                    "start": 0,
                    "end": lead_end,
                }
            )
            prev = lead_end
    remaining = list(manip_acts)
    for k, w in enumerate(wins):
        act = next((x for x in remaining if x["target"] == w["object"]), None)
        if act:
            remaining.remove(act)
        oid = os.path.splitext(w["object"])[0]
        verb = act["action"].replace("Action", "").lower() if act else "move"
        nxt = wins[k + 1]["attach"] if k + 1 < len(wins) else n - 1
        end = (
            min(nxt, w["detach"] + max(10, (nxt - w["detach"]) // 2))
            if k + 1 < len(wins)
            else n - 1
        )
        segments.append(
            {
                "step": "%s_%s" % (verb, oid),
                "action": act["action"] if act else None,
                "arm": act["arm"] if act else None,
                "start": prev,
                "end": end,
                "picks": oid,
                "attach": w["attach"],
                "detach": w["detach"],
                "place": w["place"],
            }
        )
        prev = end
    if not segments:
        label = (
            rec.actions[0]["action"].replace("Action", "").lower()
            if len(rec.actions) == 1
            else "plan"
        )
        segments.append(
            {"step": label, "action": None, "arm": None, "start": 0, "end": n - 1}
        )
    return segments


def link_set(part: Any) -> List[str]:
    """
    A robot part's link names, stripped of their model-name prefix.
    """
    if not isinstance(part, HasBodies):
        return []
    link_names = []
    for body in part.bodies or []:
        name = str(body.name) if isinstance(body, NamesAWorldEntity) else str(body)
        link_names.append(name.split("/", 1)[1] if "/" in name else name)
    return link_names


def build_scene(rec: Recorder, name: str, out_dir: str, step: int) -> Dict[str, Any]:
    """
    Downsample the recording to every step-th frame (always keeping the last)
    and assemble scene.json + trajectory.json from it.
    """
    frame_count = len(rec.frames)
    kept_indices = list(range(0, frame_count, step))
    if kept_indices and kept_indices[-1] != frame_count - 1:
        kept_indices.append(frame_count - 1)
    downsampled_index = {raw_index: kept for kept, raw_index in enumerate(kept_indices)}

    def nearest(raw_index: int) -> int:
        """
        The downsampled index closest to a raw frame index.
        """
        return downsampled_index.get(
            raw_index,
            downsampled_index[
                min(downsampled_index, key=lambda kept: abs(kept - raw_index))
            ],
        )

    n = frame_count
    idx = kept_indices
    frames = [rec.frames[index] for index in kept_indices]
    base = [rec.base_frames[index] for index in kept_indices]
    objs = [rec.object_frames[index] for index in kept_indices]

    raw_frames_per_second = (
        1.0 / rec.control_dt if rec.control_dt else FALLBACK_FRAMES_PER_SECOND
    )
    fps = max(MINIMUM_FRAMES_PER_SECOND, round(raw_frames_per_second / step))

    # %% robot description
    robot = rec.robot
    root_name = str(robot.root.name)
    prefix = root_name.split("/", 1)[0] if "/" in root_name else ""
    base_body = root_name.split("/", 1)[1] if "/" in root_name else root_name
    parts = {}
    for arm in robot.get_arms():
        arm_links = link_set(arm)
        end_effector = arm.end_effector if isinstance(arm, HasAnEndEffector) else None
        end_effector_links = link_set(end_effector) if end_effector is not None else []
        parts[type(arm).__name__] = sorted(set(arm_links) - set(end_effector_links))
        if end_effector is not None:
            parts[type(end_effector).__name__] = sorted(set(end_effector_links))

    # %% segments: data-derived windows, labelled from the parsed actions
    segments = []
    for raw_segment in derive_segments(rec):
        segment = dict(raw_segment)
        segment["start"] = nearest(raw_segment["start"])
        segment["end"] = nearest(raw_segment["end"])
        if "attach" in segment:
            segment["attach"] = nearest(raw_segment["attach"])
            segment["detach"] = nearest(raw_segment["detach"])
        segments.append(segment)
    # a scene with two transports of the same object would otherwise name both steps
    # identically, and the viewer keys its playback captions on the step name
    step_counts: Dict[str, int] = {}
    for segment in segments:
        step_counts[segment["step"]] = step_counts.get(segment["step"], 0) + 1
        if step_counts[segment["step"]] > 1:
            segment["step"] = "%s_%d" % (
                segment["step"],
                step_counts[segment["step"]],
            )

    # %% objects
    objects = []
    palette = ObjectPalette()
    for i, source in enumerate(rec.mesh_sources):
        mesh = os.path.basename(source)
        if mesh not in rec.object_frames[0]:
            continue
        destination = os.path.join(out_dir, "meshes", "objects", mesh)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        entry = {
            "id": os.path.splitext(mesh)[0],
            "key": mesh,
            "mesh": "meshes/objects/" + mesh,
            "spawn": rec.object_frames[0][mesh],
            "color": palette.color_for(i),
        }
        # recorded from the world, so the knowledge base does not have to guess it;
        # omitted when the object's shapes report no measurable size
        body = (rec._bodies or {}).get(mesh)
        extent = BodyExtent.of(body) if body is not None else None
        if extent is not None:
            entry["height"] = round(extent.z, POSE_PRECISION)
        objects.append(entry)

    # %% place target + drag bounds
    places = [segment["place"] for segment in segments if segment.get("place")]
    place_target = None
    if places:
        center_x = sum(place[0] for place in places) / len(places)
        center_y = sum(place[1] for place in places) / len(places)
        lowest_z = min(place[2] for place in places)
        place_target = {
            "pos": [round(center_x, 3), round(center_y, 3)],
            "z": round(lowest_z - PLACE_TARGET_DROP, 3),
            "bounds": {
                "minX": round(center_x - PLACE_BOUNDS_MARGIN, 2),
                "maxX": round(center_x + PLACE_BOUNDS_MARGIN, 2),
                "minY": round(center_y - PLACE_BOUNDS_MARGIN, 2),
                "maxY": round(center_y + PLACE_BOUNDS_FRONT_MARGIN, 2),
            },
        }
    drag_bounds = None
    if objects:
        spawn_x = [entry["spawn"][0] for entry in objects]
        spawn_y = [entry["spawn"][1] for entry in objects]
        drag_bounds = {
            "minX": round(min(spawn_x) - DRAG_BOUNDS_MARGIN_X, 2),
            "maxX": round(max(spawn_x) + DRAG_BOUNDS_MARGIN_X, 2),
            "minY": round(min(spawn_y) - DRAG_BOUNDS_MARGIN_Y, 2),
            "maxY": round(max(spawn_y) + DRAG_BOUNDS_MARGIN_Y, 2),
        }

    # %% bundle the URDF models
    world_body_names = [
        str(body.name) if isinstance(body, NamesAWorldEntity) else ""
        for body in rec.world.bodies
    ]
    models = []
    missing: List[str] = []
    for source in rec.urdf_sources:
        base_name = os.path.splitext(os.path.basename(source))[0]
        report = bundle_urdf(source, base_name, out_dir, hints=rec.resolutions)
        missing += report["missing"]
        # find this model's prefix in the composed world via one of its links
        model_prefix = ""
        for link in report["links"][:PREFIX_PROBE_LINKS]:
            prefixed = next(
                (
                    body_name
                    for body_name in world_body_names
                    if body_name.endswith("/" + link)
                ),
                None,
            )
            if prefixed:
                model_prefix = prefixed.split("/", 1)[0]
                break
        is_robot = base_body in report["links"]
        models.append(
            {
                "name": base_name,
                "urdf": "%s.urdf" % base_name,
                "prefix": model_prefix,
                "robot": is_robot,
                "links": len(report["links"]),
                "movableJoints": report["movable_joints"],
            }
        )
        log(
            "bundled %-28s prefix=%-12s robot=%s meshes=%d missing=%d"
            % (
                base_name,
                model_prefix or "-",
                is_robot,
                report["meshes_copied"],
                len(report["missing"]),
            )
        )

    scene = {
        "name": name,
        "fps": fps,
        "trajectory": "trajectory.json",
        "models": models,
        "robot": {
            "name": type(robot).__name__.lower(),
            "prefix": prefix,
            "baseBody": base_body,
            "parts": parts,
        },
        "objects": objects,
        "segments": segments,
        "actions": rec.actions,
        "planTrees": rec.serialize_plans(),
        "placeTarget": place_target,
        "dragBounds": drag_bounds,
        "missingAssets": sorted(set(missing)),
    }
    _write_json(Path(out_dir) / "scene.json", scene, indent=1)
    _write_json(
        Path(out_dir) / "trajectory.json",
        {"fps": fps, "frames": frames, "base": base, "objects": objs},
    )
    return scene


def _update_scene_index(path: Path, name: str) -> None:
    """
    Register a freshly written scene in the index the viewer reads.

    A missing or unreadable index is rebuilt from scratch; an index that exists but
    lacks the keys is filled in rather than crashing on them.
    """
    index: Dict[str, Any] = {}
    if path.is_file():
        index = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(index, dict):
        index = {}
    index.setdefault("scenes", [])
    index.setdefault("default", name)
    if name not in index["scenes"]:
        index["scenes"].append(name)
    _write_json(path, index, indent=1)


def _write_json(path: Path, payload: Any, indent: Optional[int] = None) -> None:
    """
    Write a bundle file, replacing it only once it is complete.

    A bundle is the artifact of a long recording, so a failure part-way through a
    write must not leave a truncated file behind.
    """
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(payload, indent=indent), encoding="utf-8")
    temporary.replace(path)


# %% the cram-viz-onboard entry point
def main() -> None:
    """
    ``cram-viz-onboard`` — record one demo run into a scene bundle.
    """
    # force: the demo's own imports configure the root logger before we get here
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("demo", help="path to the coraplex demo .py file")
    ap.add_argument("--name", required=True, help="scene name (output folder)")
    ap.add_argument(
        "--out",
        default=str(paths.scenes_dir()),
        help="scenes directory (default: CRAM_VIZ_SCENES or ~/.cram_viz/scenes)",
    )
    ap.add_argument("--step", type=int, default=0, help="downsample step (0 = auto)")
    args = ap.parse_args()

    try:
        import coraplex  # noqa: F401
    except ModuleNotFoundError:
        sys.exit(
            "The CRAM stack is not importable — run under the action-cram venv:\n"
            "  the workspace venv (uv sync), then: cram-viz-onboard ..."
        )

    rec = Recorder()
    rec.install_asset_hooks()
    rec.install_tick_hook()
    rec.install_segment_hook()

    demo = os.path.abspath(args.demo)
    log("running demo:", demo)
    sys.path.insert(0, os.path.dirname(demo))
    # make repo-level helper packages (e.g. test.conftest) importable — the
    # demos rely on pytest's rootdir behaviour for that
    candidate = os.path.dirname(demo)
    while candidate != os.path.dirname(candidate):
        if os.path.isdir(os.path.join(candidate, "coraplex")) and os.path.isdir(
            os.path.join(candidate, "test")
        ):
            sys.path.insert(0, candidate)
            log("repo root on sys.path:", candidate)
            break
        candidate = os.path.dirname(candidate)
    runpy.run_path(demo, run_name="__main__")
    log(
        "demo finished: %d raw frames, %d actions" % (len(rec.frames), len(rec.actions))
    )

    if not rec.frames:
        sys.exit("No frames captured — did the demo perform a plan?")
    if rec.robot is None:
        sys.exit("No AbstractRobot semantic annotation found in the world.")

    step = args.step or max(1, len(rec.frames) // TARGET_BUNDLE_FRAMES)
    out_dir = os.path.join(args.out, args.name)
    os.makedirs(out_dir, exist_ok=True)
    scene = build_scene(rec, args.name, out_dir, step)
    _update_scene_index(Path(args.out) / "index.json", args.name)

    log("scene '%s' written to %s" % (args.name, out_dir))
    log(
        "  models:  %s"
        % ", ".join(
            "%s%s" % (model["name"], " (robot)" if model["robot"] else "")
            for model in scene["models"]
        )
    )
    log("  objects: %s" % ", ".join(entry["id"] for entry in scene["objects"]))
    log("  segments: %s" % " → ".join(entry["step"] for entry in scene["segments"]))
    if scene["missingAssets"]:
        log("  warning — %d missing assets:" % len(scene["missingAssets"]))
        for asset in scene["missingAssets"][:MISSING_ASSETS_LOGGED]:
            log("   ", asset)
    sys.stdout.flush()
    os._exit(0)  # don't hang on non-daemon ROS/viz threads the demo started


if __name__ == "__main__":
    main()
