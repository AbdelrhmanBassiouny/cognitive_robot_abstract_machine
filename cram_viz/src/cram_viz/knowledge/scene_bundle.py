"""
Reading the active scene bundle (scene.json, trajectory.json, the robot URDF).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from typing_extensions import Any, Dict, List, Optional, Tuple

from cram_viz import get_logger, paths

logger = get_logger(__name__)


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

    Scene bundles and the scan cache are generated artifacts that a failed run can leave
    half-written; the viewer degrades instead of refusing to start.
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
