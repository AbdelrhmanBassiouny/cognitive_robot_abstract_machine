from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from robokudo.object_knowledge_base import (
    BaseObjectKnowledgeBase,
    ObjectKnowledge,
    PredefinedObject,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from robokudo.object_knowledge_base import BaseObjectKnowledgeBase, ObjectSpec
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world_description.geometry import Color, Scale



@dataclass
class ObjectKnowledgeBase(BaseObjectKnowledgeBase):
    def __init__(self) -> None:
        super().__init__()
        root = self.world.root

        milk_path = (
            Path(__file__).resolve().parents[5]
            / "semantic_digital_twin"
            / "resources"
            / "stl"
            / "milk.stl"
        )

        specs = [
            ObjectSpec(
                name="cereal",
                box_scale=Scale(0.20, 0.20, 0.20),
                pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-1.3, y=1.0, z=1.1, reference_frame=root
                ),
            ),
            ObjectSpec(
                name="milk",
                mesh_path=milk_path,
                pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                    x=-1.3, y=1.2, z=1.1, reference_frame=root
                ),
            ),
        ]

        self.build_objects(root, specs)
