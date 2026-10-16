"""Record a video from the PR2's head camera while it performs RoboCasa's counter to sink task.

The plan runs without MuJoCo; a callback records the global pose of every robot body and of the
target object on each world state change. A forked child then builds one MuJoCo scene in which
those bodies hang freely from the root, replays the recorded poses and renders from the head camera.
"""
import faulthandler
import multiprocessing
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).parent))
from render_counter_to_sink_helpers import MujocoBuilder  # noqa: F401  (installs the render patches)

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.mujoco_video_recording import MujocoVideoRecorder, VideoResolution
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.callbacks.callback import StateChangeCallback
from semantic_digital_twin.world_description.connections import Connection6DoF, FixedConnection

faulthandler.dump_traceback_later(1500, exit=True)
output_path = Path(sys.argv[1])
layout = LayoutType[sys.argv[2]] if len(sys.argv) > 2 else LayoutType.LAYOUT001
frame_limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
target_frame_count = 900
resolution = VideoResolution(width=960, height=720)
camera_frame_name = "wide_stereo_optical_frame"


@dataclass(eq=False)
class PoseRecorder(StateChangeCallback):
    """Keeps the global pose of the given bodies at every state change."""

    bodies: list = field(kw_only=True)
    poses: list = field(kw_only=True, default_factory=list)

    def on_state_change(self, **kwargs):
        world = self._world
        self.poses.append(np.stack([world.compute_forward_kinematics_np(world.root, body) for body in self.bodies]))


episode = CounterToSinkEpisode.compose(layout, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
print("task:", episode.task.instruction, flush=True)
target_body = episode.target_object.root
print("target", target_body.name, type(target_body.parent_connection).__name__, target_body.parent_connection.parent.name, flush=True)
# only bodies that show something; links without geometry also lack the mass MuJoCo needs for a free joint
recorded_bodies = [
    body
    for body in world.get_kinematic_structure_entities_of_branch(robot.root)
    if hasattr(body, "visual") and body.visual.shapes
] + [target_body]
camera_body = world.get_body_by_name(camera_frame_name)
camera_parent = camera_body
while camera_parent not in recorded_bodies:
    camera_parent = camera_parent.parent_connection.parent
print("camera attached to", camera_parent.name, flush=True)
parent_T_camera_frame = world.compute_forward_kinematics_np(camera_parent, camera_body)
start_world = deepcopy(world)
recorder = PoseRecorder(_world=world, bodies=recorded_bodies)
recorder.on_state_change()

start = time.time()
outcome = episode.perform()
print(f"plan done in {time.time() - start:.0f}s, outcome {outcome}, succeeded {outcome.succeeded}", flush=True)
poses = np.stack(recorder.poses)
recorder.stop()
moved = np.r_[True, np.abs(np.diff(poses, axis=0)).reshape(len(poses) - 1, -1).max(axis=1) > 1e-6]
poses = poses[moved]
print("recorded", len(recorder.poses), "states,", len(poses), "with motion", flush=True)
step = max(1, len(poses) // target_frame_count)
poses = np.concatenate([poses[::step], np.repeat(poses[-1:], 30, axis=0)])
if frame_limit:
    poses = poses[np.linspace(0, len(poses) - 1, frame_limit).astype(int)]


def render_video():
    replay = start_world
    names = [body.name for body in recorded_bodies]
    bodies = [replay.get_body_by_name(name) for name in names]
    with replay.modify_world():
        for body in bodies:
            # a fresh connection without offsets, so the recorded global pose is its state
            replay.remove_connection(body.parent_connection)
            replay.add_connection(Connection6DoF.create_with_dofs(replay, replay.root, body))
    # everything else stays where it stands; MuJoCo would start every other joint at zero
    movable = [
        c
        for c in replay.connections
        if not isinstance(c, (FixedConnection, Connection6DoF))
    ]
    transforms = [replay.compute_forward_kinematics(c.parent, c.child) for c in movable]
    with replay.modify_world():
        for connection, transform in zip(movable, transforms):
            parent, child = connection.parent, connection.child
            replay.remove_connection(connection)
            replay.add_connection(FixedConnection(parent=parent, child=child, parent_T_connection_expression=transform))
    for body in replay.bodies:
        body.collision.shapes.clear()

    # MuJoCo cameras look along -z with y up, an optical frame along +z with y down
    parent_T_camera = parent_T_camera_frame @ np.diag([1.0, -1.0, -1.0, 1.0])
    x, y, z, w = Rotation.from_matrix(parent_T_camera[:3, :3]).as_quat()
    camera = MujocoCamera(
        name="head_camera",
        body=replay.get_body_by_name(camera_parent.name),
        position=parent_T_camera[:3, 3].tolist(),
        quaternion=[w, x, y, z],
        fovy=60.0,
        resolution=[float(resolution.width), float(resolution.height)],
    )
    camera.body.add_simulator_property(camera)
    dofs = [body.parent_connection.passive_dofs for body in bodies]

    def apply(frame_poses):
        for body_dofs, pose in zip(dofs, frame_poses):
            values = np.r_[pose[:3, 3], Rotation.from_matrix(pose[:3, :3]).as_quat()]
            for dof, value in zip(body_dofs, values):
                replay.state[dof.id].position = value

    apply(poses[0])
    replay.notify_state_change()
    video_recorder = MujocoVideoRecorder(world=replay, camera=camera, resolution=resolution)
    start = time.time()
    video_recorder.start()
    print(f"mujoco scene built in {time.time() - start:.0f}s", flush=True)
    for index, frame_poses in enumerate(poses[1:]):
        apply(frame_poses)
        replay.notify_state_change()
        if index % 100 == 0:
            print(f"frame {index}/{len(poses)} at {time.time() - start:.0f}s", flush=True)
    video = video_recorder.stop()
    video.write(output_path)
    print("wrote", output_path, len(video.frames), "frames", flush=True)


# MuJoCo hangs when it shares a process with a plan that ran, so the video renders in a child
child = multiprocessing.get_context("fork").Process(target=render_video)
start = time.time()
child.start()
child.join(1200)
if child.is_alive():
    child.kill()
    print("render timed out", flush=True)
print(f"render exit {child.exitcode} in {time.time() - start:.0f}s", flush=True)
