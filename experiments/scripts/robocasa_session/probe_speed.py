"""Where does the wall time of a stepped MuJoCo RoboCasa simulation go?"""
import collections, faulthandler, sys, time
from datetime import timedelta
import mujoco
import numpy as np
faulthandler.dump_traceback_later(900, exit=True)
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.multi_sim import MujocoSim
from giskardpy.executor import SteppedSimulationPacer

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT002, StyleType.STYLE001)
world = episode.task.world
simulation = MujocoSim(world=world, headless=True)
simulation.start_stepped_simulation()
simulator = simulation.simulator
model, data = simulator._mj_model, simulator._mj_data
o = model.opt
print("timestep", o.timestep, "integrator", o.integrator, "solver", o.solver, "iterations", o.iterations, "ls", o.ls_iterations,
      "cone", o.cone, "jacobian", o.jacobian, "noslip", o.noslip_iterations, "ccd", o.ccd_iterations, "simulator.step_size", simulator.step_size,
      "nv", model.nv, "nu", model.nu, "ngeom", model.ngeom, "nmesh", model.nmesh, flush=True)
simulation.step_simulation(timedelta(seconds=0.5))
t = time.time(); simulation.step_simulation(timedelta(seconds=1)); wall = time.time() - t
print(f"1 s simulated in {wall:.2f}s wall via step_simulation", flush=True)
n = round(1 / o.timestep)
t = time.time()
for _ in range(n):
    mujoco.mj_step(model, data)
print(f"raw mj_step x{n}: {time.time()-t:.2f}s", flush=True)
t = time.time()
for _ in range(n):
    simulator.step()
print(f"simulator.step x{n}: {time.time()-t:.2f}s", flush=True)
for integrator in (0, 3):
    saved = model.opt.integrator; model.opt.integrator = integrator; t = time.time()
    for _ in range(n):
        mujoco.mj_step(model, data)
    print(f"integrator {integrator}: mj_step x{n}: {time.time()-t:.2f}s", flush=True); model.opt.integrator = saved
# profile one mj_step
before = {i: (data.timer[i].duration, data.timer[i].number) for i in range(len(data.timer))}
for _ in range(200):
    mujoco.mj_step(model, data)
for name in ["mjTIMER_STEP", "mjTIMER_FORWARD", "mjTIMER_POSITION", "mjTIMER_VELOCITY", "mjTIMER_ACTUATION", "mjTIMER_CONSTRAINT",
             "mjTIMER_POS_COLLISION", "mjTIMER_POS_MAKE", "mjTIMER_POS_PROJECT", "mjTIMER_COL_BROAD", "mjTIMER_COL_NARROW"]:
    timer = data.timer[getattr(mujoco.mjtTimer, name)]
    i = int(getattr(mujoco.mjtTimer, name)); d = timer.duration - before[i][0]; k = timer.number - before[i][1]
    print(f"{name}: {d / max(k, 1) * 1e3:.3f} ms per call ({k} calls)")
print("ncon", data.ncon, "nefc", data.nefc, "solver niter", data.solver_niter[:1], flush=True)
pairs = collections.Counter()
for c in data.contact[: data.ncon]:
    b1 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[c.geom1])
    b2 = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, model.geom_bodyid[c.geom2])
    pairs[(b1, b2)] += 1
for pair, count in pairs.most_common(25):
    print(count, pair)
# which servoed joints move at rest?
pacer = SteppedSimulationPacer(simulation)
names = pacer._servoed_joint_names()
prev = simulator.get_joints_values(names).result
pacer.sleep()
cur = simulator.get_joints_values(names).result
speeds = sorted(((abs(cur[k] - prev[k]) * pacer.target_frequency, k) for k in names), reverse=True)[:8]
print("target_frequency", pacer.target_frequency, "fastest joints at rest (per s):", [(round(s, 4), k) for s, k in speeds], flush=True)
simulation.stop_simulation()
