"""Compare the target's mass in RoboCasa's own model, in the world and in our MuJoCo build, and check that a seed fixes the episode."""
import random, sys
import mujoco, numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
for attempt in range(2):
    random.seed(7); np.random.seed(7)
    episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT002, StyleType.STYLE001)
    target = episode.target_object.root
    sim = episode.environment.sim
    body_id = sim.model.body_name2id(episode.environment.objects["obj"].root_body)
    subtree = [b for b in range(sim.model.nbody) if sim.model.body_rootid[b] == sim.model.body_rootid[body_id]]
    print(attempt, episode.task.instruction, "| robocasa mass", round(float(sim.model.body_mass[subtree].sum()), 4),
          "| world inertial", None if target.inertial is None else target.inertial.mass, flush=True)
