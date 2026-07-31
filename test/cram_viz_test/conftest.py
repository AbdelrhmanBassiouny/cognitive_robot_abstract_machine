"""
Fixtures for the cram_viz tests.

``fixture_scene`` builds a tiny but complete scene bundle (scene.json + trajectory.json
+ a minimal URDF) in a tmp directory and points cram_viz at it via the CRAM_VIZ_*
environment variables, so the KB and the server tests run against deterministic data
instead of a real (huge, generated) bundle.
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCENE = {
    "name": "fixture",
    "fps": 30,
    "trajectory": "trajectory.json",
    "models": [
        {"name": "pr2", "urdf": "robot.urdf", "prefix": "pr2", "robot": True},
    ],
    "robot": {
        "name": "pr2",
        "prefix": "pr2",
        "parts": {
            "left_arm": ["l_shoulder_link", "l_wrist_link"],
            "left_gripper": ["l_gripper_link"],
        },
    },
    "objects": [
        {
            "id": "milk",
            "key": "milk.stl",
            "mesh": "milk.stl",
            "spawn": [2.37, 2.0, 1.05],
            "color": "#f3f0ea",
        },
    ],
    "segments": [
        {
            "step": "prepare",
            "action": "ParkArmsAction",
            "arm": None,
            "start": 0,
            "end": 1,
        },
        {
            "step": "transport_milk",
            "action": "TransportAction",
            "arm": "left",
            "start": 1,
            "end": 3,
            "picks": "milk",
        },
    ],
    "planTrees": [
        {
            "kind": "SequentialNode",
            "label": "SequentialNode",
            "status": "SUCCEEDED",
            "children": [
                {
                    "kind": "ActionNode",
                    "label": "TransportAction",
                    "status": "CREATED",
                    "arm": "LEFT",
                    "target": "milk.stl",
                    "children": [
                        {
                            "kind": "ConditionNode",
                            "label": "ConditionNode",
                            "status": "CREATED",
                            "children": [],
                        },
                        {
                            "kind": "MotionNode",
                            "label": "MoveTCPMotion",
                            "status": "CREATED",
                            "children": [],
                        },
                    ],
                },
            ],
        },
    ],
    "placeTarget": {
        "pos": [4.9, 3.3],
        "z": 0.72,
        "bounds": {"minX": 4.4, "maxX": 5.5, "minY": 2.7, "maxY": 3.9},
    },
    "dragBounds": {"minX": 0, "maxX": 6, "minY": 0, "maxY": 6},
}

TRAJECTORY = {
    "fps": 30,
    "frames": [
        {"pr2/torso_lift_joint": 0.0, "pr2/l_wrist_flex_joint": -0.1},
        {"pr2/torso_lift_joint": 0.1, "pr2/l_wrist_flex_joint": -0.5},
        {"pr2/torso_lift_joint": 0.3, "pr2/l_wrist_flex_joint": -0.2},
    ],
    "base": [[0, 0, 0, 0, 0, 0, 1]] * 3,
    "objects": [{"milk.stl": [2.37, 2.0, 1.05, 0, 0, 0, 1]}] * 3,
}

#: real files instead of embedded strings, so they stay valid URDF and Python
DATASET_DIR = Path(__file__).parent / "dataset"

#: the scene's robot description
ROBOT_URDF_PATH = DATASET_DIR / "fixture_robot.urdf"

#: a miniature CRAM repository, so the knowledge base's scan is fast and deterministic
ARCHITECTURE_DIR = DATASET_DIR / "architecture"


def reset_knowledge_base_cache() -> None:
    """
    Drop the cached knowledge base so the next build picks up the current environment.

    Does nothing without krrood: :mod:`cram_viz.kb` is then not importable, and the
    tests that need it skip themselves.
    """
    if importlib.util.find_spec("krrood") is None:
        return
    from cram_viz import kb

    kb.reset_kb()


@pytest.fixture()
def fixture_scene(tmp_path, monkeypatch):
    """
    A complete miniature scene bundle + architecture; returns the data dir.
    """
    scenes = tmp_path / "scenes" / "fixture"
    scenes.mkdir(parents=True)
    (scenes / "scene.json").write_text(json.dumps(SCENE))
    (scenes / "trajectory.json").write_text(json.dumps(TRAJECTORY))
    (scenes / "robot.urdf").write_text(ROBOT_URDF_PATH.read_text())
    (scenes / "milk.stl").write_bytes(b"solid milk\nendsolid milk\n")
    (tmp_path / "scenes" / "index.json").write_text(
        json.dumps({"default": "fixture", "scenes": ["fixture"]})
    )

    monkeypatch.setenv("CRAM_VIZ_DATA", str(tmp_path))
    monkeypatch.setenv("CRAM_VIZ_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("CRAM_VIZ_SCENE", "fixture")
    monkeypatch.setenv("CRAM_VIZ_ARCHITECTURE", str(ARCHITECTURE_DIR))

    # a fresh knowledge base per test: it is cached, and the environment just changed
    reset_knowledge_base_cache()
    yield tmp_path
    reset_knowledge_base_cache()
