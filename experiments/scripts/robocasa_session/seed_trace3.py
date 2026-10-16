from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed
with robocasa_version_assertions_relaxed():
    import robocasa  # noqa
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from robocasa.models.fixtures.fixture import Fixture
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader

original = Fixture.get_reset_regions
def traced(self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    print("REGIONS", self.name, {k: v for k, v in kwargs.items() if k != "env" and k != "ref"}, "ref", getattr(kwargs.get("ref"), "name", kwargs.get("ref")),
          [(name, [round(float(x), 3) for x in region["size"]]) for name, region in result.items()])
    return result
for cls in [Fixture] + Fixture.__subclasses__():
    pass
import robocasa.models.fixtures.counter as counter
original_counter = counter.Counter.get_reset_regions
def traced_counter(self, *args, **kwargs):
    result = original_counter(self, *args, **kwargs)
    print("COUNTER", self.name, {k: v for k, v in kwargs.items() if k not in ("env", "ref")}, "ref", getattr(kwargs.get("ref"), "name", kwargs.get("ref")),
          [(name, [round(float(x), 3) for x in region["size"]]) for name, region in result.items()])
    return result
counter.Counter.get_reset_regions = traced_counter
loader = RoboCasaDatasetLoader()
for _ in range(2):
    print("=== build")
    loader.build_task_environment("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001, seed=7)
