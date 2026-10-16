"""How far from the middle of their collision geometry do RoboCasa objects have their origin?"""
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
for attempt in range(6):
    episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT002, StyleType.STYLE001)
    body = episode.target_object.root
    mesh = body.collision.combined_mesh
    lowest, highest = mesh.bounds
    print(f"{episode.task.instruction[9:40]:32s} origin to box center {np.round((lowest + highest) / 2, 3)} extents {np.round(highest - lowest, 3)}", flush=True)
