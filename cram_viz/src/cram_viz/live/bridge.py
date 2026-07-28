"""The live-viz bridge state: what a RUNNING demo publishes to the viewer.

This module is deliberately free of HTTP and of hook installation — it holds
the :class:`Bridge` singleton whose snapshot methods run on the SIMULATION
thread (see hooks.py for why that matters) and whose ``get_*`` accessors hand
finished, plain-dict snapshots to the HTTP layer.

Node STATUS is where the plan and the statechart differ, and it is worth
knowing why: coraplex only performs the plan ROOT (Plan.perform ->
root.perform); ActionNode.notify expands its children but never performs them,
so every inner PlanNode keeps status CREATED for the whole run. The real
per-step progress lives in the giskardpy motion statechart's life cycle
(NOT_STARTED/RUNNING/PAUSED/DONE/FAILED). GiskardExecutable.motion_mappings is
the bridge between the two — a dict {MotionNode: Task} — so we read the life
cycle of each MotionNode's task and propagate it up the plan tree. Those
statuses are flagged ``derived``.
"""

import os
import threading
import time
import urllib.parse

# same palette the onboarder / viewer use, so a live object keeps its colour
PALETTE = ["#f3f0ea", "#cf5b3a", "#b8bcc4", "#e7c26a", "#7fb069", "#5b8cff",
           "#c98bdb", "#ff9d6b", "#6bd0c0", "#d0c86b"]

# giskardpy LifeCycleValues -> coraplex TaskStatus vocabulary, so the viewer
# styles plan nodes and statechart nodes with one status palette
LIFE_NAME = {0: "NOT_STARTED", 1: "RUNNING", 2: "PAUSED", 3: "DONE", 4: "FAILED"}
LIFE_TO_STATUS = {0: "CREATED", 1: "RUNNING", 2: "PAUSE", 3: "SUCCEEDED", 4: "FAILED"}
# for bottom-up aggregation in the plan tree: higher wins
STATUS_RANK = {"CREATED": 0, "SUCCEEDED": 1, "PAUSE": 2, "RUNNING": 3,
               "INTERRUPTED": 4, "FAILED": 5}


class Bridge:
    def __init__(self):
        self.world = None
        self.robot = None
        self.seq = 0
        self.state = {"seq": 0, "frames": {}, "base": None, "objects": {}}
        self._conns = []
        self._bodies = {}
        self._last_bind = 0.0
        self._lock = threading.Lock()
        self._moves = []               # queued object moves from the viewer
        self._moves_lock = threading.Lock()
        self._mesh_files = {}          # 'milk.stl' (lower) -> abs path (STLParser hook)
        self._mesh_serve = {}          # object key -> abs mesh path (for /mesh)
        self.object_meta = []          # [{key,id,kind,mesh|size,color}] catalog
        # ---- plan + motion statechart introspection (read on the sim thread) --
        self.plan_state = {"sig": "", "nodes": []}
        self.chart_state = {"sig": "", "title": "", "nodes": [], "edges": []}
        self._plan = None              # coraplex Plan (captured in Plan.perform)
        self._chart = None             # MotionStatechart the executor compiled
        self._chart_struct = None      # its structure (rebuilt when it changes)
        self._chart_title = ""         # which action's motions it belongs to
        self._motion_tasks = {}        # id(MotionNode) -> giskard Task (live group)
        self._frozen = {}              # id(PlanNode) -> final status of a done group
        self._ticks = 0
        self._last_life = None

    # ---- viewer -> world: queued here (HTTP thread), applied on the sim thread
    def queue_move(self, req):
        with self._moves_lock:
            self._moves.append(req)

    def apply_moves(self):
        """Called from the tick hook (sim thread) — the only place that may
        write to the world."""
        with self._moves_lock:
            moves, self._moves = self._moves, []
        if not moves or self.world is None:
            return
        from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
        from semantic_digital_twin.world_description.connections import Connection6DoF
        for m in moves:
            body = self._bodies.get(m.get("object"))
            if body is None:
                continue
            try:
                conn = body.parent_connection
                # Only free-floating (6DoF) objects are draggable. Objects that are
                # rigidly fixed to furniture — e.g. the spoon on the drawer, which must
                # ride along when the drawer opens — keep their FixedConnection and are
                # left untouched (a FixedConnection has no settable origin).
                if not isinstance(conn, Connection6DoF):
                    print("[live_viz] %s is fixed (%s) — not draggable, skipping"
                          % (m["object"], type(conn).__name__), flush=True)
                    continue
                pos = m["pos"]
                q = m.get("quat")
                if not q:
                    cur = self._pose7(body)
                    q = [cur[3], cur[4], cur[5], cur[6]]
                world_T_obj = HomogeneousTransformationMatrix.from_xyz_quaternion(
                    pos[0], pos[1], pos[2], q[0], q[1], q[2], q[3],
                    reference_frame=self.world.root)
                # `origin` is parent-relative. After an earlier re-parent the parent may
                # no longer be world.root, so express the target in the parent frame
                # (parent == root -> this is a no-op).
                try:
                    parent_T_obj = conn.parent.global_pose.inverse() @ world_T_obj
                except Exception:
                    parent_T_obj = world_T_obj
                conn.origin = parent_T_obj

                # NOTE: we deliberately do NOT re-parent (move_branch) here. That is a
                # structural change of the kinematic tree (modify_world + FK recompile)
                # and running it inside the tick hook while a giskard goal is live hangs
                # the executor. Re-parenting must happen as its own plan step between
                # motions (see AttachNode in coraplex/plans/executables.py), not from the
                # bridge thread. The light pose write above already makes object.global_pose
                # correct, which is all the plan's navigate/pick reachability needs.
                gp = self._pose7(body)
                print("[live_viz] moved %s -> world (%.3f, %.3f, %.3f) [final=%s]"
                      % (m["object"], gp[0], gp[1], gp[2], bool(m.get("final"))),
                      flush=True)
            except Exception as ex:
                print("[live_viz] move failed for %s: %s" % (m.get("object"), ex), flush=True)

    def _find_support(self, obj_body):
        """The furniture / ground body the object currently rests on (the highest
        supporting surface below it), or None. Used to re-parent a dropped object."""
        from semantic_digital_twin.reasoning.predicates import is_supported_by
        w = self.world
        try:
            own = set(w.get_kinematic_structure_entities_of_branch(obj_body))
        except Exception:
            own = {obj_body}
        robot_bodies = set()
        if self.robot is not None:
            try:
                robot_bodies = set(
                    w.get_kinematic_structure_entities_of_branch(self.robot.root))
            except Exception:
                pass
        best, best_z = None, -1e18
        for cand in (getattr(w, "bodies_with_collision", None) or w.bodies):
            if cand in own or cand in robot_bodies:
                continue
            try:
                if is_supported_by(obj_body, cand):
                    z = float(cand.global_pose.to_position().to_np().flatten()[2])
                    if z > best_z:
                        best_z, best = z, cand
            except Exception:
                continue
        return best

    # ---- world discovery (rebound every few seconds: worlds get modified) ----
    def _bind(self):
        w = self.world
        if w is None:
            return
        self._last_bind = time.time()
        try:
            from semantic_digital_twin.robots.robot_parts import AbstractRobot
            robots = w.get_semantic_annotations_by_type(AbstractRobot)
            self.robot = robots[0] if robots else None
        except Exception:
            self.robot = None
        conns = []
        for c in getattr(w, "connections", None) or []:
            if hasattr(c, "position"):
                try:
                    float(c.position)
                    conns.append(c)
                except Exception:
                    pass
        bodies = {}
        if self.robot is not None:
            bodies["__base__"] = self.robot.root
        # loose objects by convention: bodies named like mesh files
        scanned = False
        try:
            for b in w.bodies:
                n = str(getattr(b, "name", ""))
                base = n.split("/")[-1]
                if base.lower().endswith((".stl", ".obj", ".dae")):
                    bodies[base] = b
            scanned = True
        except Exception as ex:
            # the world is mid-modification (a body is being spawned/removed).
            # Keep the previous catalog instead of publishing an empty one —
            # the viewer would otherwise hide every object it already shows.
            print("[live_viz] body scan skipped this bind: %s" % ex, flush=True)
        if not scanned:
            for k, b in self._bodies.items():
                bodies.setdefault(k, b)
        self._conns, self._bodies = conns, bodies
        self._build_object_meta(bodies)

    def _build_object_meta(self, bodies):
        """Geometry catalog for the viewer: mesh URL per object (served by the
        bridge) or a box size, so objects the viewer doesn't have yet can be
        spawned live."""
        meta, serve, i = [], {}, 0
        for key, b in bodies.items():
            if key == "__base__":
                continue
            color = PALETTE[i % len(PALETTE)]
            i += 1
            mf = self._mesh_files.get(key.lower())
            oid = os.path.splitext(key)[0]
            if mf and os.path.isfile(mf):
                serve[key] = mf
                meta.append({"key": key, "id": oid, "kind": "mesh",
                             "mesh": "/mesh?key=" + urllib.parse.quote(key),
                             "format": os.path.splitext(key)[1].lstrip(".").lower(),
                             "color": color})
            else:
                meta.append({"key": key, "id": oid, "kind": "box",
                             "size": self._box_size(b) or [0.06, 0.06, 0.12], "color": color})
        self._mesh_serve = serve
        with self._lock:
            self.object_meta = meta

    @staticmethod
    def _box_size(body):
        """Best-effort AABB size of a body's visual/collision (metres)."""
        for attr in ("visual", "collision"):
            sc = getattr(body, attr, None)
            shapes = getattr(sc, "shapes", None) or (sc if isinstance(sc, (list, tuple)) else None)
            for sh in (shapes or []):
                scale = getattr(sh, "scale", None)
                if scale is not None:
                    try:
                        return [round(float(getattr(scale, ax)), 4) for ax in ("x", "y", "z")]
                    except Exception:
                        pass
        return None

    @staticmethod
    def _pose7(body):
        p = body.global_pose
        t = p.to_position().to_np().flatten()
        q = p.to_quaternion().to_np().flatten()
        return [round(float(v), 5) for v in (t[0], t[1], t[2], q[0], q[1], q[2], q[3])]

    def snapshot(self):
        if self.world is None:
            return
        if time.time() - self._last_bind > 3.0:
            self._bind()
        frames = {}
        for c in self._conns:
            try:
                frames[str(getattr(c, "name", ""))] = round(float(c.position), 5)
            except Exception:
                pass
        base = None
        objs = {}
        for n, b in self._bodies.items():
            try:
                if n == "__base__":
                    base = self._pose7(b)
                else:
                    objs[n] = self._pose7(b)
            except Exception:
                pass
        with self._lock:
            self.seq += 1
            self.state = {"seq": self.seq, "frames": frames, "base": base, "objects": objs}

    def get_state(self):
        with self._lock:
            return dict(self.state)

    # ---- plan tree ---------------------------------------------------------
    def bind_motion_group(self, executable):
        """A GiskardExecutable is about to run: remember which plan MotionNode
        maps to which statechart task, so the plan tree can show live progress."""
        try:
            for node, task in (executable.motion_mappings or {}).items():
                self._motion_tasks[id(node)] = task
        except Exception:
            pass
        title = ""
        try:
            for node in executable.motion_mappings or {}:
                action = getattr(node, "parent_action_node", None)
                d = getattr(action, "designator", None)
                if d is not None:
                    title = type(d).__name__
                    break
        except Exception:
            pass
        self._chart_title = title

    def freeze_motion_group(self, executable, status):
        """The group finished: pin its final status. Reading the tasks' life
        cycle afterwards is not reliable — the executor cleans its nodes up."""
        try:
            for node in (executable.motion_mappings or {}):
                self._frozen[id(node)] = status
                self._motion_tasks.pop(id(node), None)
            for attr in ("pre_condition_node", "post_condition_node"):
                cond = getattr(executable, attr, None)
                if cond is not None:
                    self._frozen[id(cond)] = status
        except Exception:
            pass

    def _live_motion_status(self, node):
        """Status of a single plan node from the statechart, or None."""
        task = self._motion_tasks.get(id(node))
        if task is not None:
            try:
                return LIFE_TO_STATUS.get(int(task.life_cycle_state))
            except Exception:
                pass
        return self._frozen.get(id(node))

    def snapshot_plan(self):
        plan = self._plan
        if plan is None:
            return
        try:
            root = plan.root
        except Exception:
            return                      # plan not a tree (yet) — try again later
        nodes, order = [], []

        def walk(n, parent_id):
            nid = "p%d" % id(n)
            d = getattr(n, "designator", None)
            own = getattr(getattr(n, "status", None), "name", "") or "CREATED"
            entry = {"id": nid, "parent": parent_id,
                     "kind": type(n).__name__,
                     "label": type(d).__name__ if d is not None else type(n).__name__,
                     "status": own, "derived": False}
            if d is not None:
                arm = getattr(d, "arm", None) or getattr(d, "arms", None)
                if arm is not None:
                    entry["arm"] = str(arm)
                target = self._designator_target(d)
                if target:
                    entry["target"] = target
            nodes.append(entry)
            order.append(nid)
            live = self._live_motion_status(n)
            child_best, children, done = "CREATED", 0, 0
            for c in (self._children_of(n) or []):
                child_status = walk(c, nid)
                child_best = self._max_status(child_best, child_status)
                children += 1
                if child_status == "SUCCEEDED":
                    done += 1
            # a real status wins; otherwise take the live statechart status, else
            # the aggregate of the children (RUNNING/FAILED bubble up). A node
            # whose children are only PARTLY done is running, not succeeded —
            # otherwise a half-executed action would already show up green.
            if own == "CREATED":
                if child_best == "SUCCEEDED" and done < children:
                    child_best = "RUNNING"
                derived = live or (child_best if child_best != "CREATED" else None)
                if derived:
                    entry["status"] = derived
                    entry["derived"] = True
            return entry["status"]

        walk(root, None)
        sig = "|".join(order)
        with self._lock:
            self.plan_state = {"sig": sig, "nodes": nodes}

    @staticmethod
    def _max_status(a, b):
        return a if STATUS_RANK.get(a, 0) >= STATUS_RANK.get(b, 0) else b

    @staticmethod
    def _children_of(node):
        try:
            return list(node.children)
        except Exception:
            return []

    def _designator_target(self, desig):
        """Name of the object a designator refers to, if it is one we know."""
        try:
            known = set(self._bodies)
        except Exception:
            return None
        for v in vars(desig).values():
            try:
                base = str(v.name).split("/")[-1]
            except Exception:
                continue
            if base in known:
                return base
        return None

    # ---- motion statechart -------------------------------------------------
    def observe_chart(self, chart):
        """Called from the tick hook with the executor's statechart. Structure is
        re-read only when the executor compiled a new one; the life cycle /
        observation vectors are cheap and refreshed whenever they change."""
        if chart is None:
            return
        if chart is not self._chart or self._chart_struct is None:
            self._chart = chart
            self._chart_struct = self._chart_structure(chart)
            self._last_life = None
        struct = self._chart_struct
        if not struct:
            return
        try:
            life = [int(chart.life_cycle_state.data[i]) for i in struct["idx"]]
            obs = [float(chart.observation_state.data[i]) for i in struct["idx"]]
        except Exception:
            return
        if life == self._last_life:
            return
        self._last_life = life
        nodes = []
        for i, n in enumerate(struct["nodes"]):
            e = dict(n)
            e["life"] = LIFE_NAME.get(life[i], str(life[i]))
            # trinary observation: 0.0 false, 0.5 unknown, 1.0 true
            e["obs"] = "TRUE" if obs[i] >= 0.75 else ("FALSE" if obs[i] <= 0.25 else "UNKNOWN")
            nodes.append(e)
        with self._lock:
            self.chart_state = {"sig": struct["sig"], "title": self._chart_title,
                                "nodes": nodes, "edges": struct["edges"]}

    @staticmethod
    def _chart_structure(chart):
        """Nodes + transition edges of a motion statechart, as plain dicts."""
        try:
            chart_nodes = list(chart.nodes)
        except Exception:
            return None
        nodes, idx = [], []
        for n in chart_nodes:
            parent = getattr(n, "parent_node_index", None)
            nodes.append({"id": "s%d" % n.index, "name": n.name,
                          "cls": type(n).__name__,
                          "parent": ("s%d" % parent) if parent is not None else None})
            idx.append(n.index)
        edges = []
        try:
            for u, v, transition in chart.rx_graph.edge_index_map().values():
                a = chart.rx_graph.get_node_data(u)
                b = chart.rx_graph.get_node_data(v)
                edges.append({"from": "s%d" % a.index, "to": "s%d" % b.index,
                              "kind": getattr(getattr(transition, "kind", None), "name", "")})
        except Exception:
            pass
        sig = "|".join(n["id"] + ":" + n["name"] for n in nodes)
        return {"nodes": nodes, "edges": edges, "idx": idx, "sig": sig}

    def get_plan(self):
        with self._lock:
            return dict(self.plan_state)

    def get_chart(self):
        with self._lock:
            return dict(self.chart_state)


BRIDGE = Bridge()
