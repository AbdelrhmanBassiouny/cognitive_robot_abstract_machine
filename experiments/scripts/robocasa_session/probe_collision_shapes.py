from collections import Counter
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001)
world, robot = episode.task.world, episode.robot
robot_bodies = set(world.get_kinematic_structure_entities_of_branch(robot.root))
kitchen = [b for b in world.bodies if b not in robot_bodies]
kinds = Counter()
for b in kitchen:
    v, c = bool(b.visual.shapes), bool(b.collision.shapes)
    kinds[(v, c)] += 1
print("kitchen bodies (visual, collision):", dict(kinds))
print("same shape objects:", sum(1 for b in kitchen if b.collision.shapes and b.collision.shapes is b.visual.shapes))
for name in ["counter_main_main_group_main", "sink_main_group_main", "stack_2_main_group_2_door_main", episode.target_object.root.name.name]:
    b = world.get_body_by_name(name)
    print(name, "visual", Counter(type(s).__name__ for s in b.visual.shapes), "collision", Counter(type(s).__name__ for s in b.collision.shapes))
