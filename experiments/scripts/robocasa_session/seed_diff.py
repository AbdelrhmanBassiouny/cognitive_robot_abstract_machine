import difflib
from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed
with robocasa_version_assertions_relaxed():
    import robocasa  # noqa
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
loader = RoboCasaDatasetLoader()
envs = [loader.build_task_environment("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001, seed=7) for _ in range(2)]
a, b = (e.model.get_xml().splitlines() for e in envs)
a = [l for x in a for l in x.replace("><", ">\n<").splitlines()]
b = [l for x in b for l in x.replace("><", ">\n<").splitlines()]
diff = list(difflib.unified_diff(a, b, lineterm="", n=0))
print(len(diff), "diff lines")
for line in diff[:40]:
    print(line[:300])
print("objects", [ (k, v.name) for k, v in envs[0].objects.items()], [(k, v.name) for k, v in envs[1].objects.items()])
