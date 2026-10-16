"""Have the PR2 perform the counter to sink task in MuJoCo physics, its base driven by the drive servos.

Usage: probe_physics_task.py <out.mp4> [LAYOUT] [noavoid]
"""
import faulthandler, logging, os, sys, time
from datetime import timedelta
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np

faulthandler.dump_traceback_later(3000, exit=True)
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import PhysicallySimulatedRobot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.composite.transporting import TransportAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from semantic_digital_twin.datastructures.definitions import TorsoState

logging.basicConfig(level=logging.WARNING)
output_path = Path(sys.argv[1])
layout = LayoutType[sys.argv[2]] if len(sys.argv) > 2 else LayoutType.LAYOUT001
collision_avoidance = "noavoid" not in sys.argv[3:]
width, height, render_period = 960, 720, 1 / 25

episode = CounterToSinkEpisode.compose(layout, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
target = episode.target_object.root
placement = episode.placement_pose()
print("task:", episode.task.instruction, "| avoidance", collision_avoidance, flush=True)
print("placement", np.round(placement.to_np()[:3, 3], 3), flush=True)

step_size = float(os.environ.get("STEP_SIZE", "0.001"))
integrator = getattr(mujoco.mjtIntegrator, os.environ.get("INTEGRATOR", "mjINT_RK4"))
print("step size", step_size, "integrator", integrator, flush=True)
contact_options = {}
if os.environ.get("CONE") == "elliptic":
    contact_options["cone"] = mujoco.mjtCone.mjCONE_ELLIPTIC
if "IMPRATIO" in os.environ:
    contact_options["impratio"] = float(os.environ["IMPRATIO"])
if os.environ.get("MULTICCD") == "1":
    contact_options["multiccd"] = True
if "NOSLIP" in os.environ:
    contact_options["noslip_iterations"] = int(os.environ["NOSLIP"])
print("contact options", contact_options, flush=True)
simulation = MujocoSim(world=world, headless=True, step_size=step_size, integrator=integrator, **contact_options)
compiled = simulation.simulator._mj_model
gripper_body_names = {b.name.name for arm in robot.all_arms for b in world.get_kinematic_structure_entities_of_branch(arm.end_effector.root)}
gripper_geoms = [g for g in range(compiled.ngeom) if mujoco.mj_id2name(compiled, mujoco.mjtObj.mjOBJ_BODY, compiled.geom_bodyid[g]) in gripper_body_names]
if "GRIPPER_CONDIM" in os.environ:
    for g in gripper_geoms:
        compiled.geom_condim[g] = int(os.environ["GRIPPER_CONDIM"])
        compiled.geom_friction[g][1] = float(os.environ.get("TORSIONAL", "0.02"))
target_id = mujoco.mj_name2id(compiled, mujoco.mjtObj.mjOBJ_BODY, target.name.name)
print("target mass in MuJoCo", round(float(compiled.body_subtreemass[target_id]), 4), "gripper geoms", len(gripper_geoms), flush=True)
simulation.start_stepped_simulation()
simulator = simulation.simulator
model, data = simulator._mj_model, simulator._mj_data
model.vis.global_.offwidth, model.vis.global_.offheight = width, height
renderer = mujoco.Renderer(model, height, width)
camera = mujoco.MjvCamera()
camera.distance, camera.elevation = 3.0, -30.0
frames, simulated = [], [0.0, 0.0]
base_name = robot.root.name.name
step_simulation = simulation.step_simulation
wall_start = time.time()


stepping_wall = [0.0]


tool_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, robot.right_arm.end_effector.tool_frame.name.name)
target_body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, target.name.name)
fingertip_bodies = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, tip.name.name) for tip in (robot.right_arm.end_effector.thumb.tip, robot.right_arm.end_effector.finger.tip)}
finger_joint = robot.right_arm.end_effector.thumb.root.parent_connection.name.name
logged = [0.0]


base_body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, robot.root.name.name)
tracked = [0.0]


def log_tracking():
    if simulated[0] - tracked[0] < 1.0:
        return
    tracked[0] = simulated[0]
    commanded_base = robot.root.global_pose.to_np()[:3, 3]
    commanded_tool = robot.right_arm.end_effector.tool_frame.global_pose.to_np()[:3, 3]
    print(f"TRACK t={simulated[0]:.1f} base error {np.round(data.xpos[base_body] - commanded_base, 3)} tool error {np.round(data.xpos[tool_body] - commanded_tool, 3)}", flush=True)


def log_grasp():
    log_tracking()
    if simulated[0] - logged[0] < 0.25:
        return
    logged[0] = simulated[0]
    tool = data.xpos[tool_body]
    obj = data.xpos[target_body_id]
    contacts = sum(1 for c in data.contact[: data.ncon] if {model.geom_bodyid[c.geom1], model.geom_bodyid[c.geom2]} & fingertip_bodies and target_body_id in (model.body_rootid[model.geom_bodyid[c.geom1]], model.body_rootid[model.geom_bodyid[c.geom2]]))
    distance = np.linalg.norm(tool - obj)
    if distance < 0.15:
        commanded_tool = robot.right_arm.end_effector.tool_frame.global_pose.to_np()[:3, 3]
        print(f"GRASP t={simulated[0]:.2f} tool-obj {np.round(tool - obj, 3)} tool error {np.round(tool - commanded_tool, 3)} finger {simulator.get_joint_value(finger_joint).result:.3f} contacts {contacts} obj z {obj[2]:.3f}", flush=True)
    if os.environ.get("RENDER") == "grasp" and distance < 0.2:
        camera.lookat[:] = obj
        camera.distance, camera.elevation = 0.6, -25.0
        camera.azimuth = float(np.degrees(np.arctan2(*(tool - obj)[1::-1]))) + 70.0
        renderer.update_scene(data, camera)
        frames.append(renderer.render())


def stepping_and_rendering(duration):
    started = time.time()
    step_simulation(duration)
    log_grasp()
    render(duration)
    stepping_wall[0] += time.time() - started


def render(duration):
    if os.environ.get("RENDER", "1") in ("0", "grasp"):
        simulated[0] += duration.total_seconds()
        return
    simulated[0] += duration.total_seconds()
    if simulated[0] - simulated[1] < render_period:
        return
    simulated[1] = simulated[0]
    base = data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, base_name)]
    focus = (base + data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, target.name.name)]) / 2
    camera.lookat[:] = [focus[0], focus[1], 0.9]
    away = base[:2] - placement.to_np()[:2, 3]
    camera.azimuth = float(np.degrees(np.arctan2(away[1], away[0]))) + 25.0
    renderer.update_scene(data, camera)
    frames.append(renderer.render())
    if len(frames) % 250 == 0:
        print(f"sim {simulated[0]:.1f}s wall {time.time()-wall_start:.0f}s base {np.round(base, 3)} commanded "
              f"{np.round(robot.root.global_pose.to_np()[:3, 3], 3)} target {np.round(data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, target.name.name)], 3)}", flush=True)


simulation.step_simulation = stepping_and_rendering
from coraplex.robot_plans.actions.core.placing import PlaceAction
from semantic_digital_twin.reasoning.robot_predicates import fractions_of_rays_between_fingers_hitting_bodies
holding_arm_and_grasp = PlaceAction._holding_arm_and_grasp


def logging_holding_arm_and_grasp(self):
    for arm in self.robot.all_arms:
        fractions = fractions_of_rays_between_fingers_hitting_bodies(arm.end_effector)
        print("GRIP", arm.end_effector.name, "object", round(fractions.get(self.object_designator.root, 0.0), 2),
              "fingers", [round(v, 2) for b, v in fractions.items() if "finger" in str(b.name)], "z", round(float(self.object_designator.root.global_pose.to_np()[2, 3]), 3), flush=True)
    return holding_arm_and_grasp(self)


PlaceAction._holding_arm_and_grasp = logging_holding_arm_and_grasp
from coraplex.datastructures.enums import ExecutionType
from coraplex.plans.executables import GiskardExecutable, UnderspecifiedExecutable
from coraplex.plans.failures import CandidateLimitReached, EmptyUnderspecified, PlanFailure
giskard_execute = GiskardExecutable.execute


def logged_giskard_execute(self):
    if GiskardExecutable.execution_type == ExecutionType.PHYSICALLY_SIMULATED:
        print(f"EXEC t={simulated[0]:.1f}", str([type(motion).__name__ for motion in self.motion_mappings])[:200], flush=True)
    return giskard_execute(self)


def logged_underspecified_execute(self):
    while self.node.advance():
        try:
            self.node.current_candidate_sequence.parse().execute()
            self.node.stop_grounding()
            return
        except PlanFailure as failure:
            print(f"CANDIDATE FAILED t={simulated[0]:.1f}", type(failure).__name__, str(failure)[:300], flush=True)
            continue
    if self.node.reached_candidate_limit:
        raise CandidateLimitReached(self.node, self.node.candidate_limit)
    raise EmptyUnderspecified()


GiskardExecutable.execute = logged_giskard_execute
UnderspecifiedExecutable.execute = logged_underspecified_execute
context = Context(world, robot, sampling_seed=42)
transport = TransportAction.from_graspable_by_closest_grasps(episode.target_object, placement, robot.right_arm, context)
plan = sequential([MoveTorsoAction(TorsoState.HIGH), transport], context)
try:
    with PhysicallySimulatedRobot(simulation=simulation, collision_avoidance=collision_avoidance):
        plan.perform()
    print("plan done", flush=True)
    simulation.step_simulation(timedelta(seconds=2))
except Exception as error:
    print("plan failed:", type(error).__name__, str(error)[:400], flush=True)
finally:
    print(f"simulated {simulated[0]:.1f}s in {time.time()-wall_start:.0f}s wall, of which {stepping_wall[0]:.0f}s stepping and rendering", flush=True)
    outcome = episode.outcome()
    print("outcome", outcome, "target at", np.round(target.global_pose.to_np()[:3, 3], 3), flush=True)
    simulation.stop_simulation()
    if frames:
        imageio.mimwrite(output_path, frames, fps=25, macro_block_size=8)
        print("wrote", output_path, len(frames), "frames", flush=True)
