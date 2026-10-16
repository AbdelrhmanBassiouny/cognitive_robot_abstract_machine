"""Load a RoboCasa kitchen, spawn the PR2 in front of the main counter and render it from inside the room."""
import math
import sys
from pathlib import Path

import imageio.v3 as imageio
import numpy as np

from experiments.robocasa_kitchen_demo import _largest_counter_top, load_kitchen
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.mujoco_video_recording import MujocoVideoRecorder, VideoResolution
from semantic_digital_twin.adapters.multi_sim import MujocoBuilder, MujocoCamera
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.spatial_types.spatial_types import HomogeneousTransformationMatrix, Point3
from semantic_digital_twin.world_description.connections import FixedConnection

# the PR2 URDF has links whose inertia violates the triangle inequality; let MuJoCo balance them,
# and allow offscreen frames larger than the 640x480 default
original_start_build = MujocoBuilder._start_build
original_end_build = MujocoBuilder._end_build


def start_build_for_rendering(self, file_path):
    original_start_build(self, file_path)
    self.spec.compiler.balanceinertia = True
    self.spec.visual.global_.offwidth = 1920
    self.spec.visual.global_.offheight = 1440


def end_build_for_rendering(self, file_path):
    original_end_build(self, file_path)
    scene = Path(file_path).read_text()
    Path(file_path).write_text(scene.replace("<compiler ", '<compiler balanceinertia="true" ', 1))


MujocoBuilder._start_build = start_build_for_rendering
MujocoBuilder._end_build = end_build_for_rendering

output_directory = Path(sys.argv[1])
output_directory.mkdir(parents=True, exist_ok=True)
layout = LayoutType[sys.argv[2]] if len(sys.argv) > 2 else LayoutType.LAYOUT001
style = StyleType[sys.argv[3]] if len(sys.argv) > 3 else StyleType.STYLE001

world = load_kitchen(layout, style)
print("kitchen bodies", len(world.bodies), "annotations", len(world.semantic_annotations))

counter_boxes = [
    box
    for box in _largest_counter_top(world).as_bounding_box_collection_in_frame(world.root).bounding_boxes
    if box.max_z < 2.0
]
counter_front_y = min(box.min_y for box in counter_boxes)
counter_center_x = (min(box.min_x for box in counter_boxes) + max(box.max_x for box in counter_boxes)) / 2
robot_x, robot_y = counter_center_x, counter_front_y - 0.6

pr2_world = URDFParser.from_file("package://iai_pr2_description/robots/pr2_with_ft2_cableguide.xacro").parse()
with world.modify_world():
    # a fixed connection, because the MuJoCo mirror does not take over the OmniDrive's degrees of freedom
    placement = FixedConnection(
        parent=world.root,
        child=pr2_world.root,
        parent_T_connection_expression=HomogeneousTransformationMatrix.from_xyz_rpy(
            robot_x, robot_y, 0.0, 0.0, 0.0, math.pi / 2
        ),
    )
    world.merge_world(pr2_world, placement)
PR2.from_world(world)
print("with PR2 bodies", len(world.bodies), "robot at", round(robot_x, 2), round(robot_y, 2))

resolution = VideoResolution(width=1280, height=960)


def attach_camera(name: str, position: np.ndarray, target: np.ndarray, fovy: float) -> MujocoCamera:
    rotation = MujocoCamera._look_at_rotation(Point3.from_iterable(position), Point3.from_iterable(target))
    quaternion_xyzw = rotation.quaternion.to_np().tolist()
    camera = MujocoCamera(
        name=name,
        body=world.root,
        position=position.tolist(),
        quaternion=[quaternion_xyzw[3]] + quaternion_xyzw[:3],
        fovy=fovy,
        resolution=[float(resolution.width), float(resolution.height)],
    )
    world.root.add_simulator_property(camera)
    return camera


robot_center = np.array([robot_x, robot_y + 0.2, 0.8])
cameras = {
    "overview.png": attach_camera("kitchen_overview_camera", np.array([5.3, -2.85, 2.7]), np.array([2.3, -0.5, 0.7]), 70.0),
    "pr2_close_up.png": attach_camera("pr2_close_up_camera", robot_center + np.array([1.4, -1.6, 0.9]), robot_center, 60.0),
}
for file_name, camera in cameras.items():
    recorder = MujocoVideoRecorder(world=world, camera=camera, resolution=resolution)
    recorder.start()
    video = recorder.stop()
    print(file_name, "frames", len(video.frames))
    imageio.imwrite(output_directory / file_name, video.frames[-1])
    print("wrote", output_directory / file_name)
