"""
The process-wide knowledge base: the recorded episode's entities, built once.
"""

from __future__ import annotations

from collections import defaultdict

from typing_extensions import Any, Dict, List, Optional, Tuple

from cram_viz.knowledge.architecture_entities import Package, PythonClass, SubPackage
from cram_viz.knowledge.architecture_scan import load_architecture
from cram_viz.knowledge.entities import (
    ActionEpisode,
    Arm,
    ArmSide,
    BenchObject,
    Gripper,
    JointMotion,
    Position,
    Robot,
)
from cram_viz.knowledge.scene_bundle import load_scene


def _side_of_name(name: str) -> Optional[ArmSide]:
    """
    Body side encoded in a part/link name, or None when it names neither.
    """
    lowered = name.lower()
    if "left" in lowered or lowered.startswith("l_"):
        return ArmSide.LEFT
    if "right" in lowered or lowered.startswith("r_"):
        return ArmSide.RIGHT
    return None


class EpisodeKnowledgeBase:
    """
    The recorded episode as EQL-queryable entities.

    Built once from the active scene bundle plus a static scan of the CRAM repository;
    every attribute is a plain list of dataclass instances that EQL variables range
    over.
    """

    def __init__(self) -> None:
        """
        Build every entity list from the active scene bundle and a static scan of the
        CRAM architecture.
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
            The arm matching the segment's recorded side hint, falling back to the first
            arm if the segment picks something but names no side.
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

        def side_of(key: str) -> ArmSide:
            """
            Which arm side a prefixed joint key belongs to, or ``ENVIRONMENT``/``BODY``
            when it isn't part of an arm.
            """
            prefix, _, joint_name = key.partition("/")
            if "/" not in key:
                prefix, joint_name = "", key
            if robot_prefix and prefix != robot_prefix:
                return ArmSide.ENVIRONMENT
            part = link_to_part.get(joint_name.replace("_joint", "_link"))
            if part and _side_of_name(part):
                return _side_of_name(part)
            return _side_of_name(joint_name) or ArmSide.BODY

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


_knowledge_base: Optional[EpisodeKnowledgeBase] = None


def get_knowledge_base() -> EpisodeKnowledgeBase:
    """
    The process-wide knowledge base, built on first use.
    """
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = EpisodeKnowledgeBase()
    return _knowledge_base


def reset_knowledge_base() -> None:
    """
    Drop the cached knowledge base (tests point CRAM_VIZ_SCENES at fixtures).
    """
    global _knowledge_base
    _knowledge_base = None
