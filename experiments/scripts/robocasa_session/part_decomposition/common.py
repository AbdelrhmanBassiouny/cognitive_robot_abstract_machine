"""Shared settings of the RoboCasa part decomposition run: which objects, where the results go."""
import json
from pathlib import Path

from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaObjectCategory
from semantic_digital_twin.semantic_annotations.semantic_annotations import Cup, Kettle, Mug, Pan, Pot

OUT = Path("/root/work/part_decomposition")
SERVER = "http://172.17.0.7:8790"
# the RoboCasa objects a robot holds by a handle
CATEGORIES = {
    "mug": (RoboCasaObjectCategory.MUG, Mug),
    "pot": (RoboCasaObjectCategory.POT, Pot),
    "pan": (RoboCasaObjectCategory.PAN, Pan),
    "kettle": (RoboCasaObjectCategory.KETTLE, Kettle),
    "cup": (RoboCasaObjectCategory.CUP, Cup),
}


def model_files(category):
    loader = RoboCasaDatasetLoader()
    directory = loader.directory / "objects"
    return sorted(f for g in loader.self_contained_object_groups for f in (directory / g).glob(f"{category}/**/model.xml"))


def objects():
    """:return: ``{key: asset path}`` for every object, e.g. ``{"mug_3": "objaverse/mug/mug_13"}``."""
    keys = {}
    for name, (category, _) in CATEGORIES.items():
        for index, f in enumerate(model_files(category)):
            keys[f"{name}_{index}"] = str(f.parent.relative_to(RoboCasaDatasetLoader().directory / "objects"))
    return keys


def load(key):
    """:return: the world and the annotation of one object, loaded the way the loader loads it."""
    name, index = key.rsplit("_", 1)
    category, annotation_type = CATEGORIES[name]
    world = RoboCasaDatasetLoader().load_object(category, int(index))
    [whole] = world.get_semantic_annotations_by_type(annotation_type)
    return world, whole


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))
