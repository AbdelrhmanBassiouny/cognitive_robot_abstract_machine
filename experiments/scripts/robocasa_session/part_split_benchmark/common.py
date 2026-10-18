"""Shared settings of the part-splitting benchmark: the objects, the splitting settings and the paths."""
import json
from pathlib import Path

from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.adapters.robocasa_dataset.semantics import RoboCasaObjectCategory
from semantic_digital_twin.pipeline.mesh_decomposition.box_decomposer import BoxDecomposer
from semantic_digital_twin.pipeline.mesh_decomposition.coacd import ApproximationMode, COACDMeshDecomposer, PreprocessingMode
from semantic_digital_twin.pipeline.mesh_decomposition.vhacd import VHACDMeshDecomposer
from semantic_digital_twin.semantic_annotations.semantic_annotations import Mug, Pot
from semantic_digital_twin.world_description.shape_collection import ShapeCollection

OUT = Path("/root/work/part_split_benchmark")
SERVER = "http://172.17.0.7:8790"
CATEGORIES = {"mug": (RoboCasaObjectCategory.MUG, Mug, 18), "pot": (RoboCasaObjectCategory.POT, Pot, 15)}

# name -> (family, parameters shown in the report, factory)
CONFIGS = {
    "coacd_t0.05": ("COACD", {"hulls": "boxes", "threshold": 0.05}, lambda: COACDMeshDecomposer(seed=0)),
    "coacd_t0.1": ("COACD", {"hulls": "boxes", "threshold": 0.1}, lambda: COACDMeshDecomposer(threshold=0.1, seed=0)),
    "coacd_t0.2": ("COACD", {"hulls": "boxes", "threshold": 0.2}, lambda: COACDMeshDecomposer(threshold=0.2, seed=0)),
    "coacd_t0.3": ("COACD", {"hulls": "boxes", "threshold": 0.3}, lambda: COACDMeshDecomposer(threshold=0.3, seed=0)),
    "coacd_t0.05_max16": ("COACD", {"hulls": "boxes", "threshold": 0.05, "max_convex_hull": 16}, lambda: COACDMeshDecomposer(max_convex_hull=16, seed=0)),
    "coacd_t0.1_max8": ("COACD", {"hulls": "boxes", "threshold": 0.1, "max_convex_hull": 8}, lambda: COACDMeshDecomposer(threshold=0.1, max_convex_hull=8, seed=0)),
    "coacd_t0.1_pre30": ("COACD", {"hulls": "boxes", "threshold": 0.1, "preprocess_resolution": 30}, lambda: COACDMeshDecomposer(threshold=0.1, preprocess_resolution=30, seed=0)),
    "coacd_ch_t0.05": ("COACD", {"hulls": "convex", "threshold": 0.05}, lambda: COACDMeshDecomposer(approximation_mode=ApproximationMode.CONVEX_HULL, seed=0)),
    "coacd_ch_t0.1": ("COACD", {"hulls": "convex", "threshold": 0.1}, lambda: COACDMeshDecomposer(approximation_mode=ApproximationMode.CONVEX_HULL, threshold=0.1, seed=0)),
    "coacd_ch_t0.2": ("COACD", {"hulls": "convex", "threshold": 0.2}, lambda: COACDMeshDecomposer(approximation_mode=ApproximationMode.CONVEX_HULL, threshold=0.2, seed=0)),
    "coacd_ch_t0.1_preon": ("COACD", {"hulls": "convex", "threshold": 0.1, "preprocess": "on"}, lambda: COACDMeshDecomposer(approximation_mode=ApproximationMode.CONVEX_HULL, threshold=0.1, preprocess_mode=PreprocessingMode.ON, seed=0)),
    "vhacd_8": ("V-HACD", {"max_convex_hulls": 8}, lambda: VHACDMeshDecomposer(max_convex_hulls=8)),
    "vhacd_16": ("V-HACD", {"max_convex_hulls": 16}, lambda: VHACDMeshDecomposer(max_convex_hulls=16)),
    "vhacd_32": ("V-HACD", {"max_convex_hulls": 32}, lambda: VHACDMeshDecomposer(max_convex_hulls=32)),
    "box_5mm": ("Boxes", {"voxel_size": 0.005}, lambda: BoxDecomposer(voxel_size=0.005)),
    "box_10mm": ("Boxes", {"voxel_size": 0.01}, lambda: BoxDecomposer(voxel_size=0.01)),
}


def objects():
    return [f"{name}_{index}" for name, (_, _, count) in CATEGORIES.items() for index in range(count)]


def load(key):
    """:return: the world and the annotation of one benchmark object, e.g. ``mug_3``."""
    name, index = key.rsplit("_", 1)
    category, annotation_type, _ = CATEGORIES[name]
    world = RoboCasaDatasetLoader().load_object(category, int(index))
    [whole] = world.get_semantic_annotations_by_type(annotation_type)
    # RoboCasa's region geoms (reg_bbox and the placement cylinders) are fully transparent but
    # parsed as visual shapes; drop them so the mesh is the object as it looks.
    visible = [shape for shape in whole.root.visual if shape.color is None or shape.color.to_rgba()[3] > 0]
    whole.root.visual = ShapeCollection(shapes=visible, reference_frame=whole.root)
    return world, whole


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1))
