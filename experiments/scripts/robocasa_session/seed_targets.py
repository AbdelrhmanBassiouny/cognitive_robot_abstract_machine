from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed
with robocasa_version_assertions_relaxed():
    import robocasa  # noqa
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
loader = RoboCasaDatasetLoader()
for seed in range(1, 25):
    env = loader.build_task_environment("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001, seed=seed)
    print("SEED", seed, env.objects["obj"].mjcf_path.split("/")[-2], flush=True)
