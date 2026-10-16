from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaObjectCategory
from semantic_digital_twin.part_finding.relationships import PartRelationshipInspector
from robocasa.models.objects.kitchen_objects import OBJ_CATEGORIES

loader = RoboCasaDatasetLoader()
print("object categories in RoboCasa:", len(OBJ_CATEGORIES))
first = next(iter(OBJ_CATEGORIES.values())); print(type(first), list(first.keys()) if isinstance(first, dict) else vars(first).keys()); print(sorted(OBJ_CATEGORIES))
for category in RoboCasaObjectCategory:
    try:
        world = loader.load_object(category)
    except Exception as error:
        print(category, type(error).__name__); continue
    annotation = next(a for a in world.semantic_annotations if getattr(a, "root", None) is not None)
    relationships = [r.name for r in PartRelationshipInspector.all_of_type(type(annotation))]
    bodies = [b for b in world.bodies if b.visual or b.collision]
    print(f"{category:8s} {type(annotation).__name__:10s} bodies={len(bodies)} vis={[len(b.visual) for b in bodies]} col={[len(b.collision) for b in bodies]} parts={relationships}")
