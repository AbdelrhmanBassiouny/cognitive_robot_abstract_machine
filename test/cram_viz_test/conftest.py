"""
Fixtures for the cram_viz tests.

``fixture_scene`` builds a tiny but complete scene bundle (scene.json + trajectory.json
+ a minimal URDF) in a tmp directory and points cram_viz at it via the CRAM_VIZ_*
environment variables, so the KB and the server tests run against deterministic data
instead of a real (huge, generated) bundle.
"""

import json
import os

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

ROBOT_URDF = """<robot name="pr2">
  <link name="base_link"/>
  <link name="torso_link"/>
  <link name="l_shoulder_link"/>
  <link name="l_wrist_link"/>
  <link name="l_gripper_link"/>
  <joint name="torso_lift_joint" type="prismatic">
    <parent link="base_link"/><child link="torso_link"/>
  </joint>
  <joint name="l_shoulder_joint" type="revolute">
    <parent link="torso_link"/><child link="l_shoulder_link"/>
  </joint>
  <joint name="l_wrist_flex_joint" type="revolute">
    <parent link="l_shoulder_link"/><child link="l_wrist_link"/>
  </joint>
  <joint name="l_gripper_joint" type="fixed">
    <parent link="l_wrist_link"/><child link="l_gripper_link"/>
  </joint>
</robot>
"""

# a miniature "architecture" so the KB's repo scan is fast and deterministic
ARCH_FILES = {
    "coraplex/src/coraplex/plans/plan.py": 'import krrood\n\n\nclass Plan:\n    """A plan."""\n\n    def perform(self):\n        pass\n',
    "coraplex/README.md": "# coraplex\nthe plan executive\n",
    "krrood/src/krrood/eql.py": 'class Entity:\n    """An entity."""\n',
    "krrood/README.md": "# krrood\nknowledge representation\n",
}


@pytest.fixture()
def fixture_scene(tmp_path, monkeypatch):
    """
    A complete miniature scene bundle + architecture; returns the data dir.
    """
    scenes = tmp_path / "scenes" / "fixture"
    scenes.mkdir(parents=True)
    (scenes / "scene.json").write_text(json.dumps(SCENE))
    (scenes / "trajectory.json").write_text(json.dumps(TRAJECTORY))
    (scenes / "robot.urdf").write_text(ROBOT_URDF)
    (scenes / "milk.stl").write_bytes(b"solid milk\nendsolid milk\n")
    (tmp_path / "scenes" / "index.json").write_text(
        json.dumps({"default": "fixture", "scenes": ["fixture"]})
    )

    arch = tmp_path / "arch"
    for rel, content in ARCH_FILES.items():
        p = arch / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    monkeypatch.setenv("CRAM_VIZ_DATA", str(tmp_path))
    monkeypatch.setenv("CRAM_VIZ_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("CRAM_VIZ_SCENE", "fixture")
    monkeypatch.setenv("CRAM_VIZ_ARCHITECTURE", str(arch))

    # a fresh KB per test: the module caches it, and the env just changed
    try:
        from cram_viz import kb

        kb.reset_kb()
    except ImportError:
        pass
    yield tmp_path
    try:
        from cram_viz import kb

        kb.reset_kb()
    except ImportError:
        pass
