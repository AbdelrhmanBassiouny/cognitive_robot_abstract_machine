from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
manager = world.collision_manager
manager.update_collision_matrix()
own = set(robot.bodies_with_collision)
for contact in manager.compute_collisions().contacts:
    names = str(contact.body_a.name) + str(contact.body_b.name)
    if "floor" in names and (contact.body_a in own or contact.body_b in own):
        print("FLOOR", contact.body_a.name, contact.body_b.name, repr(contact.distance), repr(manager.get_violated_distance(contact.body_a, contact.body_b)), flush=True)
