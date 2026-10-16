
import sys
from copy import deepcopy
from pathlib import Path

import imageio.v3 as imageio
import numpy as np

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.composite.transporting import TransportAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from semantic_digital_twin.adapters.mujoco_video_recording import MujocoVideoRecorder, VideoResolution
from semantic_digital_twin.adapters.multi_sim import MujocoBuilder, MujocoCamera
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world_description.connections import Connection6DoF, FixedConnection

# the PR2 URDF has links whose inertia violates the triangle inequality; let MuJoCo balance them,
# and allow offscreen frames larger than the 640x480 default
original_start_build = MujocoBuilder._start_build
original_end_build = MujocoBuilder._end_build


def start_build_for_rendering(self, file_path):
    original_start_build(self, file_path)
    self.spec.compiler.balanceinertia = True
    self.spec.compiler.usethread = False
    self.spec.visual.global_.offwidth = 1920
    self.spec.visual.global_.offheight = 1440


def end_build_for_rendering(self, file_path):
    original_end_build(self, file_path)
    scene = Path(file_path).read_text()
    Path(file_path).write_text(scene.replace("<compiler ", '<compiler balanceinertia="true" ', 1))


original_build_tendons = MujocoBuilder._build_tendons
converted_texture_directory = Path("/root/work/png_textures")


def build_tendons_then_convert_jpeg_textures(self):
    """MuJoCo reads only PNG textures; give it PNG copies of the JPEG ones some objaverse objects use."""
    from PIL import Image

    original_build_tendons(self)
    converted_texture_directory.mkdir(parents=True, exist_ok=True)
    for texture in self.spec.textures:
        source = Path(texture.file)
        if source.suffix.lower() not in (".jpg", ".jpeg"):
            continue
        converted = converted_texture_directory / (str(abs(hash(str(source)))) + ".png")
        if not converted.exists():
            Image.open(source).convert("RGB").save(converted)
        texture.file = str(converted)


MujocoBuilder._build_tendons = build_tendons_then_convert_jpeg_textures
MujocoBuilder._start_build = start_build_for_rendering
MujocoBuilder._end_build = end_build_for_rendering

resolution = VideoResolution(width=1280, height=960)


def frozen_copy(world):
    """A copy of the world in which every movable connection is frozen where it stands now,
    since the MuJoCo mirror ignores drives and starts every joint at zero."""
    frozen = deepcopy(world)
    # free bodies stay free only on the top level, which is the only place MuJoCo allows free joints
    movable = [
        c
        for c in frozen.connections
        if not isinstance(c, FixedConnection) and not (isinstance(c, Connection6DoF) and c.parent is frozen.root)
    ]
    transforms = [frozen.compute_forward_kinematics(c.parent, c.child) for c in movable]
    with frozen.modify_world():
        for connection, transform in zip(movable, transforms):
            parent, child = connection.parent, connection.child
            frozen.remove_connection(connection)
            frozen.add_connection(FixedConnection(parent=parent, child=child, parent_T_connection_expression=transform))
    # a picture needs no collision geometry, and MuJoCo spends minutes on the convex hulls of some meshes
    for body in frozen.bodies:
        body.collision.shapes.clear()
    return frozen


def render(frozen, cameras, output_directory: Path, prefix: str) -> None:
    """Render one frame per camera of a frozen copy."""
    for name, (position, target, fovy) in cameras.items():
        rotation = MujocoCamera._look_at_rotation(Point3.from_iterable(position), Point3.from_iterable(target))
        quaternion_xyzw = rotation.quaternion.to_np().tolist()
        camera = MujocoCamera(
            name=f"{prefix}_{name}_camera",
            body=frozen.root,
            position=list(map(float, position)),
            quaternion=[quaternion_xyzw[3]] + quaternion_xyzw[:3],
            fovy=fovy,
            resolution=[float(resolution.width), float(resolution.height)],
        )
        frozen.root.add_simulator_property(camera)
        recorder = MujocoVideoRecorder(world=frozen, camera=camera, resolution=resolution)
        recorder.start()
        video = recorder.stop()
        path = output_directory / f"{prefix}_{name}.png"
        imageio.imwrite(path, video.frames[-1])
        print("wrote", path)


