import os, time, traceback
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

seed = int(os.environ.get("SEED", "10"))
episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=seed)
print("TARGET", episode.environment.objects["obj"].mjcf_path.split("/")[-2], flush=True)
start = time.time()
try:
    outcome = episode.perform(collision_avoidance=os.environ.get("COLLISION_AVOIDANCE", "1") == "1")
    print("OUTCOME", outcome, "succeeded", outcome.succeeded)
except Exception as failure:
    traceback.print_exc()
    print("FAILED", type(failure).__name__, str(failure)[:500])
print("TOOK", round(time.time() - start), "s; target at", np.round(episode.target_object.root.global_pose.to_np()[:3, 3], 3).tolist())
