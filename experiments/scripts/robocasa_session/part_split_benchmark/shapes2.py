"""Print each visual shape of an object with its color and size, plus the MJCF default classes."""
import sys, re
from common import load, CATEGORIES
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
loader = RoboCasaDatasetLoader(); d = loader.directory / "objects"
for key in sys.argv[1:]:
    world, whole = load(key)
    print("=====", key)
    for s in whole.root.visual:
        print("  ", type(s).__name__, "rgba", s.color.to_rgba() if hasattr(s, "color") and s.color is not None else None, "extents", s.mesh.extents.round(3))
    name, index = key.rsplit("_", 1); category = CATEGORIES[name][0]
    files = sorted(f for g in loader.self_contained_object_groups for f in (d / g).glob(f"{category}/**/model.xml"))
    xml = files[int(index)].read_text()
    print(re.findall(r"<default[^>]*>.*?</default>", xml, re.S)[:3])
    print([g[:160] for g in re.findall(r"<site[^>]*>", xml)][:4])
