#!/usr/bin/env python3
"""onboard_demo.py — turn a coraplex demo into a self-contained web-viewer scene.

Runs the demo file UNMODIFIED under instrumentation and emits a scene bundle:

    static/scenes/<name>/
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

Usage (interpreter needs the CRAM stack, e.g. the action-cram venv):
    ~/.virtualenvs/action-cram/bin/python tools/onboard_demo.py \
        ~/actions_cram/cognitive_robot_abstract_machine/coraplex/demos/coraplex_bullet_world_demo/demo.py \
        --name pr2_kitchen

By default `import rclpy` is blocked so demos skip their ROS visualization
branch; pass --allow-ros to keep it.
"""
import argparse
import json
import math
import os
import runpy
import sys
import time

from cram_viz.onboard.bundle_urdf import bundle_urdf  # noqa: E402
from cram_viz import paths  # noqa: E402

T0 = time.time()


def log(*a):
    print("[onboard %6.1fs]" % (time.time() - T0), *a, flush=True)


# ================================================================ recorder ===
class Recorder:
    def __init__(self):
        self.resolutions = {}          # uri -> resolved path
        self.urdf_sources = []         # URDF/xacro files the world was built from
        self.stl_sources = []          # loose object mesh files
        self.frames = []               # [{conn_name: position}]
        self.base_frames = []          # [[x,y,z,qx,qy,qz,qw]]
        self.obj_frames = []           # [{obj_name: pose7}]
        self.actions = []              # {action, depth, start, end}
        self.plan_nodes = []           # the actual ActionNode objects (plan tree)
        self._stack = []
        self.world = None
        self.robot = None
        self._conns = None
        self._bodies = None            # {obj_name: body}, incl. '__base__'
        self.control_dt = None

    # ---- asset hooks ---------------------------------------------------------
    def install_asset_hooks(self):
        from semantic_digital_twin.adapters.package_resolver import PackageUriResolver
        from semantic_digital_twin.adapters.urdf import URDFParser
        from semantic_digital_twin.adapters.mesh import STLParser
        rec = self

        orig_resolve = PackageUriResolver.resolve
        def resolve(self, uri):
            p = orig_resolve(self, uri)
            rec.resolutions[uri] = p
            return p
        PackageUriResolver.resolve = resolve

        orig_from_file = URDFParser.from_file.__func__
        def from_file(cls, file_path, **kw):
            if file_path not in rec.urdf_sources:
                rec.urdf_sources.append(file_path)
            return orig_from_file(cls, file_path, **kw)
        URDFParser.from_file = classmethod(from_file)

        orig_stl = STLParser.__init__
        def stl_init(self, file_path, *a, **kw):
            if file_path not in rec.stl_sources:
                rec.stl_sources.append(file_path)
            return orig_stl(self, file_path, *a, **kw)
        STLParser.__init__ = stl_init

    # ---- trajectory hook -----------------------------------------------------
    def install_tick_hook(self):
        from giskardpy.executor import Executor
        rec = self
        orig_tick = Executor.tick

        def tick(self, *a, **kw):
            r = orig_tick(self, *a, **kw)
            rec._snap(self)
            return r
        Executor.tick = tick

    def _lazy_bind(self, executor):
        self.world = executor.context.world
        try:
            self.control_dt = executor.context.qp_controller_config.control_dt
        except Exception:
            pass
        from semantic_digital_twin.robots.robot_parts import AbstractRobot
        robots = self.world.get_semantic_annotations_by_type(AbstractRobot)
        self.robot = robots[0] if robots else None
        self._bodies = {}
        if self.robot is not None:
            self._bodies["__base__"] = self.robot.root
        for f in self.stl_sources:
            name = os.path.basename(f)
            try:
                self._bodies[name] = self.world.get_body_by_name(name)
            except Exception:
                pass
        self._conns = []
        for c in getattr(self.world, "connections", None) or []:
            if hasattr(c, "position"):
                try:
                    float(c.position)
                    self._conns.append(c)
                except Exception:
                    pass
        log("bound: robot=%s, %d movable connections, objects=%s"
            % (type(self.robot).__name__ if self.robot else None,
               len(self._conns), [k for k in self._bodies if k != "__base__"]))

    @staticmethod
    def _pose7(body):
        p = body.global_pose
        t = p.to_position().to_np().flatten()
        q = p.to_quaternion().to_np().flatten()
        return [round(float(v), 5) for v in (t[0], t[1], t[2], q[0], q[1], q[2], q[3])]

    def _snap(self, executor):
        if self._conns is None:
            self._lazy_bind(executor)
        fr = {}
        for c in self._conns:
            try:
                fr[str(getattr(c, "name", ""))] = round(float(c.position), 5)
            except Exception:
                pass
        self.frames.append(fr)
        self.base_frames.append(self._pose7(self._bodies["__base__"]) if "__base__" in self._bodies else None)
        of = {}
        for n, b in self._bodies.items():
            if n == "__base__":
                continue
            try:
                of[n] = self._pose7(b)
            except Exception:
                pass
        self.obj_frames.append(of)
        if len(self.frames) % 2000 == 0:
            log("... %d frames" % len(self.frames))

    # ---- action metadata hook ----------------------------------------------------
    # Plans compile all actions into merged motion statecharts, so there is no
    # per-action call boundary at execution time. ActionNode.parse DOES fire
    # once per action (in plan order) — we record the action class, its arm and
    # its target object there, and later derive the segment TIMING from the
    # recorded data (object attach/detach + first base motion).
    def _target_of(self, desig):
        basenames = {os.path.basename(f) for f in self.stl_sources}
        for v in vars(desig).values():
            try:
                nm = str(getattr(v, "name"))
            except Exception:
                continue
            base = nm.split("/")[-1]
            if base in basenames:
                return base
        return None

    def install_segment_hook(self):
        from coraplex.plans.plan_node import ActionNode
        rec = self
        orig_parse = ActionNode.parse

        def parse(node, *a, **kw):
            d = node.designator
            arm = getattr(d, "arm", None) or getattr(d, "arms", None)
            rec.actions.append({"action": type(d).__name__,
                                "arm": str(arm) if arm is not None else None,
                                "target": rec._target_of(d)})
            rec.plan_nodes.append(node)
            log("action parsed:", rec.actions[-1]["action"],
                "->", rec.actions[-1]["target"] or "-")
            return orig_parse(node, *a, **kw)
        ActionNode.parse = parse

    # ---- the executed plan tree, serialized from the real PlanNode graph ------
    def serialize_plans(self, max_nodes=400):
        roots, seen = [], set()
        for n in self.plan_nodes:
            r = n
            while getattr(r, "parent", None) is not None:
                r = r.parent
            if id(r) not in seen:
                seen.add(id(r))
                roots.append(r)
        count = [0]

        def ser(n):
            if count[0] >= max_nodes:
                return None
            count[0] += 1
            d = getattr(n, "designator", None)
            status = getattr(n, "status", None)
            entry = {"kind": type(n).__name__,
                     "label": type(d).__name__ if d is not None else type(n).__name__,
                     "status": getattr(status, "name", str(status) if status else "")}
            if d is not None:
                tgt = self._target_of(d)
                if tgt:
                    entry["target"] = tgt
                arm = getattr(d, "arm", None) or getattr(d, "arms", None)
                if arm is not None:
                    entry["arm"] = str(arm)
            kids = [ser(c) for c in getattr(n, "children", ()) or ()]
            entry["children"] = [k for k in kids if k]
            return entry
        return [t for t in (ser(r) for r in roots) if t]


# ============================================================ post-process ===
def moved(a, b, eps=0.02):
    return math.hypot(a[0] - b[0], a[1] - b[1]) + abs(a[2] - b[2]) > eps


def object_windows(rec):
    """attach..detach window (raw frames) per object that travelled overall."""
    O = rec.obj_frames
    n = len(O)
    wins = []
    for name in O[0]:
        p0, pe = O[0].get(name), O[n - 1].get(name)
        if not p0 or not pe or not moved(p0, pe, 0.03):
            continue
        attach = next((i for i in range(n) if name in O[i] and moved(O[i][name], p0)), n - 1)
        detach = next((i for i in range(n - 1, -1, -1) if name in O[i] and moved(O[i][name], pe)), 0) + 1
        if attach < detach:
            wins.append({"object": name, "attach": attach, "detach": detach, "place": pe[:3]})
    wins.sort(key=lambda w: w["attach"])
    return wins


def first_base_motion(rec, before):
    """First raw frame (< before) at which the robot base left its spawn."""
    b0 = rec.base_frames[0]
    for i in range(min(before, len(rec.base_frames))):
        b = rec.base_frames[i]
        if b and b0 and math.hypot(b[0] - b0[0], b[1] - b0[1]) > 0.05:
            return i
    return before


def derive_segments(rec):
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
            label = (lead_acts[0]["action"].replace("Action", "").lower()
                     if len(lead_acts) == 1 else "prepare")
            segments.append({"step": label, "action": ",".join(x["action"] for x in lead_acts) or None,
                             "arm": None, "start": 0, "end": lead_end})
            prev = lead_end
    remaining = list(manip_acts)
    for k, w in enumerate(wins):
        act = next((x for x in remaining if x["target"] == w["object"]), None)
        if act:
            remaining.remove(act)
        oid = os.path.splitext(w["object"])[0]
        verb = (act["action"].replace("Action", "").lower() if act else "move")
        nxt = wins[k + 1]["attach"] if k + 1 < len(wins) else n - 1
        end = min(nxt, w["detach"] + max(10, (nxt - w["detach"]) // 2)) if k + 1 < len(wins) else n - 1
        segments.append({"step": "%s_%s" % (verb, oid),
                         "action": act["action"] if act else None,
                         "arm": act["arm"] if act else None,
                         "start": prev, "end": end, "picks": oid,
                         "attach": w["attach"], "detach": w["detach"], "place": w["place"]})
        prev = end
    if not segments:
        label = (rec.actions[0]["action"].replace("Action", "").lower()
                 if len(rec.actions) == 1 else "plan")
        segments.append({"step": label, "action": None, "arm": None, "start": 0, "end": n - 1})
    return segments


PALETTE = ["#f3f0ea", "#cf5b3a", "#b8bcc4", "#e7c26a", "#7fb069", "#5b8cff"]


def link_set(part):
    out = []
    for b in getattr(part, "bodies", None) or []:
        n = str(getattr(b, "name", b))
        out.append(n.split("/", 1)[1] if "/" in n else n)
    return out


def build_scene(rec, name, out_dir, step):
    n = len(rec.frames)
    idx = list(range(0, n, step))
    if idx and idx[-1] != n - 1:
        idx.append(n - 1)
    remap = {}
    for k, orig in enumerate(idx):
        remap[orig] = k

    def nearest(i):
        return remap.get(i, remap[min(remap, key=lambda o: abs(o - i))])

    frames = [rec.frames[i] for i in idx]
    base = [rec.base_frames[i] for i in idx]
    objs = [rec.obj_frames[i] for i in idx]

    raw_fps = 1.0 / rec.control_dt if rec.control_dt else 50.0
    fps = max(10, round(raw_fps / step))

    # ---- robot description ----------------------------------------------------
    robot = rec.robot
    root_name = str(robot.root.name)
    prefix = root_name.split("/", 1)[0] if "/" in root_name else ""
    base_body = root_name.split("/", 1)[1] if "/" in root_name else root_name
    parts = {}
    try:
        for arm in robot.get_arms():
            arm_links = link_set(arm)
            ee = getattr(arm, "end_effector", None)
            ee_links = link_set(ee) if ee is not None else []
            key = type(arm).__name__
            parts[key] = sorted(set(arm_links) - set(ee_links))
            if ee is not None:
                parts[type(ee).__name__] = sorted(set(ee_links))
    except Exception as ex:
        log("arm introspection failed:", ex)

    # ---- segments: data-derived windows, labelled from the parsed actions -----
    segments = []
    for s in derive_segments(rec):
        e = dict(s)
        e["start"] = nearest(s["start"])
        e["end"] = nearest(s["end"])
        if "attach" in e:
            e["attach"] = nearest(s["attach"])
            e["detach"] = nearest(s["detach"])
        segments.append(e)
    seen = {}
    for s in segments:
        seen[s["step"]] = seen.get(s["step"], 0) + 1
        if seen[s["step"]] > 1:
            s["step"] = "%s_%d" % (s["step"], seen[s["step"]])

    # ---- objects ---------------------------------------------------------------
    objects = []
    for i, src in enumerate(rec.stl_sources):
        mesh = os.path.basename(src)
        if mesh not in rec.obj_frames[0]:
            continue
        dst = os.path.join(out_dir, "meshes", "objects", mesh)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        import shutil
        shutil.copy2(src, dst)
        objects.append({"id": os.path.splitext(mesh)[0], "key": mesh,
                        "mesh": "meshes/objects/" + mesh,
                        "spawn": rec.obj_frames[0][mesh],
                        "color": PALETTE[i % len(PALETTE)]})

    # ---- place target + drag bounds -------------------------------------------
    places = [s["place"] for s in segments if s.get("place")]
    place_target = None
    if places:
        cx = sum(p[0] for p in places) / len(places)
        cy = sum(p[1] for p in places) / len(places)
        cz = min(p[2] for p in places)
        place_target = {"pos": [round(cx, 3), round(cy, 3)], "z": round(cz - 0.02, 3),
                        "bounds": {"minX": round(cx - 0.55, 2), "maxX": round(cx + 0.55, 2),
                                   "minY": round(cy - 0.55, 2), "maxY": round(cy + 0.65, 2)}}
    drag_bounds = None
    if objects:
        xs = [o["spawn"][0] for o in objects]
        ys = [o["spawn"][1] for o in objects]
        drag_bounds = {"minX": round(min(xs) - 0.35, 2), "maxX": round(max(xs) + 0.35, 2),
                       "minY": round(min(ys) - 0.6, 2), "maxY": round(max(ys) + 0.6, 2)}

    # ---- bundle the URDF models -------------------------------------------------
    world_body_names = [str(getattr(b, "name", "")) for b in rec.world.bodies]
    models, missing = [], []
    for i, src in enumerate(rec.urdf_sources):
        base_name = os.path.splitext(os.path.basename(src))[0]
        rep = bundle_urdf(src, base_name, out_dir, hints=rec.resolutions)
        missing += rep["missing"]
        # find this model's prefix in the composed world via one of its links
        mprefix = ""
        for ln in rep["links"][:12]:
            hit = next((w for w in world_body_names if w.endswith("/" + ln)), None)
            if hit:
                mprefix = hit.split("/", 1)[0]
                break
        is_robot = base_body in rep["links"]
        models.append({"name": base_name, "urdf": "%s.urdf" % base_name,
                       "prefix": mprefix, "robot": is_robot,
                       "links": len(rep["links"]), "movableJoints": rep["movable_joints"]})
        log("bundled %-28s prefix=%-12s robot=%s meshes=%d missing=%d"
            % (base_name, mprefix or "-", is_robot, rep["meshes_copied"], len(rep["missing"])))

    scene = {
        "name": name,
        "fps": fps,
        "trajectory": "trajectory.json",
        "models": models,
        "robot": {"name": type(robot).__name__.lower(), "prefix": prefix,
                  "baseBody": base_body, "parts": parts},
        "objects": objects,
        "segments": segments,
        "actions": rec.actions,
        "planTrees": rec.serialize_plans(),
        "placeTarget": place_target,
        "dragBounds": drag_bounds,
        "missingAssets": sorted(set(missing)),
    }
    json.dump(scene, open(os.path.join(out_dir, "scene.json"), "w"), indent=1)
    json.dump({"fps": fps, "frames": frames, "base": base, "objects": objs},
              open(os.path.join(out_dir, "trajectory.json"), "w"))
    return scene


# ==================================================================== main ===
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demo", help="path to the coraplex demo .py file")
    ap.add_argument("--name", required=True, help="scene name (output folder)")
    ap.add_argument("--out", default=str(paths.scenes_dir()),
                    help="scenes directory (default: CRAM_VIZ_SCENES or ~/.cram_viz/scenes)")
    ap.add_argument("--step", type=int, default=0, help="downsample step (0 = auto)")
    args = ap.parse_args()

    try:
        import coraplex  # noqa: F401
    except ModuleNotFoundError:
        sys.exit("The CRAM stack is not importable — run under the action-cram venv:\n"
                 "  ~/.virtualenvs/action-cram/bin/python tools/onboard_demo.py ...")

    rec = Recorder()
    rec.install_asset_hooks()
    rec.install_tick_hook()
    rec.install_segment_hook()

    demo = os.path.abspath(args.demo)
    log("running demo:", demo)
    sys.path.insert(0, os.path.dirname(demo))
    # make repo-level helper packages (e.g. test.conftest) importable — the
    # demos rely on pytest's rootdir behaviour for that
    d = os.path.dirname(demo)
    while d != os.path.dirname(d):
        if os.path.isdir(os.path.join(d, "coraplex")) and os.path.isdir(os.path.join(d, "test")):
            sys.path.insert(0, d)
            log("repo root on sys.path:", d)
            break
        d = os.path.dirname(d)
    runpy.run_path(demo, run_name="__main__")
    log("demo finished: %d raw frames, %d actions" % (len(rec.frames), len(rec.actions)))

    if not rec.frames:
        sys.exit("No frames captured — did the demo perform a plan?")
    if rec.robot is None:
        sys.exit("No AbstractRobot semantic annotation found in the world.")

    step = args.step or max(1, len(rec.frames) // 1500)
    out_dir = os.path.join(args.out, args.name)
    os.makedirs(out_dir, exist_ok=True)
    scene = build_scene(rec, args.name, out_dir, step)

    # maintain the scene index the viewer reads
    idx_path = os.path.join(args.out, "index.json")
    try:
        index = json.load(open(idx_path))
    except Exception:
        index = {"default": args.name, "scenes": []}
    if args.name not in index["scenes"]:
        index["scenes"].append(args.name)
    index.setdefault("default", args.name)
    json.dump(index, open(idx_path, "w"), indent=1)

    log("scene '%s' written to %s" % (args.name, out_dir))
    log("  models:  %s" % ", ".join("%s%s" % (m["name"], " (robot)" if m["robot"] else "") for m in scene["models"]))
    log("  objects: %s" % ", ".join(o["id"] for o in scene["objects"]))
    log("  segments: %s" % " → ".join(s["step"] for s in scene["segments"]))
    if scene["missingAssets"]:
        log("  WARNING — %d missing assets:" % len(scene["missingAssets"]))
        for m in scene["missingAssets"][:10]:
            log("   ", m)
    sys.stdout.flush()
    os._exit(0)      # don't hang on non-daemon ROS/viz threads the demo started


if __name__ == "__main__":
    main()
