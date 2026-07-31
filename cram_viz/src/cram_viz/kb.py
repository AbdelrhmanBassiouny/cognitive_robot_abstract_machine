"""
The recorded demo scene as an EQL (Entity Query Language) knowledge base.

EQL is krrood's pythonic relational query language. This module models the recorded
coraplex/giskardpy episode — bench objects, robot parts, action episodes, per-joint
motion — as plain dataclasses and exposes:

fresh_namespace()  -> dict for evaluating one EQL query (fresh variables)
run_query(code)    -> execute an EQL query string, return JSON-able result
graph_payload()    -> nodes/edges/details/presets for the UI knowledge graph
view_payload(name) -> one of the graph-panel tabs (knowledge / kinematics /
plan / chart)

krrood is imported lazily: without it the static viewer still works, only the EQL panel
is unavailable. Scene bundles are read from paths.scenes_dir().
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path

from typing_extensions import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
    Tuple,
)

from krrood.entity_query_language import factories as eql_factories

from cram_viz import paths

logger = logging.getLogger(__name__)


@runtime_checkable
class NamesAnEntity(Protocol):
    """
    A query result that carries an entity name the viewer can highlight.
    """

    name: Any


@runtime_checkable
class IsEvaluable(Protocol):
    """
    An EQL expression that still has to be evaluated to yield its solutions.
    """

    def evaluate(self) -> Any:
        """
        Run the query and return its result.
        """


@runtime_checkable
class MapsNamesToValues(Protocol):
    """
    A result row that binds names to values, such as EQL's unification dictionary.
    """

    def items(self) -> Any:
        """
        The name/value pairs of this row.
        """


def scene_name() -> Optional[str]:
    """
    The active scene: ``CRAM_VIZ_SCENE``, else the scenes-index default.
    """
    environment_override = os.environ.get("CRAM_VIZ_SCENE")
    if environment_override:
        return environment_override
    index_path = paths.scenes_dir() / "index.json"
    if not index_path.is_file():
        return None
    index = _read_json(index_path)
    return index.get("default") if isinstance(index, dict) else None


def _read_json(path: Path) -> Any:
    """
    Read a JSON file, treating unreadable or corrupt content as absent.

    Scene bundles and the scan cache are generated artifacts that a failed run can
    leave half-written; the viewer degrades instead of refusing to start.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as error:
        logger.warning("ignoring unreadable %s: %s", path, error)
        return None


def scene_dir() -> Optional[Path]:
    """
    Directory of the active scene bundle, or None without one.
    """
    name = scene_name()
    return paths.scenes_dir() / name if name else None


def load_scene() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    The active scene's (scene.json, trajectory.json), or ``({}, {})``.
    """
    directory = scene_dir()
    if not directory:
        return {}, {}
    scene = _read_json(directory / "scene.json")
    if not isinstance(scene, dict):
        return {}, {}
    trajectory = _read_json(directory / scene.get("trajectory", "trajectory.json"))
    return scene, trajectory if isinstance(trajectory, dict) else {}


def load_urdf() -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Parse the active scene's robot URDF into (links, joints).

    Used by the kinematic-tree view; a regex parse suffices because the bundled URDFs
    are flat.
    """
    scene, _ = load_scene()
    robot_model = next(
        (model for model in scene.get("models", []) if model.get("robot")), None
    )
    directory = scene_dir()
    if not robot_model or not directory:
        return [], []
    urdf_path = directory / robot_model["urdf"]
    if not urdf_path.is_file():
        return [], []
    text = urdf_path.read_text(encoding="utf-8", errors="replace")
    links = re.findall(r'<link\s+name="([^"]+)"', text)
    joints = []
    for joint in re.finditer(
        r'<joint\s+name="([^"]+)"\s+type="([^"]+)">(.*?)</joint>', text, re.S
    ):
        body = joint.group(3)
        parent = re.search(r'<parent\s+link="([^"]+)"', body)
        child = re.search(r'<child\s+link="([^"]+)"', body)
        if parent and child:
            joints.append(
                {
                    "name": joint.group(1),
                    "type": joint.group(2),
                    "parent": parent.group(1),
                    "child": child.group(1),
                }
            )
    return links, joints


# %% the entity model
@dataclass(unsafe_hash=True)
class Position:
    """
    A world position in metres.
    """

    x: float
    """
    World x coordinate.
    """

    y: float
    """
    World y coordinate.
    """

    z: float
    """
    World z coordinate.
    """

    def __repr__(self) -> str:
        return "(%.2f, %.2f, %.2f)" % (self.x, self.y, self.z)


@dataclass(unsafe_hash=True)
class Gripper:
    """
    An end effector of the recorded robot.
    """

    name: str
    """
    Part name from the scene's robot annotation.
    """

    side: str
    """
    Body side the gripper belongs to ('left' / 'right').
    """

    opening_m: Optional[float] = None
    """
    Maximum opening width in metres as recorded by the onboarder, or None when the
    bundle does not report one.
    """


@dataclass(unsafe_hash=True)
class Arm:
    """
    A manipulator of the recorded robot.
    """

    name: str
    """
    Part name from the scene's robot annotation.
    """

    side: str
    """
    Body side of the arm ('left' / 'right').
    """

    robot: str
    """
    Name of the robot this arm belongs to.
    """

    gripper: Gripper
    """
    The end effector mounted on this arm.
    """


@dataclass(unsafe_hash=True)
class Robot:
    """
    The robot that executed the recorded episode.
    """

    name: str
    """
    Robot name from the scene bundle.
    """

    arm_count: int
    """
    Number of annotated arms.
    """


@dataclass(unsafe_hash=True)
class BenchObject:
    """
    A loose object (or named location) in the scene.
    """

    name: str
    """
    Object identifier, e.g. ``milk``.
    """

    kind: str
    """
    ``object`` for graspable things, ``location`` for named areas.
    """

    label: str
    """
    Human-readable display name.
    """

    height_m: Optional[float]
    """
    Object height in metres as recorded by the onboarder, or None when the bundle does
    not report one (the object's shapes carry no measurable size).
    """

    position: Position
    """
    Spawn position recorded at frame 0 of the episode.
    """


@dataclass(unsafe_hash=True)
class ActionEpisode:
    """
    One executed plan segment of the recording.
    """

    name: str
    """
    Segment step name, e.g. ``transport_milk``.
    """

    index: int
    """
    Position of the episode in execution order.
    """

    start_frame: int
    """
    First trajectory frame of the episode.
    """

    end_frame: int
    """
    Frame after the last trajectory frame of the episode.
    """

    duration_s: float
    """
    Episode duration in seconds.
    """

    performed_by: Optional[Arm]
    """
    The arm that performed the manipulation, if any.
    """

    picks: Optional[BenchObject]
    """
    The object the episode picks up, if any.
    """

    places_at: Optional[BenchObject]
    """
    The location the object is placed at, if any.
    """


@dataclass(unsafe_hash=True)
class JointMotion:
    """
    Per-joint motion statistics over the whole recorded trajectory.
    """

    name: str
    """
    Joint name (without the model prefix).
    """

    arm_side: str
    """
    Body side the joint belongs to ('left' / 'right' / 'body' / …).
    """

    min_rad: float
    """
    Smallest recorded joint position (radians or metres).
    """

    max_rad: float
    """
    Largest recorded joint position (radians or metres).
    """

    range_rad: float
    """Travelled range, ``max_rad - min_rad``."""


# %% the CRAM architecture entities
@dataclass(unsafe_hash=True)
class Package:
    """
    A top-level package of the CRAM repository.
    """

    name: str
    """
    Directory name, e.g. ``coraplex``.
    """

    description: str
    """
    One-line description (curated, or the first README line).
    """

    module_count: int
    """
    Number of Python modules in the package.
    """

    class_count: int
    """
    Number of classes defined in the package.
    """


@dataclass(unsafe_hash=True)
class SubPackage:
    """
    A qualified subpackage, e.g. ``coraplex.plans``.
    """

    name: str
    """
    Qualified name, e.g. ``coraplex.plans``.
    """

    package: str
    """
    The top-level package this subpackage belongs to.
    """

    module_count: int
    """
    Number of modules in the subpackage.
    """

    class_count: int
    """
    Number of classes defined in the subpackage.
    """


@dataclass(unsafe_hash=True)
class PythonClass:
    """
    A class found by the static scan of the CRAM repository.
    """

    name: str
    """
    Class name.
    """

    package: str
    """
    Top-level package the class is defined in.
    """

    subpackage: str
    """
    Qualified subpackage (equal to ``package`` for top-level modules).
    """

    module: str
    """
    Repository-relative module path.
    """

    bases: tuple
    """
    Names of the direct base classes.
    """

    methods: int
    """
    Number of methods defined on the class.
    """

    doc: str
    """
    First docstring line, or ``''``.
    """


# %% scan the CRAM architecture
def _cram_root() -> str:
    """
    The CRAM repository the architecture graph is scanned from.
    """
    return str(paths.architecture_root())


def _architecture_cache() -> str:
    """
    Path of the scan cache — always in the writable data directory, because the scenes
    checkout may be read-only.
    """
    return os.path.join(str(paths.data_dir()), "arch_cache.json")


#: how much of a README's first line is kept as a package description
DESCRIPTION_LENGTH_LIMIT = 120

#: bumped whenever the cached scan's shape changes, so old caches are discarded
ARCHITECTURE_CACHE_VERSION = 2

#: directories never descended into during the architecture scan
SKIP_DIRS = {
    "__pycache__",
    "node_modules",
    "doc",
    "docs",
    "resources",
    "build",
    "dist",
    "plugins",
}

#: curated one-line descriptions for the well-known workspace packages
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


def _first_readme_line(directory: str) -> str:
    """
    The first non-empty line of a directory's README, or ``''``.
    """
    for name in ("README.md", "readme.md"):
        readme_path = Path(directory) / name
        if not readme_path.is_file():
            continue
        text = readme_path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                return stripped[:DESCRIPTION_LENGTH_LIMIT]
    return ""


def scan_architecture() -> (
    Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Tuple[str, str]]]
):
    """
    Statically scan the CRAM repository for its architecture graph.

    :return: (packages, classes, import edges between packages). A pure ``ast`` parse —
        nothing is imported.
    """
    packages: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []
    imports: Dict[str, set] = {}
    cram_root = _cram_root()
    if not os.path.isdir(cram_root):
        return packages, classes, []

    package_dirs = {"root": cram_root}
    for entry in sorted(os.listdir(cram_root)):
        directory = os.path.join(cram_root, entry)
        if (
            os.path.isdir(directory)
            and not entry.startswith(".")
            and entry not in SKIP_DIRS
            and "egg-info" not in entry
        ):
            package_dirs[entry] = directory
    package_names = set(package_dirs)

    modules_per_package: Dict[str, int] = {}
    for package, base in package_dirs.items():
        module_count = 0
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [
                name
                for name in dirnames
                if not name.startswith(".") and name not in SKIP_DIRS
            ]
            if package == "root":
                dirnames[:] = []  # root package = top-level scripts only
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                source = Path(path).read_text(encoding="utf-8", errors="replace")
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    # a module the running interpreter cannot parse (a newer syntax,
                    # or a template) contributes nothing to the architecture graph
                    continue
                module_count += 1
                module = os.path.relpath(path, cram_root)[:-3].replace(os.sep, ".")
                _collect_classes_and_imports(
                    tree, package, module, package_names, classes, imports
                )
        modules_per_package[package] = module_count

    class_counts = Counter(entry["package"] for entry in classes)
    for package in package_dirs:
        description = PKG_DESCRIPTIONS.get(package) or _first_readme_line(
            package_dirs[package]
        )
        packages.append(
            dict(
                name=package,
                description=description,
                module_count=modules_per_package.get(package, 0),
                class_count=class_counts.get(package, 0),
            )
        )
    dependency_edges = sorted(
        (source, target) for source, targets in imports.items() for target in targets
    )
    return packages, classes, dependency_edges


def _collect_classes_and_imports(
    tree: ast.Module,
    package: str,
    module: str,
    package_names: set,
    classes: List[Dict[str, Any]],
    imports: Dict[str, set],
) -> None:
    """
    Collect class definitions and cross-package imports from one module.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = tuple(
                (
                    base.id
                    if isinstance(base, ast.Name)
                    else (base.attr if isinstance(base, ast.Attribute) else "?")
                )
                for base in node.bases
            )
            doc = (ast.get_docstring(node) or "").strip().split("\n")[0][:140]
            methods = sum(
                1
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            classes.append(
                dict(
                    name=node.name,
                    package=package,
                    module=module,
                    bases=list(bases),
                    methods=methods,
                    doc=doc,
                )
            )
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif node.level == 0:
                roots = [(node.module or "").split(".")[0]]
            else:
                roots = []
            for root in roots:
                if root in package_names and root != package:
                    imports.setdefault(package, set()).add(root)


def _load_architecture_cache(cram_root: str, require_classes: bool) -> Optional[tuple]:
    """
    The cached scan if it is usable, else None.

    A cache written for another repository root is not trusted (unless no repository
    exists at all, in which case any cache beats nothing).
    """
    cache_path = Path(_architecture_cache())
    if not cache_path.is_file():
        return None
    cached = _read_json(cache_path)
    if not isinstance(cached, dict):
        return None
    if cached.get("version") != ARCHITECTURE_CACHE_VERSION:
        return None
    if os.path.isdir(cram_root) and cached.get("cram_root") != cram_root:
        return None
    if require_classes and not cached.get("classes"):
        return None
    return (
        cached["packages"],
        cached["classes"],
        [tuple(edge) for edge in cached["deps"]],
    )


def load_architecture() -> (
    Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Tuple[str, str]]]
):
    """
    :func:`scan_architecture` behind a JSON disk cache.

    A full scan takes seconds, so results are cached in the data directory, keyed by the
    scanned root; a cache from another root is rescanned.
    """
    cram_root = _cram_root()
    cached = _load_architecture_cache(cram_root, require_classes=False)
    if cached is not None:
        return cached
    if not os.path.isdir(cram_root):
        return [], [], []
    packages, classes, dependency_edges = scan_architecture()
    if not classes:
        # a checkout exists but yielded nothing (empty or partial clone) — fall
        # back to the cache rather than losing the architecture graph
        return _load_architecture_cache(cram_root, require_classes=True) or (
            packages,
            classes,
            dependency_edges,
        )
    cache_path = Path(_architecture_cache())
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    # written via a temporary file: a half-written cache would be read back as a
    # complete one on the next start
    temporary = cache_path.with_suffix(".part")
    temporary.write_text(
        json.dumps(
            {
                "version": ARCHITECTURE_CACHE_VERSION,
                "cram_root": cram_root,
                "packages": packages,
                "classes": classes,
                "deps": dependency_edges,
            }
        ),
        encoding="utf-8",
    )
    temporary.replace(cache_path)
    return packages, classes, dependency_edges


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


def _side_of_name(name: str) -> str:
    """
    Body side encoded in a part/link name: 'left', 'right' or ``''``.
    """
    lowered = name.lower()
    if "left" in lowered or lowered.startswith("l_"):
        return "left"
    if "right" in lowered or lowered.startswith("r_"):
        return "right"
    return ""


class KB:
    """
    The recorded episode as EQL-queryable entities.

    Built once from the active scene bundle plus a static scan of the CRAM repository;
    every attribute is a plain list of dataclass instances that EQL variables range
    over.
    """

    def __init__(self) -> None:
        """
        Build every entity list from the active scene bundle and a static
        scan of the CRAM architecture.
        """
        scene, trajectory = load_scene()
        frames_per_second = scene.get("fps", 30)
        parts = (scene.get("robot") or {}).get("parts") or {}
        robot_name = (scene.get("robot") or {}).get("name", "robot")
        robot_prefix = (scene.get("robot") or {}).get("prefix", "")

        self.objects = self._build_objects(scene)
        objects_by_id = {entity.name: entity for entity in self.objects}
        place_area = objects_by_id.get("place_area")

        self.grippers, self.arms = self._build_arms(parts, robot_name)
        self.robot = Robot(robot_name, arm_count=len(self.arms))
        self.episodes = self._build_episodes(
            scene, frames_per_second, objects_by_id, place_area
        )
        self.joints = self._build_joint_motions(trajectory, parts, robot_prefix)

        packages, classes, dependency_edges = load_architecture()
        self.packages = [Package(**entry) for entry in packages]
        self.classes = [
            PythonClass(
                name=entry["name"],
                package=entry["package"],
                subpackage=self._subpackage_of(entry["package"], entry["module"]),
                module=entry["module"],
                bases=tuple(entry["bases"]),
                methods=entry["methods"],
                doc=entry["doc"],
            )
            for entry in classes
        ]
        self.package_deps = dependency_edges
        self.subpackages = self._build_subpackages(self.classes)

    @staticmethod
    def _build_objects(scene: Dict[str, Any]) -> List[BenchObject]:
        """
        Scene objects (spawn poses recorded at frame 0) plus the place area.
        """
        objects = []
        for entry in scene.get("objects") or []:
            objects.append(
                BenchObject(
                    name=entry["id"],
                    kind="object",
                    label=entry["id"].replace("_", " ").title(),
                    height_m=entry.get("height"),
                    position=Position(
                        *[round(value, 3) for value in entry["spawn"][:3]]
                    ),
                )
            )
        if scene.get("placeTarget"):
            target = scene["placeTarget"]
            objects.append(
                BenchObject(
                    name="place_area",
                    kind="location",
                    label="Place area",
                    height_m=0.0,  # a target area on a surface, not a solid
                    position=Position(
                        round(target["pos"][0], 3),
                        round(target["pos"][1], 3),
                        target.get("z", 0),
                    ),
                )
            )
        return objects

    @staticmethod
    def _build_arms(
        parts: Dict[str, Any], robot_name: str
    ) -> Tuple[List[Gripper], List[Arm]]:
        """
        Arms and grippers from the recorded robot annotation parts.

        Gripper keywords take precedence — robot names can contain 'arm' themselves, so
        'arm' alone must not decide.
        """
        gripper_parts = [
            part
            for part in parts
            if any(
                keyword in part.lower() for keyword in ("gripper", "hand", "effector")
            )
        ]
        arm_parts = [
            part
            for part in parts
            if part not in gripper_parts and "arm" in part.lower()
        ]
        grippers, arms = [], []
        for arm_part in sorted(arm_parts):
            side = _side_of_name(arm_part) or "n/a"
            gripper_part = next(
                (part for part in gripper_parts if _side_of_name(part) == side), None
            )
            gripper = Gripper(gripper_part or (arm_part + "_ee"), side)
            grippers.append(gripper)
            arms.append(Arm(arm_part, side, robot_name, gripper))
        return grippers, arms

    def _build_episodes(
        self,
        scene: Dict[str, Any],
        frames_per_second: int,
        objects_by_id: Dict[str, BenchObject],
        place_area: Optional[BenchObject],
    ) -> List[ActionEpisode]:
        """
        Action episodes from the recorded plan segments.
        """

        def arm_for(segment: Dict[str, Any]) -> Optional[Arm]:
            """
            The arm matching the segment's recorded side hint, falling back to
            the first arm if the segment picks something but names no side.
            """
            hint = (segment.get("arm") or "").lower()
            for arm in self.arms:
                if arm.side and arm.side in hint:
                    return arm
            return self.arms[0] if self.arms and segment.get("picks") else None

        episodes = []
        for index, segment in enumerate(scene.get("segments") or []):
            picks = objects_by_id.get(segment.get("picks"))
            episodes.append(
                ActionEpisode(
                    name=segment["step"],
                    index=index,
                    start_frame=segment["start"],
                    end_frame=segment["end"],
                    duration_s=round(
                        (segment["end"] - segment["start"]) / max(1, frames_per_second),
                        1,
                    ),
                    performed_by=arm_for(segment) if picks else None,
                    picks=picks,
                    places_at=place_area if picks else None,
                )
            )
        return episodes

    @staticmethod
    def _build_joint_motions(
        trajectory: Dict[str, Any], parts: Dict[str, Any], robot_prefix: str
    ) -> List[JointMotion]:
        """
        Per-joint motion statistics over the whole recorded trajectory.
        """
        minimum: Dict[str, float] = {}
        maximum: Dict[str, float] = {}
        for frame in trajectory.get("frames") or []:
            for joint, value in frame.items():
                if joint not in minimum or value < minimum[joint]:
                    minimum[joint] = value
                if joint not in maximum or value > maximum[joint]:
                    maximum[joint] = value

        link_to_part = {link: part for part, links in parts.items() for link in links}

        def side_of(key: str) -> str:
            """
            Which arm side a prefixed joint key belongs to, or "environment"/
            "body" when it isn't part of an arm.
            """
            prefix, _, joint_name = key.partition("/")
            if "/" not in key:
                prefix, joint_name = "", key
            if robot_prefix and prefix != robot_prefix:
                return "environment"
            part = link_to_part.get(joint_name.replace("_joint", "_link"))
            if part and _side_of_name(part):
                return _side_of_name(part)
            return _side_of_name(joint_name) or "body"

        return [
            JointMotion(
                name=key.partition("/")[2] or key,
                arm_side=side_of(key),
                min_rad=round(minimum[key], 3),
                max_rad=round(maximum[key], 3),
                range_rad=round(maximum[key] - minimum[key], 3),
            )
            for key in sorted(minimum)
        ]

    @staticmethod
    def _subpackage_of(package: str, module: str) -> str:
        """
        Qualified subpackage of a module path.

        ``coraplex.src.coraplex.plans.designator`` → ``coraplex.plans``; top-level
        modules collapse onto the package itself.
        """
        segments = module.split(".")
        if segments and segments[0] == package:
            segments = segments[1:]
        while segments and segments[0] in ("src", package):
            segments = segments[1:]
        return package + "." + segments[0] if len(segments) >= 2 else package

    @staticmethod
    def _build_subpackages(classes: List[PythonClass]) -> List[SubPackage]:
        """
        Subpackage entities aggregated from the scanned classes.
        """
        modules = defaultdict(set)
        class_counts = defaultdict(int)
        for entry in classes:
            if entry.subpackage != entry.package:
                modules[(entry.package, entry.subpackage)].add(entry.module)
                class_counts[entry.subpackage] += 1
        return [
            SubPackage(
                name=subpackage,
                package=package,
                module_count=len(modules[(package, subpackage)]),
                class_count=class_counts[subpackage],
            )
            for (package, subpackage) in sorted(modules)
        ]


_kb: Optional[KB] = None


def get_kb() -> KB:
    """
    The process-wide knowledge base, built on first use.
    """
    global _kb
    if _kb is None:
        _kb = KB()
    return _kb


def reset_kb() -> None:
    """
    Drop the cached KB (tests point CRAM_VIZ_SCENES at fixtures).
    """
    global _kb
    _kb = None


# %% EQL session
#: EQL factories re-exported into every query namespace.
#: Imported by name rather than looked up, so a factory that krrood renames or drops
#: breaks the import instead of silently vanishing from the query console.
EQL_FACTORIES = {
    "entity": eql_factories.entity,
    "set_of": eql_factories.set_of,
    "variable": eql_factories.variable,
    "an": eql_factories.an,
    "a": eql_factories.a,
    "the": eql_factories.the,
    "and_": eql_factories.and_,
    "or_": eql_factories.or_,
    "not_": eql_factories.not_,
    "contains": eql_factories.contains,
    "in_": eql_factories.in_,
    "exists": eql_factories.exists,
    "for_all": eql_factories.for_all,
    "count": eql_factories.count,
    "count_all": eql_factories.count_all,
    "average": eql_factories.average,
    "sum": eql_factories.sum,
    "max": eql_factories.max,
    "min": eql_factories.min,
    "mode": eql_factories.mode,
    "distinct": eql_factories.distinct,
    "flat_variable": eql_factories.flat_variable,
    "variable_from": eql_factories.variable_from,
}


def fresh_namespace() -> Dict[str, Any]:
    """
    A namespace for evaluating one EQL query (fresh variables each time).
    """
    kb = get_kb()
    namespace: Dict[str, Any] = dict(EQL_FACTORIES)
    namespace.update(
        Position=Position,
        Gripper=Gripper,
        Arm=Arm,
        Robot=Robot,
        BenchObject=BenchObject,
        ActionEpisode=ActionEpisode,
        JointMotion=JointMotion,
        Package=Package,
        SubPackage=SubPackage,
        PythonClass=PythonClass,
        objects=kb.objects,
        episodes=kb.episodes,
        arms=kb.arms,
        grippers=kb.grippers,
        joints=kb.joints,
        robots=[kb.robot],
        packages=kb.packages,
        subpackages=kb.subpackages,
        classes=kb.classes,
    )
    # ready-made query variables so one-liners stay short
    namespace["obj"] = eql_factories.variable(BenchObject, domain=kb.objects)
    namespace["ep"] = eql_factories.variable(ActionEpisode, domain=kb.episodes)
    namespace["arm"] = eql_factories.variable(Arm, domain=kb.arms)
    namespace["j"] = eql_factories.variable(JointMotion, domain=kb.joints)
    namespace["rob"] = eql_factories.variable(Robot, domain=[kb.robot])
    namespace["pkg"] = eql_factories.variable(Package, domain=kb.packages)
    namespace["sub"] = eql_factories.variable(SubPackage, domain=kb.subpackages)
    namespace["cls"] = eql_factories.variable(PythonClass, domain=kb.classes)
    return namespace


def _entity_name(value: Any) -> Optional[str]:
    """
    The entity's name attribute, or None for non-entities.
    """
    return str(value.name) if isinstance(value, NamesAnEntity) else None


def _jsonable(value: Any) -> Any:
    """
    A JSON-serializable rendering of one query result value.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return _entity_name(value) or repr(value)
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return repr(value)


def run_query(code: str, limit: int = 200) -> Dict[str, Any]:
    """
    Execute an EQL query string and return a JSON-able result payload.

    The last expression of ``code`` is the query; preceding statements are executed as
    setup.

    :param code: The EQL query source.
    :param limit: Maximum number of result rows to return.
    """
    namespace = fresh_namespace()
    tree = ast.parse(code, mode="exec")
    if not tree.body:
        raise ValueError("empty query")
    last = tree.body[-1]
    if isinstance(last, ast.Expr):
        if len(tree.body) > 1:
            preamble = ast.Module(body=tree.body[:-1], type_ignores=[])
            exec(compile(preamble, "<eql>", "exec"), namespace)
        result = eval(compile(ast.Expression(last.value), "<eql>", "eval"), namespace)
    else:
        exec(compile(tree, "<eql>", "exec"), namespace)
        result = namespace.get("result")

    if isinstance(result, IsEvaluable):
        result = result.evaluate()
    rows, highlight, more = _result_rows(result, limit)
    kind = "rows" if rows and "__entity__" not in rows[0] else "entities"
    return {
        "ok": True,
        "kind": kind,
        "rows": rows,
        "count": len(rows),
        "more": more,
        "highlight": sorted(set(highlight)),
    }


def _result_rows(
    result: Any, limit: int
) -> Tuple[List[Dict[str, Any]], List[str], bool]:
    """
    Render a query result into (answer rows, highlight ids, truncated).
    """
    rows: List[Dict[str, Any]] = []
    highlight: List[str] = []
    if result is None:
        return rows, highlight, False
    if isinstance(result, (str, int, float, bool)):
        rows.append({"value": _jsonable(result)})
        return rows, highlight, False
    if is_dataclass(result) and not isinstance(result, type):
        rows.append(_entity_row(result, highlight))
        return rows, highlight, False
    try:
        iterator = iter(result)
    except TypeError:
        rows.append({"value": _jsonable(result)})
        return rows, highlight, False
    for item in iterator:
        if len(rows) >= limit:
            return rows, highlight, True
        rows.append(_item_row(item, highlight))
    return rows, highlight, False


def _entity_row(item: Any, highlight: List[str]) -> Dict[str, Any]:
    """
    One entity as an answer row; collects the ids to highlight.
    """
    name = _entity_name(item)
    if name:
        highlight.append(name)
    if isinstance(item, PythonClass):
        # classes aren't graph nodes — light up their subpackage + package instead
        highlight.append(item.subpackage)
        highlight.append(item.package)
    row = {"__entity__": name or repr(item), "__type__": type(item).__name__}
    for entity_field in fields(item):
        if entity_field.name != "name":
            row[entity_field.name] = _jsonable(vars(item)[entity_field.name])
    return row


def _item_row(item: Any, highlight: List[str]) -> Dict[str, Any]:
    """
    One arbitrary query result item as an answer row.
    """
    if is_dataclass(item) and not isinstance(item, type):
        return _entity_row(item, highlight)
    if isinstance(item, MapsNamesToValues):  # a unification row from set_of()
        row = {}
        for key, value in item.items():
            if (
                is_dataclass(value)
                and not isinstance(value, type)
                and _entity_name(value)
            ):
                highlight.append(_entity_name(value))
            row[str(key)] = _jsonable(value)
        return row
    return {"value": _jsonable(item)}


# %% the UI graph
def graph_payload() -> Dict[str, Any]:
    """
    The knowledge-graph overview: nodes, edges, details and presets.
    """
    kb = get_kb()
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
        def link(src: str, dst: str, label: str) -> None:
            """
            Add an edge, but only if dst is actually a node in this view.
            """
            if any(n["id"] == dst for n in nodes):
                edges.append({"from": src, "to": dst, "kind": "type", "label": label})

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

#: at most this many classes are drawn in one drill-down view
CLASS_CAP = 150


def _view() -> tuple:
    """
    Fresh (nodes, edges, details, add) accumulators for one subgraph.
    """
    nodes, edges, details = [], [], {}

    def add(
        node_id: str, label: str, group: str, lines: List[str], **extra: Any
    ) -> None:
        """
        Append one graph node (plus arbitrary extra fields) and its detail entry.
        """
        node = {
            "id": node_id,
            "label": label,
            "group": group,
            "title": "\n".join([label] + lines),
        }
        node.update(extra)
        nodes.append(node)
        details[node_id] = {"label": label, "group": group, "lines": lines}

    return nodes, edges, details, add


# %% the graph-panel tabs
def view_payload(name: str) -> Dict[str, Any]:
    """
    One tab of the graph panel.

    ``knowledge`` is the entity graph (the default, with drill-down); the others are
    structural views of the same demo that the UI can overlay with live status from the
    bridge (see :mod:`cram_viz.live.http`, ``/plan`` and ``/chart``).
    """
    kb = get_kb()
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


def _class_id(python_class: PythonClass) -> str:
    """
    Graph node id of a scanned class (module-qualified).
    """
    return python_class.module + "." + python_class.name


def _class_lines(python_class: PythonClass, drill_hint: bool = True) -> List[str]:
    """
    Detail lines shown for a class node.
    """
    lines = [
        "a PythonClass",
        "package: " + python_class.package,
        "module: " + python_class.module,
        "methods: %d" % python_class.methods,
    ]
    if python_class.bases:
        lines.append("bases: " + ", ".join(python_class.bases))
    if python_class.doc:
        lines.append(python_class.doc)
    if drill_hint:
        lines.append("double-click: inheritance view")
    return lines


def _add_classes(
    add: Any,
    edges: List[Dict[str, Any]],
    parent_id: str,
    shown: List[PythonClass],
    total: int,
) -> List[str]:
    """
    Add class nodes plus their on-screen inheritance edges to a view.

    :return: Extra detail lines for the parent (a truncation notice, if any).
    """
    name_to_id: Dict[str, str] = {}
    for python_class in shown:
        class_id = _class_id(python_class)
        add(class_id, python_class.name, "pyclass", _class_lines(python_class))
        edges.append(
            {"from": parent_id, "to": class_id, "kind": "prop", "label": "defines"}
        )
        name_to_id.setdefault(python_class.name, class_id)
    for python_class in shown:
        for base in python_class.bases:
            if base in name_to_id and name_to_id[base] != _class_id(python_class):
                edges.append(
                    {
                        "from": _class_id(python_class),
                        "to": name_to_id[base],
                        "kind": "type",
                        "label": "inherits",
                    }
                )
    if total > len(shown):
        return [
            "showing the %d largest of %d classes (by method count)"
            % (len(shown), total)
        ]
    return []


def _count_plan_nodes(tree: Dict[str, Any]) -> int:
    """
    Number of nodes in a serialized plan tree.
    """
    return 1 + sum(_count_plan_nodes(child) for child in tree.get("children", []))


def expand_node(node_id: str) -> Optional[Dict[str, Any]]:
    """
    The inside view of a double-clicked node, or None if not drillable.
    """
    kb = get_kb()
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


#: plan-node kind → node colour group of the graph panel
PLAN_GROUPS = {
    "ActionNode": "event",
    "MotionNode": "robot",
    "ConditionNode": "goal",
    "AttachmentNode": "object",
    "DetachmentNode": "object",
}

#: legend rows of the plan view
PLAN_LEGEND = [
    {"group": "event", "label": "Action"},
    {"group": "robot", "label": "Motion"},
    {"group": "goal", "label": "Condition"},
    {"group": "object", "label": "Attach / detach"},
    {"group": "ind", "label": "Other plan node"},
]


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
            PLAN_GROUPS.get(tree.get("kind"), "ind"),
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
        "legend": PLAN_LEGEND,
        "layout": "hier",
        "live": "plan",
        "statusLegend": True,
        "empty": "No plan tree in this bundle — re-run cram-viz-onboard.",
    }


#: the one URDF joint type that cannot move
FIXED_JOINT_TYPE = "fixed"


def _is_movable(joint: Dict[str, str]) -> bool:
    """
    Whether a URDF joint can move (every type except ``fixed``).
    """
    return joint["type"] != FIXED_JOINT_TYPE


def _urdf_view(kb: KB) -> Dict[str, Any]:
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
            "crumb": kb.robot.name + " · URDF (not found)",
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
        "crumb": kb.robot.name + " · URDF",
        "nodes": nodes,
        "edges": edges,
        "details": details,
        "legend": legend,
    }


def _package_view(kb: KB, package: Package) -> Dict[str, Any]:
    """
    Inside view of a package: its subpackages and top-level classes.
    """
    nodes, edges, details, add = _view()
    subpackages = [entry for entry in kb.subpackages if entry.package == package.name]
    top_level = sorted(
        (
            entry
            for entry in kb.classes
            if entry.package == package.name and entry.subpackage == package.name
        ),
        key=lambda entry: -entry.methods,
    )
    add(
        package.name,
        package.name,
        "concept",
        [
            "a Package",
            package.description,
            "%d modules · %d classes" % (package.module_count, package.class_count),
        ],
    )
    for subpackage in subpackages:
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
                "from": package.name,
                "to": subpackage.name,
                "kind": "prop",
                "label": "contains",
            }
        )
    note = _add_classes(add, edges, package.name, top_level[:CLASS_CAP], len(top_level))
    if note:
        details[package.name]["lines"] += note
    return {
        "ok": True,
        "crumb": package.name,
        "nodes": nodes,
        "edges": edges,
        "details": details,
    }


def _subpackage_view(kb: KB, subpackage: SubPackage) -> Dict[str, Any]:
    """
    Inside view of a subpackage: its classes with inheritance edges.
    """
    nodes, edges, details, add = _view()
    classes = sorted(
        (entry for entry in kb.classes if entry.subpackage == subpackage.name),
        key=lambda entry: -entry.methods,
    )
    add(
        subpackage.name,
        subpackage.name.split(".", 1)[1],
        "klass",
        [
            "a SubPackage of " + subpackage.package,
            "%d modules · %d classes"
            % (subpackage.module_count, subpackage.class_count),
        ],
    )
    note = _add_classes(add, edges, subpackage.name, classes[:CLASS_CAP], len(classes))
    if note:
        details[subpackage.name]["lines"] += note
    return {
        "ok": True,
        "crumb": subpackage.name.split(".", 1)[1],
        "nodes": nodes,
        "edges": edges,
        "details": details,
    }


#: at most this many subclasses are drawn in a class inheritance view
SUBCLASS_CAP = 80


def _class_view(kb: KB, python_class: PythonClass) -> Dict[str, Any]:
    """
    Inheritance view of one class: bases above, repo subclasses below.
    """
    nodes, edges, details, add = _view()
    class_id = _class_id(python_class)
    add(
        class_id,
        python_class.name,
        "pyclass",
        _class_lines(python_class, drill_hint=False),
    )
    # direct base classes: resolve inside the repo (same package preferred),
    # otherwise show them as external
    for base in python_class.bases:
        candidates = [entry for entry in kb.classes if entry.name == base]
        pick = next(
            (entry for entry in candidates if entry.package == python_class.package),
            candidates[0] if candidates else None,
        )
        if pick:
            base_id = _class_id(pick)
            if base_id not in details:
                add(base_id, pick.name, "pyclass", _class_lines(pick))
        else:
            base_id = "ext:" + base
            if base_id not in details:
                add(base_id, base, "upper", ["external base class (outside the repo)"])
        edges.append(
            {"from": class_id, "to": base_id, "kind": "type", "label": "inherits"}
        )
    # every subclass in the repo (matched by base name)
    subclasses = [
        entry
        for entry in kb.classes
        if python_class.name in entry.bases and _class_id(entry) != class_id
    ]
    for subclass in subclasses[:SUBCLASS_CAP]:
        subclass_id = _class_id(subclass)
        if subclass_id not in details:
            add(subclass_id, subclass.name, "pyclass", _class_lines(subclass))
        edges.append(
            {"from": subclass_id, "to": class_id, "kind": "type", "label": "inherits"}
        )
    if len(subclasses) > SUBCLASS_CAP:
        details[class_id]["lines"].append(
            "showing %d of %d subclasses" % (SUBCLASS_CAP, len(subclasses))
        )
    return {
        "ok": True,
        "crumb": python_class.name,
        "nodes": nodes,
        "edges": edges,
        "details": details,
    }


#: static presets for the architecture side of the graph
ARCH_PRESETS = [
    {
        "text": "CRAM packages by size",
        "code": "set_of(pkg.name, pkg.class_count).ordered_by(pkg.class_count, descending=True)",
    },
    {
        "text": "all Designator classes",
        "code": "an(entity(cls).where(cls.name.endswith('Designator')))",
    },
    {
        "text": "where does EQL live?",
        "code": "set_of(cls.name, cls.module).where(in_('entity_query_language', cls.module)).limit(15)",
    },
    {
        "text": "subclasses of Symbol",
        "code": "an(entity(cls).where(in_('Symbol', cls.bases)))",
    },
    {
        "text": "inside coraplex",
        "code": "an(entity(sub).where(sub.package == 'coraplex'))",
    },
]


def get_presets() -> List[Dict[str, str]]:
    """
    Ready-made queries for the EQL panel.

    Scene presets are generated from the loaded scene, so they stay valid for any
    onboarded robot/environment; the architecture presets are static.
    """
    kb = get_kb()
    presets = [
        {"text": "which robot is this?", "code": "the(entity(rob))"},
        {"text": "which arms does it have?", "code": "an(entity(arm))"},
        {"text": "each arm and its gripper", "code": "set_of(arm.side, arm.gripper)"},
        {"text": "what is in the scene?", "code": "an(entity(obj))"},
        {
            "text": "what gets moved?",
            "code": "an(entity(ep.picks).where(ep.picks != None))",
        },
    ]
    first_object = next((entry for entry in kb.objects if entry.kind == "object"), None)
    if first_object:
        presets.append(
            {
                "text": "the %s" % first_object.label.lower(),
                "code": "the(entity(obj).where(obj.name == '%s'))" % first_object.name,
            }
        )
    manipulation = next((episode for episode in kb.episodes if episode.picks), None)
    if manipulation:
        if manipulation.places_at:
            presets.append(
                {
                    "text": "where does it place them?",
                    "code": "the(entity(ep.places_at).where(ep.name == '%s'))"
                    % manipulation.name,
                }
            )
        if manipulation.performed_by:
            presets.append(
                {
                    "text": "which arm does '%s'?" % manipulation.name,
                    "code": "the(entity(ep.performed_by).where(ep.name == '%s'))"
                    % manipulation.name,
                }
            )
    return presets + ARCH_PRESETS


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
