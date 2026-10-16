import collections, sys
import numpy
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaObjectCategory
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

loader = RoboCasaDatasetLoader()
layouts = [int(a) for a in sys.argv[1:]] or [1]
for layout in layouts:
    world = loader.load_kitchen(LayoutType(layout), StyleType(1), numpy.random.default_rng(0))
    annotations = collections.defaultdict(list)
    for annotation in world.semantic_annotations:
        root = getattr(annotation, "root", None)
        if root is not None:
            annotations[root.name.name].append(type(annotation).__name__)
    print(f"===== layout {layout}: {len(world.bodies)} bodies")
    for body in world.bodies:
        connection = body.parent_connection
        kind = type(connection).__name__ if connection is not None else "-"
        name = body.name.name
        interesting = any(k in name for k in ("handle", "knob", "button", "lever", "spout", "door", "drawer", "lid", "rack", "tray", "dial", "switch", "faucet", "head"))
        if kind not in ("FixedConnection", "-") or interesting or name in annotations:
            print(f"{name:60s} {kind:22s} vis={len(body.visual)} col={len(body.collision)} {annotations.get(name, '')}")
