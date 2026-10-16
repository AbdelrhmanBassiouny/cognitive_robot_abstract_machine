import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001, seed=10)
world, env = episode.task.world, episode.environment
for name, model in env.objects.items():
    body = world.get_body_by_name(model.root_body)
    box = body.collision.as_bounding_box_collection_in_frame(world.root).bounding_box()
    print("OBJ", name, model.mjcf_path.split("/")[-2], "ours", np.round([box.min_x, box.min_y, box.min_z, box.max_x, box.max_y, box.max_z], 3).tolist(),
          "robocasa", np.round(env.sim.data.get_body_xpos(model.root_body), 3).tolist(), "shapes", len(body.collision.shapes))
