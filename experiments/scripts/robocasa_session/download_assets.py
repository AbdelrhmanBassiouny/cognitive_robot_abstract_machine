"""Download RoboCasa kitchen textures and fixtures with the version assertions relaxed."""
import builtins

from semantic_digital_twin.adapters.robocasa_dataset.mujoco_compat import robocasa_version_assertions_relaxed

builtins.input = lambda prompt="": "y"
with robocasa_version_assertions_relaxed():
    from robocasa.scripts.download_kitchen_assets import download_kitchen_assets
download_kitchen_assets(["tex", "tex_generative", "fixtures_lw"])
