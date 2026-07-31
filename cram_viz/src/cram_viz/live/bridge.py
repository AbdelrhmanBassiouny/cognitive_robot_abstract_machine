"""
The live-viz bridge state: what a running demo publishes to the viewer.

This module is free of HTTP and of hook installation — it holds the :class:`Bridge`
singleton whose snapshot methods run on the *simulation* thread (see
:mod:`cram_viz.live.hooks` for why that matters) and whose ``get_*`` accessors hand
finished, plain-dict snapshots to the HTTP layer.

Node status is where the plan and the statechart differ: coraplex only performs the plan
root (``Plan.perform`` → ``root.perform``); ``ActionNode.notify`` expands its children
but never performs them, so every inner ``PlanNode`` keeps status ``CREATED`` for the
whole run. The real per-step progress lives in the giskardpy motion statechart's life
cycle. ``GiskardExecutable.motion_mappings`` (a ``{MotionNode: Task}`` dict) is the
bridge between the two — the life cycle of each motion node's task is read and
propagated up the plan tree; those statuses are flagged ``derived``.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.parse
import math
from dataclasses import dataclass, field
from enum import Enum
from http.server import ThreadingHTTPServer
from pathlib import Path

from typing_extensions import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
    Set,
    Tuple,
    TYPE_CHECKING,
)

from semantic_digital_twin.robots.robot_parts import AbstractRobot
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from cram_viz.body_geometry import BodyExtent
from semantic_digital_twin.world_description.connections import (
    ActiveConnection1DOF,
    Connection6DoF,
)

from cram_viz.palette import ObjectPalette

if TYPE_CHECKING:
    from coraplex.plans.executables import GiskardExecutable
    from coraplex.plans.plan import Plan
    from giskardpy.motion_statechart.motion_statechart import MotionStatechart
    from semantic_digital_twin.world import World
    from semantic_digital_twin.world_description.world_entity import Body

logger = logging.getLogger(__name__)


class TaskStatusName(str, Enum):
    """
    The status vocabulary the viewer styles plan and statechart nodes with.

    Mirrors coraplex's ``TaskStatus`` names. A plain ``str`` enum, because the values
    travel to the frontend as JSON and are compared against the names coraplex itself
    reports.
    """

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    PAUSE = "PAUSE"


class LiveHook(Enum):
    """
    The CRAM classes the live bridge patches to observe a running demo.
    """

    TICK = "tick"
    """
    ``Executor.tick`` — binds the world and snapshots it every simulation step.
    """

    PLAN = "plan"
    """
    ``Plan.perform`` and ``GiskardExecutable.execute`` — follow the plan tree.
    """

    MESH = "mesh"
    """
    ``MeshParser.parse`` — remember which file each object's geometry came from.
    """


#: giskardpy ``LifeCycleValues`` ordinal → its name, for the statechart view
LIFE_CYCLE_NAME = {0: "NOT_STARTED", 1: "RUNNING", 2: "PAUSED", 3: "DONE", 4: "FAILED"}

#: giskardpy ``LifeCycleValues`` ordinal → coraplex ``TaskStatus`` vocabulary,
#: so the viewer styles plan nodes and statechart nodes with one status palette
LIFE_CYCLE_TO_STATUS = {
    0: "CREATED",
    1: "RUNNING",
    2: "PAUSE",
    3: "SUCCEEDED",
    4: "FAILED",
}

#: for bottom-up aggregation in the plan tree: the higher rank wins
STATUS_RANK = {
    "CREATED": 0,
    "SUCCEEDED": 1,
    "PAUSE": 2,
    "RUNNING": 3,
    "INTERRUPTED": 4,
    "FAILED": 5,
}

#: how long a world binding stays fresh before the bridge re-discovers bodies
REBIND_INTERVAL_SECONDS = 3.0

#: key under which the robot's root body is published, instead of as a loose object
ROBOT_BASE_KEY = "__base__"

#: a body whose name ends in one of these is a loose object, not part of a model
MESH_SUFFIXES = (".stl", ".obj", ".dae")

#: fallback size for an object whose shapes carry no scale, in metres
DEFAULT_OBJECT_SIZE = (0.06, 0.06, 0.12)

#: decimal places poses and joint positions are rounded to before publishing
POSE_PRECISION = 5

#: decimal places object sizes are rounded to before publishing
SIZE_PRECISION = 4


def _pose_as_position_quaternion(body: Body) -> List[float]:
    """
    Return a body's world pose as ``[x, y, z, qx, qy, qz, qw]``.
    """
    pose = body.global_pose
    translation = pose.to_position().to_np().flatten()
    quaternion = pose.to_quaternion().to_np().flatten()
    return [round(float(value), 5) for value in (*translation[:3], *quaternion[:4])]


@runtime_checkable
class DescribesAnAction(Protocol):
    """
    A plan node carrying the designator that describes what it does.

    Structural, because only some coraplex node types have a designator at all.
    """

    designator: Any


@runtime_checkable
class NamesAWorldEntity(Protocol):
    """
    Anything carrying a world-entity name, such as a body a designator refers to.
    """

    name: Any


class MalformedMoveRequest(Exception):
    """
    Raised when the viewer's move payload cannot be read as a pose.
    """


@dataclass(frozen=True)
class MoveRequest:
    """
    A drag the viewer performed on one object, to be written into the world.
    """

    object_key: str
    """
    Mesh key of the dragged object, as published in the geometry catalog.
    """

    position: List[float]
    """
    Target position ``[x, y, z]`` in world coordinates.
    """

    quaternion: Optional[List[float]] = None
    """
    Target orientation ``[qx, qy, qz, qw]``, or None to keep the current one.
    """

    is_final: bool = False
    """
    Whether this is the drag's last update, as opposed to an intermediate one.
    """

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> MoveRequest:
        """
        Build a request from a decoded ``POST /move`` body.

        :raises MalformedMoveRequest: If the object key or the position is unusable.
            Validating here keeps bad input from raising inside the simulation tick,
            where the only recovery is to drop the whole snapshot.
        """
        object_key = payload.get("object")
        if not isinstance(object_key, str) or not object_key:
            raise MalformedMoveRequest("'object' must be a non-empty string")
        position = cls._coordinates(payload.get("pos"), "pos", 3)
        quaternion = (
            cls._coordinates(payload.get("quat"), "quat", 4)
            if payload.get("quat")
            else None
        )
        return cls(
            object_key=object_key,
            position=position,
            quaternion=quaternion,
            is_final=bool(payload.get("final")),
        )

    @staticmethod
    def _coordinates(value: Any, name: str, length: int) -> List[float]:
        """
        Read a fixed-length list of finite coordinates out of a payload field.
        """
        if not isinstance(value, (list, tuple)) or len(value) != length:
            raise MalformedMoveRequest(
                "'%s' must be a list of %d numbers" % (name, length)
            )
        coordinates = []
        for entry in value:
            if isinstance(entry, bool) or not isinstance(entry, (int, float)):
                raise MalformedMoveRequest("'%s' must contain only numbers" % name)
            if not math.isfinite(entry):
                raise MalformedMoveRequest("'%s' must be finite" % name)
            coordinates.append(float(entry))
        return coordinates


@dataclass
class MotionNodeProgress:
    """
    What the bridge knows about one plan node's execution.

    Holds the node itself so the identity key derived from it stays unique for as long
    as the entry lives.
    """

    node: Any
    """
    The plan node this progress belongs to.
    """

    task: Optional[Any] = None
    """
    The giskard task while the node's motion group runs, else None.
    """

    status: Optional[TaskStatusName] = None
    """
    The status pinned when the node's motion group finished, else None.
    """


@dataclass
class Bridge:
    """
    Shared state between the running demo and the viewer.

    All world reads and writes happen on the simulation thread (the tick hook); the HTTP
    handlers only ever read the finished snapshot dicts under :attr:`_lock`.
    """

    world: Optional[World] = None
    """
    The executing world, captured by the tick hook on its first call.
    """

    robot: Optional[AbstractRobot] = None
    """
    The robot annotation of :attr:`world`, re-discovered on every bind.
    """

    seq: int = 0
    """
    Monotonic snapshot counter so the viewer can skip unchanged states.
    """

    state: Dict[str, Any] = field(
        default_factory=lambda: {"seq": 0, "frames": {}, "base": None, "objects": {}}
    )
    """
    The newest world snapshot in the trajectory-frame format.
    """

    object_meta: List[Dict[str, Any]] = field(default_factory=list)
    """
    Geometry catalog for the viewer: one entry per loose object.
    """

    plan_state: Dict[str, Any] = field(default_factory=lambda: {"sig": "", "nodes": []})
    """
    The newest plan-tree snapshot (see :meth:`snapshot_plan`).
    """

    chart_state: Dict[str, Any] = field(
        default_factory=lambda: {"sig": "", "title": "", "nodes": [], "edges": []}
    )
    """
    The newest motion-statechart snapshot (see :meth:`observe_chart`).
    """

    _connections: List[Any] = field(default_factory=list)
    """
    Actuated world connections whose positions are published as frames.
    """

    _bodies: Dict[str, Body] = field(default_factory=dict)
    """
    Published bodies by mesh key; :data:`ROBOT_BASE_KEY` is the robot root.
    """

    _last_bind: float = 0.0
    """
    Timestamp of the last world discovery (see ``REBIND_INTERVAL_SECONDS``).
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards every snapshot dict that the HTTP layer reads.
    """

    _moves: List[Dict[str, Any]] = field(default_factory=list)
    """
    Object moves queued by the viewer, applied on the simulation thread.
    """

    _moves_lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards :attr:`_moves` (written by HTTP threads).
    """

    _mesh_files: Dict[str, str] = field(default_factory=dict)
    """
    Mesh basename (lowercase) → absolute path, filled by the mesh hook.
    """

    _mesh_serve: Dict[str, str] = field(default_factory=dict)
    """
    Object key → absolute mesh path served via the ``/mesh`` endpoint.
    """

    _plan: Optional[Plan] = None
    """
    The coraplex plan captured by the ``Plan.perform`` hook.
    """

    _chart: Optional[MotionStatechart] = None
    """
    The motion statechart the executor is currently ticking.
    """

    _chart_structure: Optional[Dict[str, Any]] = None
    """
    Serialized structure of :attr:`_chart`, rebuilt when it changes.
    """

    _chart_title: str = ""
    """
    Name of the action whose motion group is executing.
    """

    _motion_nodes: Dict[int, MotionNodeProgress] = field(default_factory=dict)
    """
    Execution progress per plan node, keyed by :meth:`Bridge._node_key`.

    Reset whenever a new plan starts performing, which bounds it to one plan's nodes.
    """

    _ticks: int = 0
    """
    Tick counter used to throttle the plan snapshot.
    """

    plan_snapshot_tick_interval: int = 5
    """
    How many simulation ticks pass between plan-tree snapshots.

    Walking the plan tree is the expensive part of a tick, and the tree changes far
    more slowly than the world pose does.
    """

    _last_node_states: Optional[Tuple[List[int], List[float]]] = None
    """
    Life-cycle and observation vectors of the last published chart snapshot.
    """

    _installed_hooks: Set[LiveHook] = field(default_factory=set)
    """
    Hooks already patched into the CRAM classes (see :meth:`claim_hook`).
    """

    live_server: Optional[ThreadingHTTPServer] = None
    """
    The bridge's HTTP server once it is listening, so a second start reuses it.
    """

    # %% one-time installation
    def claim_hook(self, hook: LiveHook) -> bool:
        """
        Claim a hook for installation, reporting whether the caller should install it.

        Patching the same method twice wraps the original a second time, so every
        snapshot would run once per wrapper.

        :return: True on the first claim, False once the hook is installed.
        """
        if hook in self._installed_hooks:
            return False
        self._installed_hooks.add(hook)
        return True

    # %% what the hooks drive
    def attach(self, world: World) -> None:
        """
        Bind to the world a demo is executing and publish its geometry catalog.
        """
        self.world = world
        self.bind()
        logger.info(
            "attached to world (robot=%s, %d joints)",
            type(self.robot).__name__ if self.robot else "?",
            len(self._connections),
        )

    def observe_tick(self, chart: Optional[MotionStatechart]) -> None:
        """
        Publish everything one simulation tick makes available.

        Applies queued viewer moves first, because the tick hook runs on the only
        thread allowed to write to the world.
        """
        self.apply_moves()
        self.snapshot()
        self.observe_chart(chart)
        self._ticks += 1
        if self._ticks % self.plan_snapshot_tick_interval == 0:
            self.snapshot_plan()

    def begin_plan(self, plan: Plan) -> None:
        """
        Record the plan that started performing and publish its tree.

        Drops the previous plan's per-node progress, so a long-running process does not
        accumulate entries for nodes that no longer exist.
        """
        self._plan = plan
        self._motion_nodes.clear()
        self.snapshot_plan()

    def remember_mesh_file(self, file_path: str) -> None:
        """
        Remember which file an object's geometry was parsed from.

        The viewer is served the mesh from here, keyed by the file's basename, which
        is also how the world names the resulting body.
        """
        self._mesh_files[Path(file_path).name.lower()] = file_path

    def publish_bodies(self, bodies: Dict[str, Body]) -> None:
        """
        Replace the published bodies and rebuild the viewer's geometry catalog.
        """
        self._bodies = bodies
        self._build_object_meta(bodies)

    # %% what the HTTP layer reads
    def object_catalog(self) -> List[Dict[str, Any]]:
        """
        The geometry catalog the viewer spawns live objects from.
        """
        with self._lock:
            return list(self.object_meta)

    def object_keys(self) -> List[str]:
        """
        Mesh keys of the published loose objects, excluding the robot root.
        """
        with self._lock:
            return [key for key in self._bodies if key != ROBOT_BASE_KEY]

    def mesh_path(self, key: str) -> Optional[str]:
        """
        Absolute path of an object's mesh file, or None if it is not served.
        """
        with self._lock:
            return self._mesh_serve.get(key)

    def status(self) -> Dict[str, Any]:
        """
        What the viewer polls to decide whether a live demo is reachable.
        """
        with self._lock:
            return {
                "running": self.world is not None,
                "robot": type(self.robot).__name__ if self.robot else None,
                "objects": [key for key in self._bodies if key != ROBOT_BASE_KEY],
                "movable": True,
                "plan": bool(self.plan_state.get("nodes")),
                "chart": bool(self.chart_state.get("nodes")),
                "seq": self.seq,
            }

    # %% viewer -> world
    def queue_move(self, request: MoveRequest) -> None:
        """
        Queue an object move from the viewer (called on an HTTP thread).
        """
        with self._moves_lock:
            self._moves.append(request)

    def apply_moves(self) -> None:
        """
        Apply queued object moves to the world.

        Called from the tick hook — the simulation thread is the only place that may
        write to the world.
        """
        with self._moves_lock:
            moves, self._moves = self._moves, []
        if not moves or self.world is None:
            return
        for move in moves:
            body = self._bodies.get(move.object_key)
            if body is None:
                logger.debug("no published body for %s — move skipped", move.object_key)
                continue
            self._apply_move(move, body)

    def _apply_move(self, move: MoveRequest, body: Body) -> None:
        """
        Write one viewer move into the world.

        Only free-floating (:class:`Connection6DoF`) objects are draggable.
        Objects rigidly fixed to furniture — e.g. a spoon on a drawer that
        must ride along when the drawer opens — keep their ``FixedConnection``
        and are left untouched (a fixed connection has no settable origin).

        .. note:: The object is not re-parented. That is a structural change of the
           kinematic tree (``modify_world`` + forward kinematics recompile), and
           running it inside the tick hook while a giskard goal is live hangs the
           executor. The plain pose write already makes ``body.global_pose`` correct,
           which is what the plan's navigate/pick reachability reads.
        """
        connection = body.parent_connection
        if not isinstance(connection, Connection6DoF):
            logger.info(
                "%s is fixed (%s) — not draggable, skipping",
                move.object_key,
                type(connection).__name__,
            )
            return
        position = move.position
        quaternion = move.quaternion
        if quaternion is None:
            quaternion = _pose_as_position_quaternion(body)[3:7]
        world_T_object = HomogeneousTransformationMatrix.from_xyz_quaternion(
            position[0],
            position[1],
            position[2],
            quaternion[0],
            quaternion[1],
            quaternion[2],
            quaternion[3],
            reference_frame=self.world.root,
        )
        # ``origin`` is parent-relative; express the target in the parent
        # frame (a no-op while the parent is the world root)
        parent_T_object = connection.parent.global_pose.inverse() @ world_T_object
        connection.origin = parent_T_object
        logger.info(
            "moved %s -> world (%.3f, %.3f, %.3f) [final=%s]",
            move.object_key,
            position[0],
            position[1],
            position[2],
            move.is_final,
        )

    # %% world discovery
    def bind(self) -> None:
        """
        Discover the robot, joints and loose objects of the current world.

        Re-run periodically because demos modify their world (objects get spawned and
        removed mid-run).
        """
        world = self.world
        if world is None:
            return
        self._last_bind = time.time()
        robots = world.get_semantic_annotations_by_type(AbstractRobot)
        self.robot = robots[0] if robots else None
        self._connections = self._actuated_connections(world)
        bodies: Dict[str, Body] = {}
        if self.robot is not None:
            bodies[ROBOT_BASE_KEY] = self.robot.root
        try:
            # loose objects by convention: bodies named like mesh files
            for body in world.bodies:
                basename = str(body.name).split("/")[-1]
                if basename.lower().endswith(MESH_SUFFIXES):
                    bodies[basename] = body
        except Exception as error:
            # boundary guard: the world is mid-modification (a body is being spawned
            # or removed) and iterating it is not safe. Keep the previous catalog
            # rather than publishing an empty one, which would make the viewer hide
            # every object it already shows.
            logger.debug("body scan skipped this bind: %s", error)
            for key, body in self._bodies.items():
                bodies.setdefault(key, body)
        self.publish_bodies(bodies)

    @staticmethod
    def _actuated_connections(world: World) -> List[ActiveConnection1DOF]:
        """
        All 1-DOF connections — the joints published as trajectory frames.
        """
        return [
            connection
            for connection in world.connections or []
            if isinstance(connection, ActiveConnection1DOF)
        ]

    def _build_object_meta(self, bodies: Dict[str, Body]) -> None:
        """
        Rebuild the geometry catalog the viewer spawns live objects from.

        Each object gets either a mesh URL (served by the bridge) or a box size, so
        objects the viewer does not know yet can appear mid-run.
        """
        catalog: List[Dict[str, Any]] = []
        serve: Dict[str, str] = {}
        palette = ObjectPalette()
        for index, (key, body) in enumerate(
            item for item in bodies.items() if item[0] != ROBOT_BASE_KEY
        ):
            color = palette.color_for(index)
            object_id = Path(key).stem
            mesh_path = self._mesh_files.get(key.lower())
            if mesh_path and Path(mesh_path).is_file():
                serve[key] = mesh_path
                catalog.append(
                    {
                        "key": key,
                        "id": object_id,
                        "kind": "mesh",
                        "mesh": "/mesh?key=" + urllib.parse.quote(key),
                        "format": Path(key).suffix.lstrip(".").lower(),
                        "color": color,
                    }
                )
            else:
                catalog.append(
                    {
                        "key": key,
                        "id": object_id,
                        "kind": "box",
                        "size": self._box_size(body) or list(DEFAULT_OBJECT_SIZE),
                        "color": color,
                    }
                )
        self._mesh_serve = serve
        with self._lock:
            self.object_meta = catalog

    @staticmethod
    def _box_size(body: Body) -> Optional[List[float]]:
        """
        Size of a body's geometry in metres, or None when no shape reports one.
        """
        extent = BodyExtent.of(body)
        return extent.rounded(SIZE_PRECISION) if extent else None

    # %% world snapshot
    def snapshot(self) -> None:
        """
        Publish the world's joints, base pose and object poses.

        Runs on the simulation thread; rebinds the world periodically so mid-run spawns
        show up.
        """
        if self.world is None:
            return
        if time.time() - self._last_bind > REBIND_INTERVAL_SECONDS:
            self.bind()
        frames = {
            str(connection.name): round(float(connection.position), 5)
            for connection in self._connections
        }
        base_pose: Optional[List[float]] = None
        object_poses: Dict[str, List[float]] = {}
        for name, body in self._bodies.items():
            if name == ROBOT_BASE_KEY:
                base_pose = _pose_as_position_quaternion(body)
            else:
                object_poses[name] = _pose_as_position_quaternion(body)
        with self._lock:
            self.seq += 1
            self.state = {
                "seq": self.seq,
                "frames": frames,
                "base": base_pose,
                "objects": object_poses,
            }

    def get_state(self) -> Dict[str, Any]:
        """
        The newest world snapshot (safe to call from HTTP threads).
        """
        with self._lock:
            return dict(self.state)

    # %% plan tree
    @staticmethod
    def _node_key(node: Any) -> int:
        """
        Identity key of a plan node.

        Identity, not equality: coraplex's ``DesignatorNode`` compares by field value,
        so two structurally identical steps of one plan would otherwise share a status.
        The :class:`MotionNodeProgress` entry pins the node itself, which keeps CPython
        from handing its ``id`` to a later object.
        """
        return id(node)

    def bind_motion_group(self, executable: GiskardExecutable) -> None:
        """
        Remember which plan motion node maps to which statechart task.

        Called when a ``GiskardExecutable`` is about to run, so the plan tree can show
        live per-step progress.
        """
        for node, task in (executable.motion_mappings or {}).items():
            self._motion_nodes[self._node_key(node)] = MotionNodeProgress(
                node=node, task=task
            )
        self._chart_title = self._motion_group_title(executable)

    @staticmethod
    def _motion_group_title(executable: GiskardExecutable) -> str:
        """
        Name of the action the motion group belongs to, or ``''``.
        """
        for node in executable.motion_mappings or {}:
            action_node = node.parent_action_node
            if action_node is not None and action_node.designator is not None:
                return type(action_node.designator).__name__
        return ""

    def freeze_motion_group(
        self, executable: GiskardExecutable, status: TaskStatusName
    ) -> None:
        """
        Pin the final status of a finished motion group and republish the plan.

        Reading the tasks' life cycle afterwards is not reliable — the executor cleans
        its nodes up.
        """
        frozen_nodes = list(executable.motion_mappings or {})
        frozen_nodes += [
            condition
            for condition in (
                executable.pre_condition_node,
                executable.post_condition_node,
            )
            if condition is not None
        ]
        for node in frozen_nodes:
            self._motion_nodes[self._node_key(node)] = MotionNodeProgress(
                node=node, status=status
            )
        self.snapshot_plan()

    def _live_motion_status(self, node: Any) -> Optional[str]:
        """
        Status of one plan node from the statechart, or None.

        A live task wins over a pinned status, so a node that is running again after a
        previous attempt reports the current life cycle.
        """
        progress = self._motion_nodes.get(self._node_key(node))
        if progress is None:
            return None
        if progress.task is not None:
            return LIFE_CYCLE_TO_STATUS.get(int(progress.task.life_cycle_state))
        return progress.status

    def snapshot_plan(self) -> None:
        """
        Serialize the plan tree with per-node execution status.

        A node's own status wins while it says something; otherwise the live statechart
        status is used, else the aggregate of the children (running/failed bubble up; a
        parent whose children are only partly done reads as running, not succeeded).
        """
        plan = self._plan
        if plan is None:
            return
        try:
            root = plan.root
        except Exception:
            # the plan is mid-mutation and not a tree right now — next tick
            return
        nodes: List[Dict[str, Any]] = []
        order: List[str] = []
        self._serialize_plan_node(root, None, nodes, order)
        with self._lock:
            self.plan_state = {"sig": "|".join(order), "nodes": nodes}

    def _serialize_plan_node(
        self,
        node: Any,
        parent_id: Optional[str],
        nodes: List[Dict[str, Any]],
        order: List[str],
    ) -> str:
        """
        Serialize one plan node and its subtree; returns the node's status.
        """
        node_id = "p%d" % id(node)
        designator = node.designator if isinstance(node, DescribesAnAction) else None
        own_status = node.status.name
        entry: Dict[str, Any] = {
            "id": node_id,
            "parent": parent_id,
            "kind": type(node).__name__,
            "label": (
                type(designator).__name__
                if designator is not None
                else type(node).__name__
            ),
            "status": own_status,
            "derived": False,
        }
        self._add_designator_metadata(entry, designator)
        nodes.append(entry)
        order.append(node_id)

        child_best, children, done = "CREATED", 0, 0
        for child in node.children:
            child_status = self._serialize_plan_node(child, node_id, nodes, order)
            child_best = self._max_status(child_best, child_status)
            children += 1
            if child_status == "SUCCEEDED":
                done += 1
        if own_status == "CREATED":
            if child_best == "SUCCEEDED" and done < children:
                child_best = "RUNNING"
            derived = self._live_motion_status(node) or (
                child_best if child_best != "CREATED" else None
            )
            if derived:
                entry["status"] = derived
                entry["derived"] = True
        return entry["status"]

    def _add_designator_metadata(
        self, entry: Dict[str, Any], designator: Optional[Any]
    ) -> None:
        """
        Add arm and target-object info from a node's designator, if any.
        """
        if designator is None:
            return
        fields = vars(designator)
        arm = fields.get("arm") or fields.get("arms")
        if arm is not None:
            entry["arm"] = str(arm)
        target = self._designator_target(designator)
        if target:
            entry["target"] = target

    @staticmethod
    def _max_status(first: str, second: str) -> str:
        """
        The higher-ranked of two statuses (see ``STATUS_RANK``).
        """
        if STATUS_RANK.get(first, 0) >= STATUS_RANK.get(second, 0):
            return first
        return second

    def _designator_target(self, designator: Any) -> Optional[str]:
        """
        Name of the published object a designator refers to, if any.
        """
        known = set(self._bodies)
        for value in vars(designator).values():
            if not isinstance(value, NamesAWorldEntity):
                continue
            basename = str(value.name).split("/")[-1]
            if basename in known:
                return basename
        return None

    def get_plan(self) -> Dict[str, Any]:
        """
        The newest plan snapshot (safe to call from HTTP threads).
        """
        with self._lock:
            return dict(self.plan_state)

    # %% motion statechart
    def observe_chart(self, chart: Optional[MotionStatechart]) -> None:
        """
        Publish the executing statechart's structure and node states.

        Called from the tick hook. The structure is re-serialized only when the executor
        compiled a new chart; the life-cycle and observation vectors are cheap and
        republished whenever either of them changes.
        """
        if chart is None:
            return
        if chart is not self._chart or self._chart_structure is None:
            self._chart = chart
            self._chart_structure = self._serialize_chart_structure(chart)
            self._last_node_states = None
        structure = self._chart_structure
        if not structure:
            return
        life_cycle = [
            int(chart.life_cycle_state.data[index]) for index in structure["indices"]
        ]
        observations = [
            float(chart.observation_state.data[index]) for index in structure["indices"]
        ]
        if (life_cycle, observations) == self._last_node_states:
            return
        self._last_node_states = (life_cycle, observations)
        nodes = []
        for position, node in enumerate(structure["nodes"]):
            entry = dict(node)
            entry["life"] = LIFE_CYCLE_NAME.get(
                life_cycle[position], str(life_cycle[position])
            )
            entry["obs"] = self._observation_name(observations[position])
            nodes.append(entry)
        with self._lock:
            self.chart_state = {
                "sig": structure["sig"],
                "title": self._chart_title,
                "nodes": nodes,
                "edges": structure["edges"],
            }

    @staticmethod
    def _observation_name(observation: float) -> str:
        """
        Trinary observation value → name (0 false, 0.5 unknown, 1 true).
        """
        if observation >= 0.75:
            return "TRUE"
        if observation <= 0.25:
            return "FALSE"
        return "UNKNOWN"

    @staticmethod
    def _serialize_chart_structure(chart: MotionStatechart) -> Optional[Dict[str, Any]]:
        """
        Nodes and transition edges of a statechart, as plain dicts.
        """
        nodes: List[Dict[str, Any]] = []
        indices: List[int] = []
        for node in chart.nodes:
            parent_index = node.parent_node_index
            nodes.append(
                {
                    "id": "s%d" % node.index,
                    "name": node.name,
                    "cls": type(node).__name__,
                    "parent": (
                        ("s%d" % parent_index) if parent_index is not None else None
                    ),
                }
            )
            indices.append(node.index)
        edges = []
        for source, target, transition in chart.rx_graph.edge_index_map().values():
            edges.append(
                {
                    "from": "s%d" % chart.rx_graph.get_node_data(source).index,
                    "to": "s%d" % chart.rx_graph.get_node_data(target).index,
                    "kind": transition.kind.name,
                }
            )
        signature = "|".join(node["id"] + ":" + node["name"] for node in nodes)
        return {"nodes": nodes, "edges": edges, "indices": indices, "sig": signature}

    def get_chart(self) -> Dict[str, Any]:
        """
        The newest statechart snapshot (safe to call from HTTP threads).
        """
        with self._lock:
            return dict(self.chart_state)


#: the process-wide bridge instance shared by hooks and HTTP handlers
BRIDGE = Bridge()
