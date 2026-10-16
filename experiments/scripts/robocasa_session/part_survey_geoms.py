import re, xml.etree.ElementTree as ET
import numpy, yaml
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes import scene_registry
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from robocasa.models.scenes import scene_builder
from robocasa.models.scenes.kitchen_arena import KitchenArena
from robosuite.models.tasks import ManipulationTask

rng = numpy.random.default_rng(0)
layout = yaml.safe_load(open(scene_registry.get_layout_path(LayoutType(1))))
style = yaml.safe_load(open(scene_registry.get_style_path(StyleType(1))))
arena = KitchenArena(layout_id=LayoutType(1), style_id=StyleType(1), rng=rng)
fixtures = scene_builder.create_fixtures(layout, style, rng=rng)
root = ET.fromstring(ManipulationTask(mujoco_arena=arena, mujoco_robots=[], mujoco_objects=list(fixtures.values())).get_xml())
pattern = re.compile(r"handle|button|knob|lever|switch|dial|spout|lid|rim", re.I)
for body in root.iter("body"):
    name = body.get("name", "")
    if not re.search(r"microwave|fridge|dishwasher|stove|sink|coffee|toaster|stack_1_main_group_1|cab_1", name):
        continue
    hits = sorted({g.get("name", "") for g in body.findall("geom") if pattern.search(g.get("name", ""))})
    if hits:
        print(f"{name:45s} {hits}")
