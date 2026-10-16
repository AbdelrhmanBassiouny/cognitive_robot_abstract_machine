import sys, time, collections
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


PlanFailure.__post_init__ = reporting_post_init
for layout in sys.argv[1:]:
    episode = CounterToSinkEpisode.compose(LayoutType[layout], StyleType.STYLE001)
    print("TASK", layout, episode.task.instruction, flush=True)
    start = time.time()
    try:
        succeeded = episode.perform(collision_avoidance=True).succeeded
    except PlanFailure as failure:
        succeeded = type(failure).__name__
    print("RESULT", layout, succeeded, f"{time.time() - start:.0f}s", dict(counts), flush=True)
    counts.clear()
