"""Record a short clip of the PR2 colliding with the kitchen while it performs the counter to sink task.

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
from semantic_digital_twin.semantic_annotations.semantic_annotations import Floor
from semantic_digital_twin.world_description.geometry import Color
from semantic_digital_twin.world_description.connections import Connection6DoF, FixedConnection

faulthandler.dump_traceback_later(1500, exit=True)
output_path = Path(sys.argv[1])
layout = LayoutType[sys.argv[2]] if len(sys.argv) > 2 else LayoutType.LAYOUT001
collision_avoidance = "noavoid" not in sys.argv[3:]
whole_episode = "whole" in sys.argv[3:]
show_collision_geometry = "collision" in sys.argv[3:]
clip_frames = 240
penetration = -0.01
resolution = VideoResolution(width=960, height=720)


@dataclass(eq=False)
class PoseRecorder(StateChangeCallback):
    """Keeps the global pose of the given bodies and the robot's penetrations at every state change."""

    bodies: list = field(kw_only=True)
    robot_bodies: set = field(kw_only=True)
    ignored: set = field(kw_only=True)
    poses: list = field(kw_only=True, default_factory=list)
    penetrations: list = field(kw_only=True, default_factory=list)

    def on_state_change(self, **kwargs):
        world = self._world
        self.poses.append(np.stack([world.compute_forward_kinematics_np(world.root, body) for body in self.bodies]))
        found = []
        for contact in world.collision_manager.compute_collisions().contacts:
            a, b = contact.body_a, contact.body_b
            if contact.distance > penetration or a in self.ignored or b in self.ignored:
                continue
            if (a in self.robot_bodies) == (b in self.robot_bodies):
                continue
            robot_body, other, point = (a, b, contact.root_P_point_on_body_a) if a in self.robot_bodies else (b, a, contact.root_P_point_on_body_b)
            found.append((robot_body.name.name, other.name.name, contact.distance, np.asarray(point)[:3].copy()))
        self.penetrations.append(found)


episode = CounterToSinkEpisode.compose(layout, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
print("task:", episode.task.instruction, flush=True)
target_body = episode.target_object.root
if "top" in sys.argv[3:]:
    from top_grasps import use_top_grasps
    target = episode.target_object
    print("top grasps:", len(use_top_grasps(target)), flush=True)
    type(episode).target_object = property(lambda self, target=target: target)
recorded_bodies = [
    body
    for body in world.get_kinematic_structure_entities_of_branch(robot.root)
    if hasattr(body, "visual") and body.visual.shapes
] + [target_body]
start_world = deepcopy(world)
recorder = PoseRecorder(
    _world=world,
    bodies=recorded_bodies,
    robot_bodies=set(robot.bodies_with_collision),
    ignored={target_body} | {floor.root for floor in world.get_semantic_annotations_by_type(Floor)},
)
recorder.on_state_change()

start = time.time()
try:
    episode.perform(collision_avoidance=collision_avoidance)
except Exception as error:  # a failed plan is still worth watching
    print("plan failed:", type(error).__name__, str(error)[:300], flush=True)
outcome = episode.outcome()
print(f"plan done in {time.time() - start:.0f}s, outcome {outcome}, succeeded {outcome.succeeded}", flush=True)
recorder.stop()
poses = np.stack(recorder.poses)
penetrations = recorder.penetrations
moved = np.r_[True, np.abs(np.diff(poses, axis=0)).reshape(len(poses) - 1, -1).max(axis=1) > 1e-6]
colliding = np.array([bool(p) for p in penetrations])
print("recorded", len(poses), "states,", moved.sum(), "with motion,", colliding.sum(), "colliding", flush=True)
target_start = recorder.poses[0][-1][:3, 3]
base_start = recorder.poses[0][0][:3, 3]
if colliding.any():
    deepest = min(range(len(penetrations)), key=lambda i: min([p[2] for p in penetrations[i]], default=0.0))
    for robot_name, other_name, distance, point in sorted(penetrations[deepest], key=lambda p: p[2])[:5]:
        print(f"deepest state {deepest}: {robot_name} in {other_name} by {-distance:.3f} m at {point}", flush=True)
else:
    print("no collision", flush=True)
    if not whole_episode:
        sys.exit(0)
if whole_episode:
    clip = np.flatnonzero(moved)
    clip = clip[np.linspace(0, len(clip) - 1, min(900, len(clip))).astype(int)]
    clip = np.concatenate([clip, np.repeat(clip[-1:], 30)])
    poses = poses[clip]
    print("whole episode with", len(clip), "frames", flush=True)
    # high behind the start pose, looking at where the object stands
    focus = target_start
    away = base_start[:2] - focus[:2]
    away = away / max(np.linalg.norm(away), 1e-6)
    side = np.array([-away[1], away[0]])
    views = {"left": np.r_[base_start[:2] + 1.0 * away + 0.8 * side, 2.3]}
else:
    # the collision episode containing the deepest state, padded with motion before and after
    first = deepest
    while first > 0 and colliding[first - 1]:
        first -= 1
    last = deepest
    while last < len(poses) - 1 and colliding[last + 1]:
        last += 1
    moved_indices = np.flatnonzero(moved | colliding)
    lo = max(0, np.searchsorted(moved_indices, first) - 120)
    hi = min(len(moved_indices), np.searchsorted(moved_indices, last) + 120)
    clip = moved_indices[lo:hi]
    clip = clip[np.linspace(0, len(clip) - 1, min(clip_frames, len(clip))).astype(int)]
    clip = np.concatenate([clip, np.repeat(clip[-1:], 20)])
    poses = poses[clip]
    print("clip of states", clip[0], "to", clip[-1], "with", len(clip), "frames", flush=True)

    # a camera behind and above the robot, looking at the deepest contact
    focus = sorted(penetrations[deepest], key=lambda p: p[2])[0][3]
    base = recorder.poses[deepest][recorded_bodies.index(robot.root) if robot.root in recorded_bodies else 0][:3, 3]
    away = base[:2] - focus[:2]
    away = away / max(np.linalg.norm(away), 1e-6)
    side = np.array([-away[1], away[0]])
    views = {
    name: np.r_[focus[:2] + 1.5 * sign * side + 0.8 * away, focus[2] + 0.45]
    for name, sign in (("left", 1.0),)
}


def look_at(camera_position):
    forward = focus - camera_position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return np.column_stack([right, up, -forward])


robot_body_names = {body.name.name for body in recorder.robot_bodies}
penetrated_names = {p[1] for found in penetrations for p in found}
print("penetrated", sorted(penetrated_names), flush=True)
print("views", views, "looking at", focus, flush=True)


def render_video(camera_position, output_path):
    camera_rotation = look_at(camera_position)
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
for name, camera_position in views.items():
    child = multiprocessing.get_context("fork").Process(
        target=render_video, args=(camera_position, output_path.with_name(f"{output_path.stem}_{name}.mp4"))
    )
    start = time.time()
    child.start()
    child.join(1200)
    if child.is_alive():
        child.kill()
        print("render timed out", flush=True)
    print(f"render {name} exit {child.exitcode} in {time.time() - start:.0f}s", flush=True)
