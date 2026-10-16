"""Record the PR2 performing the counter to sink task and dropping the object into the sink.

Usage: record_drop_video.py <out.mp4> <LAYOUT> [noavoid] [always]
Renders only if the episode succeeds, unless ``always`` is given.
"""
import faulthandler
import multiprocessing
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).parent))
from render_counter_to_sink_helpers import MujocoBuilder  # noqa: F401  (installs the render patches)

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode, RoboCasaObjectName
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.mujoco_video_recording import MujocoVideoRecorder, VideoResolution
from semantic_digital_twin.adapters.multi_sim import MujocoCamera
from semantic_digital_twin.callbacks.callback import StateChangeCallback
from semantic_digital_twin.spatial_types.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world_description.connections import Connection6DoF, FixedConnection

faulthandler.dump_traceback_later(2400, exit=True)
output_path = Path(sys.argv[1])
layout = LayoutType[sys.argv[2]] if len(sys.argv) > 2 else LayoutType.LAYOUT001
collision_avoidance = "noavoid" not in sys.argv[3:]
show_collision_geometry = False
resolution = VideoResolution(width=960, height=720)


@dataclass(eq=False)
class PoseRecorder(StateChangeCallback):
    """Keeps the global pose of the given bodies at every state change."""

    bodies: list = field(kw_only=True)
    poses: list = field(kw_only=True, default_factory=list)

    def on_state_change(self, **kwargs):
        world = self._world
        self.poses.append(np.stack([world.compute_forward_kinematics_np(world.root, body) for body in self.bodies]))


drop_states = []


def animated_fall(self, settling_time=2.0, frame_time=1 / 30):
    """The library's fall, but putting the object where it is after every video frame."""
    if not self.target_object_released:
        return
    drop_states.append(len(recorder.poses))
    joint = self.environment.objects[RoboCasaObjectName.TARGET].joints[0]
    self.copy_target_object_pose_into_robocasa()
    simulation = self.environment.sim
    simulation.data.set_joint_qvel(joint, np.zeros(6))
    steps_per_frame = round(frame_time / simulation.model.opt.timestep)
    for _ in range(round(settling_time / frame_time)):
        for _ in range(steps_per_frame):
            simulation.step()
        x, y, z, qw, qx, qy, qz = simulation.data.get_joint_qpos(joint)
        self.target_object.root.parent_connection.origin = HomogeneousTransformationMatrix.from_xyz_quaternion(
            x, y, z, qx, qy, qz, qw, reference_frame=self.task.world.root
        )


CounterToSinkEpisode.let_the_target_object_fall = animated_fall

episode = CounterToSinkEpisode.compose(layout, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
print("task:", episode.task.instruction, "avoidance", collision_avoidance, flush=True)
target_body = episode.target_object.root
sink_point = episode.placement_pose().to_np()[:3, 3]
recorded_bodies = [
    body
    for body in world.get_kinematic_structure_entities_of_branch(robot.root)
    if hasattr(body, "visual") and body.visual.shapes
] + [target_body]
start_world = deepcopy(world)
recorder = PoseRecorder(_world=world, bodies=recorded_bodies)
recorder.on_state_change()

start = time.time()
try:
    outcome = episode.perform(collision_avoidance=collision_avoidance)
except Exception as error:  # a failed plan is still worth watching
    print("plan failed:", type(error).__name__, str(error)[:300], flush=True)
    outcome = episode.outcome()
print(f"plan done in {time.time() - start:.0f}s, outcome {outcome}, succeeded {outcome.succeeded}", flush=True)
recorder.stop()
if not outcome.succeeded and "always" not in sys.argv[3:]:
    sys.exit(0)
poses = np.stack(recorder.poses)
moved = np.r_[True, np.abs(np.diff(poses, axis=0)).reshape(len(poses) - 1, -1).max(axis=1) > 1e-6]
drop_start = drop_states[0] if drop_states else len(poses)
motion = np.flatnonzero(moved[:drop_start])
motion = motion[np.linspace(0, len(motion) - 1, min(840, len(motion))).astype(int)]
clip = np.concatenate([motion, np.arange(drop_start, len(poses)), np.repeat([len(poses) - 1], 30)])
poses = poses[clip]
print("recorded", len(recorder.poses), "states, video", len(clip), "frames, fall", len(recorder.poses) - drop_start, flush=True)
base_start = recorder.poses[0][0][:3, 3]
target_start = recorder.poses[0][-1][:3, 3]
focus = (target_start + sink_point) / 2
away = base_start[:2] - focus[:2]
away = away / max(np.linalg.norm(away), 1e-6)
side = np.array([-away[1], away[0]])
# beyond the sink along the counter, on the far side from where the object stood
along = sink_point[:2] - target_start[:2]
along = along / max(np.linalg.norm(along), 1e-6)
views = {
    "overview": (np.r_[focus[:2] + 1.8 * away + 0.6 * side, 2.2], focus),
    "sink": (np.r_[sink_point[:2] + 1.1 * along + 0.7 * away, sink_point[2] + 0.8], sink_point - np.r_[0.0, 0.0, 0.1]),
}


def look_at(camera_position, focus):
    forward = focus - camera_position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return np.column_stack([right, up, -forward])


print("views", views, flush=True)


def render_video(camera_position, focus, output_path):
    camera_rotation = look_at(camera_position, focus)
    replay = start_world
    names = [body.name for body in recorded_bodies]
    bodies = [replay.get_body_by_name(name) for name in names]
    # the replay has no collision geometry, so rules naming bodies cannot be resolved
    replay.collision_manager.ignore_collision_rules.clear()
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
        if show_collision_geometry:
            if body.name.name in robot_body_names:
                color = Color(1.0, 0.55, 0.1, 0.45)
            elif body.name.name == target_body.name.name:
                color = Color(1.0, 0.9, 0.0, 1.0)
            elif body.name.name in penetrated_names:
                color = Color(0.9, 0.15, 0.15, 0.55)
            else:
                color = Color(0.7, 0.72, 0.75, 1.0)
            for shape in body.collision.shapes:
                shape.color = color
            body.visual.shapes[:] = body.collision.shapes[:]
        body.collision.shapes.clear()

    x, y, z, w = Rotation.from_matrix(camera_rotation).as_quat()
    camera = MujocoCamera(
        name="observer",
        body=replay.root,
        position=camera_position.tolist(),
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
        if index % 60 == 0:
            print(f"frame {index}/{len(poses)} at {time.time() - start:.0f}s", flush=True)
    video = video_recorder.stop()
    video.write(output_path)
    print("wrote", output_path, len(video.frames), "frames", flush=True)


# MuJoCo hangs when it shares a process with a plan that ran, so each video renders in a child
for name, (camera_position, focus) in views.items():
    child = multiprocessing.get_context("fork").Process(
        target=render_video, args=(camera_position, focus, output_path.with_name(f"{output_path.stem}_{name}.mp4"))
    )
    start = time.time()
    child.start()
    child.join(1200)
    if child.is_alive():
        child.kill()
        print("render timed out", flush=True)
    print(f"render {name} exit {child.exitcode} in {time.time() - start:.0f}s", flush=True)
