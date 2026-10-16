import sys, traceback
import numpy as np
from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed
with robocasa_version_assertions_relaxed():
    import robocasa  # noqa
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
import robosuite.environments.base as base

class LoggingGenerator:
    def __init__(self, generator, log):
        self._generator, self._log = generator, log
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        attribute = getattr(self._generator, name)
        if not callable(attribute):
            return attribute
        def call(*args, **kwargs):
            frame = traceback.extract_stack(limit=3)[0]
            result = attribute(*args, **kwargs)
            self._log.append(f"{frame.filename.split('/')[-1]}:{frame.lineno} {name} -> {str(result)[:60]}")
            return result
        return call

logs = []
original_init = base.MujocoEnv.__init__
def init(self, *a, **k):
    original_init(self, *a, **k)
logs_current = []
original_setattr = base.MujocoEnv.__setattr__
def setattr_(self, name, value):
    if name == "rng" and isinstance(value, np.random.Generator):
        value = LoggingGenerator(value, logs[-1])
    original_setattr(self, name, value)
base.MujocoEnv.__setattr__ = setattr_
loader = RoboCasaDatasetLoader()
for _ in range(2):
    logs.append([])
    env = loader.build_task_environment("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001, seed=7)
a, b = logs
print("calls", len(a), len(b))
for index, (x, y) in enumerate(zip(a, b)):
    if x != y:
        print("first divergence at", index)
        for line in a[max(0, index - 5): index + 5]:
            print("A", line)
        for line in b[max(0, index - 5): index + 5]:
            print("B", line)
        break
