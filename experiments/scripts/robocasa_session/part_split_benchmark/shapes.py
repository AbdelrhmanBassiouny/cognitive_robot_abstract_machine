"""List the bodies and visual/collision shapes of benchmark objects, and the geoms of their MJCF."""
import sys, re
from common import load, CATEGORIES
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
loader = RoboCasaDatasetLoader(); d = loader.directory / "objects"
for key in sys.argv[1:]:
    world, whole = load(key)
    name, index = key.rsplit("_", 1); category = CATEGORIES[name][0]
    files = sorted(f for g in loader.self_contained_object_groups for f in (d / g).glob(f"{category}/**/model.xml"))
    print("=====", key, files[int(index)].relative_to(d))
    for body in world.bodies:
        print("  body", body.name.name, "visual", [type(s).__name__ for s in body.visual][:6], len(body.visual), "collision", len(body.collision))
    xml = files[int(index)].read_text()
    for geom in re.findall(r"<geom[^>]*>", xml)[:8]:
        print("   ", geom[:220])
