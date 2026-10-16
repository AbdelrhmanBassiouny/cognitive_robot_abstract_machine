"""Compose the counter to sink episode, mirror it into MuJoCo with the PR2's servos and drive, and step it."""
import faulthandler, sys, time
from datetime import timedelta
import numpy as np
faulthandler.dump_traceback_later(900, exit=True)
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.multi_sim import MujocoSim

t = time.time()
episode = CounterToSinkEpisode.compose(LayoutType[sys.argv[1] if len(sys.argv) > 1 else "LAYOUT001"], StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
print(f"composed in {time.time()-t:.0f}s; actuators {len(world.actuators)}; drive {type(robot.drive).__name__}", flush=True)
base_name = robot.root.name.name
target = episode.target_object.root
print("kinematic base", np.round(robot.root.global_pose.to_np()[:3, 3], 3), "target", np.round(target.global_pose.to_np()[:3, 3], 3), flush=True)
t = time.time()
simulation = MujocoSim(world=world, headless=True)
simulation.start_stepped_simulation()
print(f"mujoco built in {time.time()-t:.0f}s; nbody {simulation.simulator._mj_model.nbody} ngeom {simulation.simulator._mj_model.ngeom}", flush=True)
for second in range(3):
    t = time.time()
    simulation.step_simulation(timedelta(seconds=1))
    base = simulation.simulator.get_body_position(body_name=base_name).result
    obj = simulation.simulator.get_body_position(body_name=target.name.name).result
    print(f"t={second+1}s ({time.time()-t:.1f}s wall) base {np.round(base,3)} target {np.round(obj,3)} ncon {simulation.simulator._mj_data.ncon}", flush=True)
simulation.stop_simulation()
