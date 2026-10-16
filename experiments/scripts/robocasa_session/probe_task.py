"""Load the RoboCasa counter to sink task and print what the CRAM world knows about it."""
from collections import Counter

from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.grasping.grasp_candidates import HasGraspCandidates

task = RoboCasaDatasetLoader().load_task("PickPlaceCounterToSink", LayoutType.LAYOUT001, StyleType.STYLE001)
world = task.world
print("instruction:", task.instruction)
print("robot base pose:", task.robot_base_pose.to_np().round(2).tolist())
print("annotation types:", Counter(type(a).__name__ for a in world.semantic_annotations))
for body in task.manipulated_objects:
    annotations = [a for a in world.semantic_annotations if a.root == body]
    print("object", body.name.name, [type(a).__name__ for a in annotations],
          "graspable", [isinstance(a, HasGraspCandidates) for a in annotations],
          "pose", body.global_pose.to_np()[:3, 3].round(2).tolist(),
          "parent", type(body.parent_connection).__name__)
for annotation in world.semantic_annotations:
    if "Sink" in type(annotation).__name__:
        box = annotation.root.collision.as_bounding_box_collection_in_frame(world.root).bounding_box() if annotation.root.collision.shapes else None
        print("sink", annotation.root.name.name, box)
