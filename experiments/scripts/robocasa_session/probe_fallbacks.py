"""List the kitchen bodies the loader falls back to a natural-language annotation for."""
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.semantic_annotations.natural_language import NaturalLanguageWithTypeDescription

for layout in (LayoutType.LAYOUT001, LayoutType.LAYOUT005):
    world = RoboCasaDatasetLoader().load_kitchen(layout, StyleType.STYLE001)
    fallbacks = [(a.root.name.name, a.type_description) for a in world.semantic_annotations if isinstance(a, NaturalLanguageWithTypeDescription)]
    print(layout.name, fallbacks)
    print("  floor bodies", [b.name.name for b in world.bodies if "floor" in b.name.name])
