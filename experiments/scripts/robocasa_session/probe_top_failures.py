import sys, time, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from top_grasps import use_top_grasps
from coraplex.plans.failures import PlanFailure
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

counts = collections.Counter()
original = PlanFailure.__post_init__


def reporting_post_init(self):
    original(self)
    first = str(self).splitlines()
    detail = first[1] if len(first) > 1 else ""
    counts[type(self).__name__] += 1
    print("FAIL", type(self).__name__, first[0][:120], "|", detail[:120], flush=True)
    if type(self).__name__ == "MotionViolatedCollisionAvoidance":
        violated = [line for line in first[1:] if "<" in line and float(line.split(": ")[-1].split(" < ")[0]) < float(line.split(" < ")[-1])]
        print("VIOLATED", sorted(set(violated))[:4], flush=True)


import inspect
from semantic_digital_twin.world import World


def closest_contacts_at_stall():
    for frame_info in inspect.stack():
        for value in frame_info.frame.f_locals.values():
            world = value if isinstance(value, World) else (vars(value).get("world") or vars(value).get("_world") if hasattr(value, "__dict__") else None)
            if isinstance(world, World):
                manager = world.collision_manager
                manager.update_collision_matrix()
                contacts = sorted(manager.compute_collisions().contacts, key=lambda c: c.distance - manager.get_violated_distance(c.body_a, c.body_b))
                return [f"{c.body_a.name.name}|{c.body_b.name.name} {c.distance:.3f}/{manager.get_violated_distance(c.body_a, c.body_b):.2f}" for c in contacts[:6]]
    return ["no world found"]


def stall_reporting_post_init(self):
    reporting_post_init(self)
    if type(self).__name__ == "MotionMadeNoProgress" and "MoveTCP" in str(self):
        print("CLOSEST", closest_contacts_at_stall(), flush=True)


PlanFailure.__post_init__ = stall_reporting_post_init
for layout in [a for a in sys.argv[1:] if a.startswith("LAYOUT")]:
    episode = CounterToSinkEpisode.compose(LayoutType[layout], StyleType.STYLE001)
    use_top_grasps(episode.target_object)
    print("TASK", layout, episode.task.instruction, flush=True)
    start = time.time()
    try:
        succeeded = episode.perform(collision_avoidance="noavoid" not in sys.argv).succeeded
    except PlanFailure as failure:
        succeeded = type(failure).__name__
    print("RESULT", layout, succeeded, f"{time.time() - start:.0f}s", dict(counts), flush=True)
    counts.clear()
