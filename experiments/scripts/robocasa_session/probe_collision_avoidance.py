import sys, time, logging
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from giskardpy.motion_statechart.goals import collision_avoidance as ca

added = []
original = ca.ExternalCollisionAvoidance.__post_init__ if hasattr(ca.ExternalCollisionAvoidance, "__post_init__") else None
for layout in sys.argv[1:]:
    episode = CounterToSinkEpisode.compose(LayoutType[layout], StyleType.STYLE001)
    start = time.time()
    outcome = episode.perform(collision_avoidance=True)
    print(layout, episode.task.instruction, outcome.succeeded, f"{time.time() - start:.0f}s", flush=True)
