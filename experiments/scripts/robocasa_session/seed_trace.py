from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed
with robocasa_version_assertions_relaxed():
    import robocasa  # noqa
import robocasa.models.objects.kitchen_object_utils as kou
import robocasa.environments.kitchen.kitchen as kitchen
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader

original = kou.sample_kitchen_object
def traced(groups, *args, **kwargs):
    rng = kwargs.get("rng")
    state = None if rng is None else rng.bit_generator.state["state"]["state"] % 100000
    result = original(groups, *args, **kwargs)
    print("SAMPLE", groups, "rng", state, result[1]["mjcf_path"].split("/")[-2])
    return result
kitchen.sample_kitchen_object = traced
original_load = kitchen.Kitchen._load_model
def traced_load(self, *a, **k):
    print("LOAD_MODEL seed", self.seed, "rng", self.rng.bit_generator.state["state"]["state"] % 100000)
    return original_load(self, *a, **k)
kitchen.Kitchen._load_model = traced_load
loader = RoboCasaDatasetLoader()
for _ in range(2):
    print("=== build")
    env = loader.build_task_environment("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001, seed=7)
