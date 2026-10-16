from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed
with robocasa_version_assertions_relaxed():
    import robocasa  # noqa
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
loader = RoboCasaDatasetLoader()
for _ in range(3):
    env = loader.build_task_environment("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001, seed=7)
    print("RESULT", [m.mjcf_path.split("/")[-2] for m in env.objects.values()], env.sim.data.get_body_xpos(env.objects["obj"].root_body).round(4).tolist())
