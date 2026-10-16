"""List the connections hanging directly off the world root, for the kitchen alone and with the PR2."""
from collections import Counter

from experiments.robocasa_kitchen_demo import _spawn_robot_and_prepare_pick_up, load_kitchen
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

world = load_kitchen(LayoutType.LAYOUT001, StyleType.STYLE001)
def report(label):
    root_connections = [c for c in world.connections if c.parent == world.root]
    print(label, "root", world.root.name, Counter(type(c).__name__ for c in root_connections))
    print("  non-fixed:", [(type(c).__name__, c.child.name.name) for c in root_connections if type(c).__name__ != "FixedConnection"][:10])
report("kitchen")
_spawn_robot_and_prepare_pick_up(world)
report("kitchen+pr2")
