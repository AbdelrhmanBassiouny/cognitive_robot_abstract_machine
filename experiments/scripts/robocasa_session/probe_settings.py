"""Wall time per simulated second and resting drift of the PR2 for several MuJoCo settings."""
import cProfile, pstats, sys, time
from copy import deepcopy
from datetime import timedelta
import mujoco
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.multi_sim import MujocoSim

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT002, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
tools = [arm.end_effector.tool_frame.name.name for arm in robot.all_arms]
settings = {
    "rk4 1ms": dict(step_size=1e-3),
    "implicitfast 1ms": dict(step_size=1e-3, integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST),
    "implicitfast 2ms": dict(step_size=2e-3, integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST),
    "implicitfast 4ms": dict(step_size=4e-3, integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST),
}
for label, kwargs in settings.items():
    simulation = MujocoSim(world=world, headless=True, **kwargs)
    simulation.start_stepped_simulation()
    simulator = simulation.simulator
    def poses():
        return np.concatenate([simulator.get_body_position(body_name=name).result for name in [robot.root.name.name, *tools]])
    start = poses()
    t = time.time()
    if label == "implicitfast 2ms":
        profiler = cProfile.Profile(); profiler.enable()
    simulation.step_simulation(timedelta(seconds=2))
    wall = (time.time() - t) / 2
    if label == "implicitfast 2ms":
        profiler.disable()
    drift = np.abs(poses() - start).max()
    print(f"{label}: {wall:.2f}s wall per simulated second, max drift {drift*1000:.1f} mm", flush=True)
    if label == "implicitfast 2ms":
        pstats.Stats(profiler).sort_stats("cumulative").print_stats(14)
    simulation.stop_simulation()
