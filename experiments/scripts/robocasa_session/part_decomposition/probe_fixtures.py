"""Which RoboCasa fixture models have doors whose handle is still part of the door mesh?"""
import json, sys, traceback
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaKitchenApplianceCategory as K
from semantic_digital_twin.semantic_annotations.mixins import HasHandle
from robocasa.models.scenes.scene_registry import StyleType

loader = RoboCasaDatasetLoader()
seen = {}
for style in StyleType:
    for category in (K.FRIDGE, K.MICROWAVE, K.DISHWASHER, K.OVEN, K.STOVE, K.CABINET, K.DRAWER, K.TOASTER, K.COFFEE_MACHINE):
        try:
            appliance = loader._find_configured_appliance(category, style)
            model = getattr(appliance, "file", None) or getattr(appliance, "xml", None) or type(appliance).__name__
            key = f"{category}:{model}"
            if key in seen:
                continue
            world = loader.load_kitchen_appliance(category, style)
            missing = []
            for a in world.semantic_annotations:
                if isinstance(a, HasHandle) and a.handle is None:
                    root = a.root
                    missing.append({"type": type(a).__name__, "body": root.name.name, "visual": len(root.visual), "collision": len(root.collision)})
            seen[key] = {"category": str(category), "style": style.name if hasattr(style, "name") else str(style), "model": str(model), "missing_handles": missing}
            print(json.dumps(seen[key]), flush=True)
        except Exception as error:
            print(json.dumps({"category": str(category), "style": str(style), "error": f"{type(error).__name__}: {str(error)[:150]}"}), flush=True)
