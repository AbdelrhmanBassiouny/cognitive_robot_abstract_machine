"""The recorded demo scene as an EQL (Entity Query Language) knowledge base.

EQL is krrood's pythonic relational query language. This module models the
recorded coraplex/giskardpy episode — bench objects, robot parts, action
episodes, per-joint motion — as plain dataclasses and exposes:

    fresh_namespace()  -> dict for evaluating one EQL query (fresh variables)
    run_query(code)    -> execute an EQL query string, return JSON-able result
    graph_payload()    -> nodes/edges/details/presets for the UI knowledge graph
    view_payload(name) -> one of the graph-panel tabs (knowledge / kinematics /
                          plan / chart)

krrood is imported lazily: without it the static viewer still works, only the
EQL panel is unavailable. Scene bundles are read from paths.scenes_dir().
"""
import ast
import json
import math
import os
from dataclasses import dataclass, fields, is_dataclass
from typing import Optional

from cram_viz import paths


def scene_name():
    """Active scene: $CRAM_VIZ_SCENE, else the scenes index default."""
    env = os.environ.get("CRAM_VIZ_SCENE")
    if env:
        return env
    try:
        index = json.load(open(os.path.join(str(paths.scenes_dir()), "index.json")))
        return index["default"]
    except Exception:
        return None


def scene_dir():
    n = scene_name()
    return os.path.join(str(paths.scenes_dir()), n) if n else None


def load_scene():
    """(scene.json, trajectory.json) of the active scene, or ({}, {})."""
    d = scene_dir()
    if not d:
        return {}, {}
    try:
        sc = json.load(open(os.path.join(d, "scene.json")))
    except Exception:
        return {}, {}
    try:
        tr = json.load(open(os.path.join(d, sc.get("trajectory", "trajectory.json"))))
    except Exception:
        tr = {}
    return sc, tr


def load_urdf():
    """Parse the active scene's ROBOT urdf into (links, joints) for the
    kinematic-tree drill view. Regex parse — the bundled URDFs are flat."""
    import re
    sc, _ = load_scene()
    robot_model = next((m for m in sc.get("models", []) if m.get("robot")), None)
    d = scene_dir()
    if not robot_model or not d:
        return [], []
    try:
        txt = open(os.path.join(d, robot_model["urdf"]), encoding="utf-8", errors="replace").read()
    except OSError:
        return [], []
    links = re.findall(r'<link\s+name="([^"]+)"', txt)
    joints = []
    for m in re.finditer(r'<joint\s+name="([^"]+)"\s+type="([^"]+)">(.*?)</joint>', txt, re.S):
        body = m.group(3)
        parent = re.search(r'<parent\s+link="([^"]+)"', body)
        child = re.search(r'<child\s+link="([^"]+)"', body)
        if parent and child:
            joints.append({"name": m.group(1), "type": m.group(2),
                           "parent": parent.group(1), "child": child.group(1)})
    return links, joints


# ---------------------------------------------------------------- the model --
@dataclass(unsafe_hash=True)
class Position:
    x: float
    y: float
    z: float

    def __repr__(self):
        return "(%.2f, %.2f, %.2f)" % (self.x, self.y, self.z)


@dataclass(unsafe_hash=True)
class Gripper:
    name: str
    side: str
    opening_m: float = 0.085          # Robotiq 2F-85


@dataclass(unsafe_hash=True)
class Arm:
    name: str
    side: str
    robot: str
    gripper: Gripper


@dataclass(unsafe_hash=True)
class Robot:
    name: str
    arm_count: int


@dataclass(unsafe_hash=True)
class BenchObject:
    name: str
    kind: str
    label: str
    height_m: float
    position: Position


@dataclass(unsafe_hash=True)
class ActionEpisode:
    name: str
    index: int
    start_frame: int
    end_frame: int
    duration_s: float
    performed_by: Optional[Arm]
    picks: Optional[BenchObject]
    places_at: Optional[BenchObject]


@dataclass(unsafe_hash=True)
class JointMotion:
    name: str
    arm_side: str                     # 'left' | 'right'
    min_rad: float
    max_rad: float
    range_rad: float


# ---- the CRAM architecture itself, scanned from ~/cognitive_robot_abstract_machine
@dataclass(unsafe_hash=True)
class Package:
    name: str
    description: str
    module_count: int
    class_count: int


@dataclass(unsafe_hash=True)
class SubPackage:
    name: str                         # qualified, e.g. 'coraplex.plans'
    package: str
    module_count: int
    class_count: int


@dataclass(unsafe_hash=True)
class PythonClass:
    name: str
    package: str
    subpackage: str                   # 'coraplex.plans' (== package for top-level modules)
    module: str                       # repo-relative module path
    bases: tuple                      # names of direct base classes
    methods: int
    doc: str                          # first docstring line ('' if none)


# -------------------------------------------- scan the CRAM architecture ----
def _cram_root():
    return str(paths.architecture_root())


def _arch_cache():
    # always in the writable data dir — scenes_dir() may be a read-only checkout
    return os.path.join(str(paths.data_dir()), "arch_cache.json")
SKIP_DIRS = {"__pycache__", "node_modules", "doc", "docs", "resources", "build", "dist", "plugins"}
PKG_DESCRIPTIONS = {
    "krrood": "knowledge representation & reasoning through OO design (home of EQL)",
    "coraplex": "the plan executive: designators, plans, locations",
    "pycram": "legacy plan executive (resources/demos)",
    "giskardpy": "constraint-based motion planning and control",
    "robokudo": "perception framework",
    "semantic_digital_twin": "semantic world model / digital twin",
    "segmind": "segmentation / vision models",
    "probabilistic_model": "probabilistic models and inference",
    "random_events": "sigma-algebra & random events for probabilistic reasoning",
    "physics_simulators": "physics simulator bindings",
    "experiments": "experiment scripts (incl. EQL experiments)",
    "test": "the test suites of all packages",
    "scripts": "maintenance scripts",
    "root": "top-level demo scripts (sterility test, wind turbine…)",
}


def _first_readme_line(d):
    for name in ("README.md", "readme.md"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            for line in open(p, encoding="utf-8", errors="replace"):
                line = line.strip().lstrip("#").strip()
                if line:
                    return line[:120]
    return ""


def scan_architecture():
    """AST-scan the CRAM repo: packages, classes, cross-package imports.
    Static parse only — nothing is imported. Cached to disk keyed by file count."""
    packages, classes, imports = [], [], {}
    cram_root = _cram_root()
    if not os.path.isdir(cram_root):
        return packages, classes, []

    pkg_dirs = {"root": cram_root}
    for e in sorted(os.listdir(cram_root)):
        d = os.path.join(cram_root, e)
        if os.path.isdir(d) and not e.startswith(".") and e not in SKIP_DIRS and "egg-info" not in e:
            pkg_dirs[e] = d
    pkg_names = set(pkg_dirs)

    per_pkg = {}
    for pkg, base in pkg_dirs.items():
        mods = 0
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if not x.startswith(".") and x not in SKIP_DIRS]
            if pkg == "root":
                dirnames[:] = []                    # root package = top-level scripts only
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
                except SyntaxError:
                    continue
                mods += 1
                rel = os.path.relpath(path, cram_root)[:-3].replace(os.sep, ".")
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        bases = tuple(
                            b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else "?")
                            for b in node.bases
                        )
                        doc = (ast.get_docstring(node) or "").strip().split("\n")[0][:140]
                        methods = sum(1 for x in node.body
                                      if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)))
                        classes.append(dict(name=node.name, package=pkg, module=rel,
                                            bases=list(bases), methods=methods, doc=doc))
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        roots = ([a.name.split(".")[0] for a in node.names]
                                 if isinstance(node, ast.Import)
                                 else [(node.module or "").split(".")[0]] if node.level == 0 else [])
                        for r in roots:
                            if r in pkg_names and r != pkg:
                                imports.setdefault(pkg, set()).add(r)
        per_pkg[pkg] = mods

    from collections import Counter
    ccount = Counter(c["package"] for c in classes)
    for pkg in pkg_dirs:
        desc = PKG_DESCRIPTIONS.get(pkg) or _first_readme_line(pkg_dirs[pkg])
        packages.append(dict(name=pkg, description=desc,
                             module_count=per_pkg.get(pkg, 0), class_count=ccount.get(pkg, 0)))
    dep_edges = sorted((a, b) for a, deps in imports.items() for b in deps)
    return packages, classes, dep_edges


def load_architecture():
    """scan_architecture() with a JSON disk cache (a full scan takes seconds)."""
    # A full scan takes seconds, so it is cached in the data directory, keyed
    # by the scanned root; a cache from another root is rescanned.
    cram_root = _cram_root()
    have_repo = os.path.isdir(cram_root)
    try:
        cached = json.load(open(_arch_cache()))
        if cached.get("version") == 2 and (not have_repo or cached.get("cram_root") == cram_root):
            return cached["packages"], cached["classes"], [tuple(e) for e in cached["deps"]]
    except Exception:
        pass
    if not have_repo:
        return [], [], []
    packages, classes, deps = scan_architecture()
    if not classes:
        # a checkout exists but yielded nothing (empty or partial clone) — fall
        # back to the cache rather than losing the architecture graph
        try:
            cached = json.load(open(_arch_cache()))
            if cached.get("version") == 2 and cached.get("classes"):
                return cached["packages"], cached["classes"], [tuple(e) for e in cached["deps"]]
        except Exception:
            pass
        return packages, classes, deps
    try:
        os.makedirs(os.path.dirname(_arch_cache()), exist_ok=True)
        json.dump({"version": 2, "cram_root": cram_root, "packages": packages,
                   "classes": classes, "deps": deps}, open(_arch_cache(), "w"))
    except Exception:
        pass
    return packages, classes, deps


def _side_of_name(name):
    n = name.lower()
    if "left" in n or n.startswith("l_"):
        return "left"
    if "right" in n or n.startswith("r_"):
        return "right"
    return ""


class KB:
    def __init__(self):
        sc, tr = load_scene()
        fps = sc.get("fps", 30)
        parts = (sc.get("robot") or {}).get("parts") or {}
        robot_name = (sc.get("robot") or {}).get("name", "robot")
        robot_prefix = (sc.get("robot") or {}).get("prefix", "")

        # scene objects (spawn poses were recorded at frame 0 of the episode)
        self.objects = []
        by_id = {}
        for o in sc.get("objects") or []:
            obj = BenchObject(name=o["id"], kind="object", label=o["id"].replace("_", " ").title(),
                              height_m=0.1, position=Position(*[round(v, 3) for v in o["spawn"][:3]]))
            self.objects.append(obj)
            by_id[o["id"]] = obj
        place_area = None
        if sc.get("placeTarget"):
            pt = sc["placeTarget"]
            place_area = BenchObject(name="place_area", kind="location", label="Place area",
                                     height_m=0.0,
                                     position=Position(round(pt["pos"][0], 3), round(pt["pos"][1], 3), pt.get("z", 0)))
            self.objects.append(place_area)

        # arms + grippers straight from the recorded robot annotation parts.
        # Gripper keywords take precedence — robot names can contain 'arm'
        # themselves (g-ARM-i), so 'arm' alone must not decide.
        grip_parts = [p for p in parts
                      if any(k in p.lower() for k in ("gripper", "hand", "effector"))]
        arm_parts = [p for p in parts if p not in grip_parts and "arm" in p.lower()]
        self.grippers, self.arms = [], []
        for ap in sorted(arm_parts):
            side = _side_of_name(ap) or "n/a"
            gp = next((g for g in grip_parts if _side_of_name(g) == side), None)
            gripper = Gripper(gp or (ap + "_ee"), side)
            self.grippers.append(gripper)
            self.arms.append(Arm(ap, side, robot_name, gripper))
        self.robot = Robot(robot_name, arm_count=len(self.arms))

        def arm_for(segment):
            hint = (segment.get("arm") or "").lower()
            for a in self.arms:
                if a.side and a.side in hint:
                    return a
            return self.arms[0] if self.arms and segment.get("picks") else None

        self.episodes = []
        for i, s in enumerate(sc.get("segments") or []):
            picks = by_id.get(s.get("picks"))
            self.episodes.append(ActionEpisode(
                name=s["step"], index=i,
                start_frame=s["start"], end_frame=s["end"],
                duration_s=round((s["end"] - s["start"]) / max(1, fps), 1),
                performed_by=arm_for(s) if picks else None,
                picks=picks,
                places_at=place_area if picks else None,
            ))

        # per-joint motion statistics over the whole recorded trajectory
        lo, hi = {}, {}
        for fr in tr.get("frames") or []:
            for k, v in fr.items():
                if k not in lo or v < lo[k]:
                    lo[k] = v
                if k not in hi or v > hi[k]:
                    hi[k] = v

        link_to_part = {}
        for p, links in parts.items():
            for l in links:
                link_to_part[l] = p

        def side_of(key):
            prefix, _, rest = key.partition("/")
            if "/" not in key:
                prefix, rest = "", key
            if robot_prefix and prefix != robot_prefix:
                return "environment"
            part = link_to_part.get(rest.replace("_joint", "_link"))
            if part:
                s = _side_of_name(part)
                if s:
                    return s
            s = _side_of_name(rest)
            return s or "body"

        self.joints = [
            JointMotion(name=k.partition("/")[2] or k, arm_side=side_of(k),
                        min_rad=round(lo[k], 3), max_rad=round(hi[k], 3),
                        range_rad=round(hi[k] - lo[k], 3))
            for k in sorted(lo)
        ]

        # the CRAM architecture itself: packages + every Python class in the repo
        pkgs, clss, deps = load_architecture()
        self.packages = [Package(**p) for p in pkgs]

        def sub_of(pkg, module):
            # 'coraplex.src.coraplex.plans.designator' -> 'coraplex.plans';
            # top-level modules collapse onto the package itself
            parts = module.split(".")
            if parts and parts[0] == pkg:
                parts = parts[1:]
            while parts and parts[0] in ("src", pkg):
                parts = parts[1:]
            return pkg + "." + parts[0] if len(parts) >= 2 else pkg

        self.classes = [PythonClass(name=c["name"], package=c["package"],
                                    subpackage=sub_of(c["package"], c["module"]),
                                    module=c["module"], bases=tuple(c["bases"]),
                                    methods=c["methods"], doc=c["doc"])
                        for c in clss]
        self.package_deps = deps

        from collections import defaultdict
        mods, ccnt = defaultdict(set), defaultdict(int)
        for c in self.classes:
            if c.subpackage != c.package:
                mods[(c.package, c.subpackage)].add(c.module)
                ccnt[c.subpackage] += 1
        self.subpackages = [
            SubPackage(name=s, package=p, module_count=len(mods[(p, s)]), class_count=ccnt[s])
            for (p, s) in sorted(mods)
        ]


_kb = None


def get_kb():
    global _kb
    if _kb is None:
        _kb = KB()
    return _kb


def reset_kb():
    """Drop the cached KB (tests point CRAM_VIZ_SCENES at fixtures)."""
    global _kb
    _kb = None


# -------------------------------------------------------------- EQL session --
# factories re-exported into every query namespace
_FACTORY_NAMES = [
    "entity", "set_of", "variable", "an", "a", "the", "and_", "or_", "not_",
    "contains", "in_", "exists", "for_all", "count", "count_all", "average",
    "sum", "min", "max", "mode", "distinct", "flat_variable", "variable_from",
]


def fresh_namespace():
    from krrood.entity_query_language import factories as F
    kb = get_kb()
    ns = {n: getattr(F, n) for n in _FACTORY_NAMES if hasattr(F, n)}
    ns.update(
        Position=Position, Gripper=Gripper, Arm=Arm, Robot=Robot,
        BenchObject=BenchObject, ActionEpisode=ActionEpisode, JointMotion=JointMotion,
        Package=Package, SubPackage=SubPackage, PythonClass=PythonClass,
        objects=kb.objects, episodes=kb.episodes, arms=kb.arms,
        grippers=kb.grippers, joints=kb.joints, robots=[kb.robot],
        packages=kb.packages, subpackages=kb.subpackages, classes=kb.classes,
    )
    # ready-made query variables so one-liners stay short
    ns["obj"] = F.variable(BenchObject, domain=kb.objects)
    ns["ep"] = F.variable(ActionEpisode, domain=kb.episodes)
    ns["arm"] = F.variable(Arm, domain=kb.arms)
    ns["j"] = F.variable(JointMotion, domain=kb.joints)
    ns["rob"] = F.variable(Robot, domain=[kb.robot])
    ns["pkg"] = F.variable(Package, domain=kb.packages)
    ns["sub"] = F.variable(SubPackage, domain=kb.subpackages)
    ns["cls"] = F.variable(PythonClass, domain=kb.classes)
    return ns


def _entity_name(v):
    return getattr(v, "name", None)


def _jsonable(v):
    if is_dataclass(v) and not isinstance(v, type):
        return _entity_name(v) or repr(v)
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    return repr(v)


def run_query(code, limit=200):
    """Execute an EQL query string; the last expression is the query."""
    ns = fresh_namespace()
    tree = ast.parse(code, mode="exec")
    if not tree.body:
        raise ValueError("empty query")
    last = tree.body[-1]
    if isinstance(last, ast.Expr):
        if len(tree.body) > 1:
            pre = ast.Module(body=tree.body[:-1], type_ignores=[])
            exec(compile(pre, "<eql>", "exec"), ns)
        result = eval(compile(ast.Expression(last.value), "<eql>", "eval"), ns)
    else:
        exec(compile(tree, "<eql>", "exec"), ns)
        result = ns.get("result")

    if hasattr(result, "evaluate"):
        result = result.evaluate()

    rows, highlight, more = [], [], False
    if result is None:
        pass
    elif isinstance(result, (str, int, float, bool)):
        rows.append({"value": _jsonable(result)})
    elif is_dataclass(result) and not isinstance(result, type):
        rows.append(_entity_row(result, highlight))
    else:
        try:
            it = iter(result)
        except TypeError:
            rows.append({"value": _jsonable(result)})
            it = None
        if it is not None:
            for item in it:
                if len(rows) >= limit:
                    more = True
                    break
                rows.append(_item_row(item, highlight))
    kind = "rows" if rows and "__entity__" not in rows[0] else "entities"
    return {"ok": True, "kind": kind, "rows": rows, "count": len(rows),
            "more": more, "highlight": sorted(set(highlight))}


def _entity_row(item, highlight):
    name = _entity_name(item)
    if name:
        highlight.append(name)
    if isinstance(item, PythonClass):
        # classes aren't graph nodes — light up their subpackage + package instead
        highlight.append(item.subpackage)
        highlight.append(item.package)
    row = {"__entity__": name or repr(item), "__type__": type(item).__name__}
    for f in fields(item):
        if f.name != "name":
            row[f.name] = _jsonable(getattr(item, f.name))
    return row


def _item_row(item, highlight):
    if is_dataclass(item) and not isinstance(item, type):
        return _entity_row(item, highlight)
    if hasattr(item, "items"):                 # UnificationDict from set_of()
        row = {}
        for k, v in item.items():
            if is_dataclass(v) and not isinstance(v, type) and _entity_name(v):
                highlight.append(_entity_name(v))
            row[str(k)] = _jsonable(v)
        return row
    return {"value": _jsonable(item)}


# ------------------------------------------------------------ the UI graph --
def graph_payload():
    kb = get_kb()
    nodes, edges, details = [], [], {}

    def add(nid, label, group, lines):
        nodes.append({"id": nid, "label": label, "group": group,
                      "title": "\n".join([label] + lines)})
        details[nid] = {"label": label, "group": group, "lines": lines}

    rob = kb.robot.name
    add(rob, rob, "robot",
        ["a Robot", "%d arm%s" % (kb.robot.arm_count, "" if kb.robot.arm_count == 1 else "s"),
         "double-click: full URDF tree"])
    for a in kb.arms:
        add(a.name, a.name.replace("_", " "), "robot",
            ["an Arm", "side: " + a.side, "gripper: " + a.gripper.name])
        edges.append({"from": rob, "to": a.name, "kind": "prop", "label": "has part"})
        add(a.gripper.name, a.gripper.name.replace("_", " "), "robot",
            ["a Gripper", "side: " + a.gripper.side, "opening: %.3f m" % a.gripper.opening_m])
        edges.append({"from": a.name, "to": a.gripper.name, "kind": "prop", "label": "has part"})

    for o in kb.objects:
        add(o.name, o.label, "object",
            ["a BenchObject", "kind: " + o.kind, "position: " + repr(o.position),
             "height: %.2f m" % o.height_m])

    prev = None
    for e in kb.episodes:
        add(e.name, e.name, "event",
            ["an ActionEpisode", "frames %d–%d" % (e.start_frame, e.end_frame),
             "duration: %.1f s" % e.duration_s]
            + (["picks: " + e.picks.name] if e.picks else [])
            + (["places at: " + e.places_at.name] if e.places_at else []))
        if prev:
            edges.append({"from": prev, "to": e.name, "kind": "type", "label": "precedes"})
        prev = e.name
        # the ROBOT performs the episode (with its arm); don't wire the episode
        # straight to the arm — the arm hangs off the robot, so the chain reads
        # transport_milk → pr2 → left_arm → left_gripper
        if e.performed_by:
            edges.append({"from": e.name, "to": e.performed_by.robot, "kind": "prop", "label": "performed by"})
        if e.picks:
            edges.append({"from": e.name, "to": e.picks.name, "kind": "prop", "label": "picks"})
        if e.places_at:
            edges.append({"from": e.name, "to": e.places_at.name, "kind": "prop", "label": "places at"})

    # the CRAM architecture cluster: repo root → packages, plus import edges
    if kb.packages:
        add("cram", "CRAM architecture", "root",
            ["~/cognitive_robot_abstract_machine",
             "%d packages · %d Python classes" % (len(kb.packages), len(kb.classes))])
        for p in kb.packages:
            add(p.name, p.name, "concept",
                ["a Package", p.description,
                 "%d modules · %d classes" % (p.module_count, p.class_count),
                 "double-click to open"])
            edges.append({"from": "cram", "to": p.name, "kind": "prop", "label": "contains"})
        for s in kb.subpackages:
            add(s.name, s.name.split(".", 1)[1], "klass",
                ["a SubPackage of " + s.package,
                 "%d modules · %d classes" % (s.module_count, s.class_count),
                 "double-click to open"])
            edges.append({"from": s.package, "to": s.name, "kind": "prop", "label": "contains"})
        for a, b in kb.package_deps:
            edges.append({"from": a, "to": b, "kind": "type", "label": "imports"})

        # ground the demo in the architecture at the SUBPACKAGE that actually
        # realises each part (only wire to a node that exists in this view)
        def link(src, dst, label):
            if any(n["id"] == dst for n in nodes):
                edges.append({"from": src, "to": dst, "kind": "type", "label": label})

        # anchor one representative transport (they all share the same stack)
        # anchor one representative manipulation episode (they share the stack)
        anchor = next((e.name for e in kb.episodes if e.picks), None)
        if anchor:
            link(anchor, "coraplex.plans", "planned by")             # plan / designator layer
            link(anchor, "giskardpy.motion_statechart", "motion by")  # motion execution
        # every physical thing in the scene is modelled in the semantic digital twin
        link(rob, "semantic_digital_twin", "modelled in")
        for o in kb.objects:
            link(o.name, "semantic_digital_twin", "modelled in")

    # the executed plan tree (captured from the real PlanNode graph)
    sc, _ = load_scene()
    if sc.get("planTrees"):
        n_nodes = sum(_count_plan(t) for t in sc["planTrees"])
        add("plan", "executed plan", "goal",
            ["the plan tree the demo actually executed",
             "%d nodes" % n_nodes, "double-click to open"])
        edges.append({"from": "plan", "to": rob, "kind": "prop", "label": "executed by"})
        for e in kb.episodes:
            edges.append({"from": "plan", "to": e.name, "kind": "type", "label": "spans"})

    status = "EQL ready · %d graph nodes · %d joints · %d CRAM classes" % (
        len(nodes), len(kb.joints), len(kb.classes))
    return {"ok": True, "status": status, "nodes": nodes, "edges": edges,
            "details": details, "presets": get_presets()}


# ---------------------------------------------------- drill-down subgraphs --
# Double-clicking a node in the UI asks for its inside view: package → its
# subpackages + top-level classes, subpackage → its classes (with inheritance
# edges), class → its base classes and every subclass in the repo.
CLASS_CAP = 150


def _view():
    nodes, edges, details = [], [], {}

    def add(nid, label, group, lines, **extra):
        node = {"id": nid, "label": label, "group": group,
                "title": "\n".join([label] + lines)}
        node.update(extra)
        nodes.append(node)
        details[nid] = {"label": label, "group": group, "lines": lines}
    return nodes, edges, details, add


# ------------------------------------------------------- the graph-panel tabs --
# Each tab of the graph panel is one of these views. "knowledge" is the entity
# graph (the default, with drill-down); the others are structural views of the
# same demo that the UI can also overlay with LIVE status from the live_viz
# bridge (see tools/live_viz.py: /plan and /chart).
def view_payload(name):
    kb = get_kb()
    if name == "knowledge":
        return graph_payload()
    if name == "kinematics":
        return _urdf_view(kb)
    if name == "plan":
        return _plan_view(kb)
    if name == "chart":
        return _chart_view(kb)
    return {"ok": False, "error": "unknown view: %s" % name}


def _chart_view(kb):
    """Motion statecharts only exist while giskardpy executes them: one is
    compiled per merged motion group and thrown away afterwards, and nothing of
    it is recorded into the bundle. So this view is live-only — the UI fills it
    from the bridge's /chart while attached."""
    return {"ok": True, "crumb": "motion statechart", "nodes": [], "edges": [],
            "details": {}, "layout": "hier", "live": "chart",
            "empty": "Motion statecharts are built and ticked at execution time. "
                     "Start the demo with tools/live_viz.py and press ◉ Live — "
                     "the statechart of the running motion group appears here, "
                     "coloured by its node life cycle."}


def _class_id(c):
    return c.module + "." + c.name


def _class_lines(c, drill_hint=True):
    lines = ["a PythonClass", "package: " + c.package, "module: " + c.module,
             "methods: %d" % c.methods]
    if c.bases:
        lines.append("bases: " + ", ".join(c.bases))
    if c.doc:
        lines.append(c.doc)
    if drill_hint:
        lines.append("double-click: inheritance view")
    return lines


def _add_classes(add, edges, parent_id, shown, total):
    name_to_id = {}
    for c in shown:
        cid = _class_id(c)
        add(cid, c.name, "pyclass", _class_lines(c))
        edges.append({"from": parent_id, "to": cid, "kind": "prop", "label": "defines"})
        name_to_id.setdefault(c.name, cid)
    # inheritance edges among the classes on screen
    for c in shown:
        for b in c.bases:
            if b in name_to_id and name_to_id[b] != _class_id(c):
                edges.append({"from": _class_id(c), "to": name_to_id[b], "kind": "type", "label": "inherits"})
    if total > len(shown):
        return ["showing the %d largest of %d classes (by method count)" % (len(shown), total)]
    return []


def _count_plan(t):
    return 1 + sum(_count_plan(c) for c in t.get("children", []))


def expand_node(node_id):
    kb = get_kb()
    if node_id == kb.robot.name:                      # robot → full URDF kinematic tree
        return _urdf_view(kb)
    if node_id == "plan":                             # → the executed plan tree
        return _plan_view(kb)
    pkg = next((p for p in kb.packages if p.name == node_id), None)
    if pkg:
        return _package_view(kb, pkg)
    sub = next((s for s in kb.subpackages if s.name == node_id), None)
    if sub:
        return _subpackage_view(kb, sub)
    cls = next((c for c in kb.classes if _class_id(c) == node_id), None)
    if cls:
        return _class_view(kb, cls)
    return None


PLAN_GROUPS = {"ActionNode": "event", "MotionNode": "robot", "ConditionNode": "goal",
               "AttachmentNode": "object", "DetachmentNode": "object"}

PLAN_LEGEND = [
    {"group": "event", "label": "Action"},
    {"group": "robot", "label": "Motion"},
    {"group": "goal", "label": "Condition"},
    {"group": "object", "label": "Attach / detach"},
    {"group": "ind", "label": "Other plan node"},
]


def _plan_view(kb):
    """The executed plan as a tree: one node per PlanNode the demo ran, with
    the designator class, status, arm and target object in the details.

    The recorded statuses are thin on purpose: coraplex performs only the plan
    ROOT (Plan.perform -> root.perform), while ActionNode.notify merely expands
    its children into the merged motion statechart. So every inner node of a
    recorded tree reads CREATED, and real per-step progress only shows up while
    the live bridge is attached (it derives it from the statechart life cycle)."""
    sc, _ = load_scene()
    trees = sc.get("planTrees") or []
    nodes, edges, details, add = _view()
    counter = [0]

    def walk(t, parent):
        nid = "pn%d" % counter[0]
        counter[0] += 1
        status = t.get("status") or "CREATED"
        lines = ["a " + t.get("kind", "PlanNode"), "status: " + status]
        if t.get("arm"):
            lines.append("arm: " + t["arm"])
        if t.get("target"):
            lines.append("target: " + t["target"])
        label = t.get("label", "?").replace("Action", "")
        add(nid, label, PLAN_GROUPS.get(t.get("kind"), "ind"), lines, status=status)
        if parent:
            edges.append({"from": parent, "to": nid, "kind": "prop", "label": "has step"})
        for c in t.get("children", []):
            walk(c, nid)

    for t in trees:
        walk(t, None)
    return {"ok": True, "crumb": "executed plan", "nodes": nodes, "edges": edges,
            "details": details, "legend": PLAN_LEGEND, "layout": "hier",
            "live": "plan", "statusLegend": True,
            "empty": "No plan tree in this bundle — re-run tools/onboard_demo.py."}


def _urdf_view(kb):
    """The scene robot's URDF as a kinematic tree: every link a node, every
    joint an edge (parent → child). Movable joints are solid edges, fixed ones
    dashed; links are coloured by robot part (from the recorded annotation)."""
    links, joints = load_urdf()
    nodes, edges, details, add = _view()
    if not links:
        return {"ok": True, "crumb": kb.robot.name + " · URDF (not found)", "nodes": [], "edges": [], "details": {}}

    # link -> part from the scene's recorded robot annotation
    sc, _ = load_scene()
    parts = (sc.get("robot") or {}).get("parts") or {}
    link_part = {}
    for p, ls in parts.items():
        for l in ls:
            link_part[l] = p

    def chain_group(name):
        p = link_part.get(name, "")
        pl = p.lower()
        if "gripper" in pl or "hand" in pl or "effector" in pl:
            return "object"                            # grippers (teal)
        if "left" in pl:
            return "robot"                             # left arm (pink)
        if "right" in pl:
            return "event"                             # right arm (purple)
        n = name.lower()
        if "head" in n or "stereo" in n or "sensor" in n or "kinect" in n or "camera" in n or "laser" in n:
            return "goal"                              # head / sensors (amber)
        return "concept"                               # base, torso, casters (green)

    # which joint drives each link (child link → its parent joint), for tooltips
    parent_joint = {j["child"]: j for j in joints}
    for ln in links:
        pj = parent_joint.get(ln)
        lines = ["a URDF Link"]
        if pj:
            lines.append("joint: %s (%s)" % (pj["name"], pj["type"]))
            lines.append("parent link: " + pj["parent"])
        else:
            lines.append("root link")
        add("urdf:" + ln, ln, chain_group(ln), lines)
    for j in joints:
        if ("urdf:" + j["parent"]) in details and ("urdf:" + j["child"]) in details:
            movable = j["type"] not in ("fixed",)
            edges.append({"from": "urdf:" + j["parent"], "to": "urdf:" + j["child"],
                          "kind": "prop" if movable else "type",
                          "label": "%s (%s)" % (j["name"], j["type"])})
    revolute = sum(1 for j in joints if j["type"] == "revolute")
    details["urdf:" + links[0]]["lines"].append(
        "%d links · %d joints (%d movable)" % (len(links), len(joints), revolute))
    legend = [
        {"group": "concept", "label": "Base / torso"},
        {"group": "robot", "label": "Left arm"},
        {"group": "event", "label": "Right arm"},
        {"group": "object", "label": "Grippers"},
        {"group": "goal", "label": "Head / sensors"},
    ]
    # force-directed, not hierarchical: the chains read better when the arms and
    # the sensor head spread out around the base than as one wide LR tree
    return {"ok": True, "crumb": kb.robot.name + " · URDF", "nodes": nodes, "edges": edges,
            "details": details, "legend": legend}


def _package_view(kb, pkg):
    nodes, edges, details, add = _view()
    subs = [s for s in kb.subpackages if s.package == pkg.name]
    top = sorted((c for c in kb.classes if c.package == pkg.name and c.subpackage == pkg.name),
                 key=lambda c: -c.methods)
    shown = top[:CLASS_CAP]
    note = []
    add(pkg.name, pkg.name, "concept",
        ["a Package", pkg.description,
         "%d modules · %d classes" % (pkg.module_count, pkg.class_count)] + note)
    for s in subs:
        add(s.name, s.name.split(".", 1)[1], "klass",
            ["a SubPackage of " + s.package,
             "%d modules · %d classes" % (s.module_count, s.class_count),
             "double-click to open"])
        edges.append({"from": pkg.name, "to": s.name, "kind": "prop", "label": "contains"})
    note = _add_classes(add, edges, pkg.name, shown, len(top))
    if note:
        details[pkg.name]["lines"] += note
    return {"ok": True, "crumb": pkg.name, "nodes": nodes, "edges": edges, "details": details}


def _subpackage_view(kb, sub):
    nodes, edges, details, add = _view()
    cls = sorted((c for c in kb.classes if c.subpackage == sub.name), key=lambda c: -c.methods)
    shown = cls[:CLASS_CAP]
    add(sub.name, sub.name.split(".", 1)[1], "klass",
        ["a SubPackage of " + sub.package,
         "%d modules · %d classes" % (sub.module_count, sub.class_count)])
    note = _add_classes(add, edges, sub.name, shown, len(cls))
    if note:
        details[sub.name]["lines"] += note
    return {"ok": True, "crumb": sub.name.split(".", 1)[1], "nodes": nodes, "edges": edges, "details": details}


def _class_view(kb, cls):
    nodes, edges, details, add = _view()
    cid = _class_id(cls)
    add(cid, cls.name, "pyclass", _class_lines(cls, drill_hint=False))
    # direct base classes: resolve inside the repo (same package preferred),
    # otherwise show them as external
    for b in cls.bases:
        cands = [c for c in kb.classes if c.name == b]
        pick = next((c for c in cands if c.package == cls.package), cands[0] if cands else None)
        if pick:
            bid = _class_id(pick)
            if bid not in details:
                add(bid, pick.name, "pyclass", _class_lines(pick))
        else:
            bid = "ext:" + b
            if bid not in details:
                add(bid, b, "upper", ["external base class (outside the repo)"])
        edges.append({"from": cid, "to": bid, "kind": "type", "label": "inherits"})
    # every subclass in the repo (matched by base name)
    subs = [c for c in kb.classes if cls.name in c.bases and _class_id(c) != cid]
    for c in subs[:80]:
        scid = _class_id(c)
        if scid not in details:
            add(scid, c.name, "pyclass", _class_lines(c))
        edges.append({"from": scid, "to": cid, "kind": "type", "label": "inherits"})
    if len(subs) > 80:
        details[cid]["lines"].append("showing 80 of %d subclasses" % len(subs))
    return {"ok": True, "crumb": cls.name, "nodes": nodes, "edges": edges, "details": details}


ARCH_PRESETS = [
    {"text": "CRAM packages by size",
     "code": "set_of(pkg.name, pkg.class_count).ordered_by(pkg.class_count, descending=True)"},
    {"text": "all Designator classes",
     "code": "an(entity(cls).where(cls.name.endswith('Designator')))"},
    {"text": "where does EQL live?",
     "code": "set_of(cls.name, cls.module).where(in_('entity_query_language', cls.module)).limit(15)"},
    {"text": "subclasses of Symbol",
     "code": "an(entity(cls).where(in_('Symbol', cls.bases)))"},
    {"text": "inside coraplex",
     "code": "an(entity(sub).where(sub.package == 'coraplex'))"},
]


def get_presets():
    """Scene presets are generated from the loaded scene, so they stay valid
    for any onboarded robot/environment; the architecture presets are static."""
    kb = get_kb()
    p = [
        {"text": "which robot is this?", "code": "the(entity(rob))"},
        {"text": "which arms does it have?", "code": "an(entity(arm))"},
        {"text": "each arm and its gripper", "code": "set_of(arm.side, arm.gripper)"},
        {"text": "what is in the scene?", "code": "an(entity(obj))"},
        {"text": "what gets moved?", "code": "an(entity(ep.picks).where(ep.picks != None))"},
    ]
    first_obj = next((o for o in kb.objects if o.kind == "object"), None)
    if first_obj:
        p.append({"text": "the %s" % first_obj.label.lower(),
                  "code": "the(entity(obj).where(obj.name == '%s'))" % first_obj.name})
    manip = next((e for e in kb.episodes if e.picks), None)
    if manip:
        if manip.places_at:
            p.append({"text": "where does it place them?",
                      "code": "the(entity(ep.places_at).where(ep.name == '%s'))" % manip.name})
        if manip.performed_by:
            p.append({"text": "which arm does '%s'?" % manip.name,
                      "code": "the(entity(ep.performed_by).where(ep.name == '%s'))" % manip.name})
    return p + ARCH_PRESETS


if __name__ == "__main__":
    # smoke test: run every preset
    for p in get_presets():
        try:
            r = run_query(p["code"])
            print("OK   %-32s -> %d rows  %s" % (p["text"], r["count"], str(r["rows"][:2])[:150]))
        except Exception as ex:
            print("FAIL %-32s -> %s: %s" % (p["text"], type(ex).__name__, ex))
