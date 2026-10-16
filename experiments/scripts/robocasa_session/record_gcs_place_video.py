"""Record the PR2 performing the counter to sink episode in MuJoCo physics, placing the object
into the basin along the GCS path.

Usage: record_gcs_place_video.py <out.mp4>  (env SEED, COLLISION_AVOIDANCE=0/1)
"""
import os, sys, time, traceback
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from experiments.robocasa_task_execution.placing_into_the_basin import SinkBasin
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

output_path = Path(sys.argv[1])
seed = int(os.environ.get("SEED", "10"))
collision_avoidance = os.environ.get("COLLISION_AVOIDANCE", "0") == "1"
width, height, frame_period = 1280, 720, 1 / 25

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=seed)
world, robot = episode.task.world, episode.robot
basin = SinkBasin.first_of(episode.environment.sink)
print("target", episode.environment.objects["obj"].mjcf_path.split("/")[-2], flush=True)
simulation = episode.start_physical_simulation()
model, data = simulation.simulator._mj_model, simulation.simulator._mj_data
model.vis.global_.offwidth, model.vis.global_.offheight = width, height
model.vis.headlight.ambient[:] = [0.4, 0.4, 0.4]
model.vis.headlight.diffuse[:] = [0.7, 0.7, 0.7]
renderer = mujoco.Renderer(model, height, width)
camera = mujoco.MjvCamera()
base_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, robot.root.name.name)
target_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, episode.target_object.root.name.name)
tool_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, robot.right_arm.end_effector.tool_frame.name.name)
basin_center = basin.floor_center
point_of_view = os.environ.get("POV") == "1"
eye_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "wide_stereo_optical_frame")
print("eye body", eye_id, flush=True)
model.vis.global_.fovy = 60.0
frames, clock = [], {"simulated": 0.0, "last_frame": -1.0}
step_simulation = simulation.step_simulation
wall_start = time.time()


def stepping_and_rendering(duration):
    step_simulation(duration)
    clock["simulated"] += duration.total_seconds()
    if clock["simulated"] - clock["last_frame"] < frame_period:
        return
    clock["last_frame"] = clock["simulated"]
    if point_of_view:
        eye, looking = data.xpos[eye_id], data.xmat[eye_id].reshape(3, 3)[:, 2]
        camera.distance = 0.5
        camera.lookat[:] = eye + looking * camera.distance
        camera.azimuth = float(np.degrees(np.arctan2(looking[1], looking[0])))
        camera.elevation = float(np.degrees(np.arcsin(np.clip(looking[2], -1.0, 1.0))))
        renderer.update_scene(data, camera)
        frames.append(renderer.render())
        return
    tool = data.xpos[tool_id]
    near_the_sink = np.linalg.norm(tool[:2] - basin_center[:2]) < 0.7
    if near_the_sink:
        camera.lookat[:] = [basin_center[0], basin_center[1], basin.rim_height]
        camera.distance, camera.azimuth, camera.elevation = 1.6, 60.0, -35.0
    else:
        focus = (data.xpos[base_id] + data.xpos[target_id]) / 2
        camera.lookat[:] = [focus[0], focus[1], 0.9]
        camera.distance, camera.azimuth, camera.elevation = 3.0, 70.0, -30.0
    renderer.update_scene(data, camera)
    frames.append(renderer.render())
    if len(frames) % 250 == 0:
        print(f"sim {clock['simulated']:.1f}s wall {time.time() - wall_start:.0f}s target {np.round(data.xpos[target_id], 3)}", flush=True)


simulation.step_simulation = stepping_and_rendering
try:
    outcome = episode.perform_in_physics(simulation, collision_avoidance=collision_avoidance)
    print("OUTCOME", outcome, "succeeded", outcome.succeeded, flush=True)
except Exception as failure:
    traceback.print_exc()
    print("FAILED", type(failure).__name__, str(failure)[:400], flush=True)
finally:
    print(f"simulated {clock['simulated']:.1f}s in {time.time() - wall_start:.0f}s wall; target at {np.round(data.xpos[target_id], 3)}", flush=True)
    simulation.stop_simulation()
    if frames:
        imageio.mimwrite(output_path, frames, fps=25, macro_block_size=8)
        print("wrote", output_path, len(frames), "frames", flush=True)
