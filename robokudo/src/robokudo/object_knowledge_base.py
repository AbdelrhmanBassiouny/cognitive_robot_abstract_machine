"""
Object knowledge base for RoboKudo.

This module provides classes for storing and managing knowledge about objects
in RoboKudo. It includes support for object components, features, and their
spatial relationships.
"""

from dataclasses import field, dataclass
from pathlib import Path

from typing_extensions import Dict, List, Any, Optional

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import Connection6DoF
from semantic_digital_twin.world_description.geometry import Box, FileMesh, Scale, Color
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body, SemanticAnnotation
from semantic_digital_twin.world_description.world_entity import (
    Body,
    SemanticAnnotation,
)
from . import defs

@dataclass
class ObjectSpec:
    """
    Data structure to define typical object properties for predefined objects.
    Will be consumed by BaseObjectKnowledgeBase.build_objects to create a world
    and the corresponding connections.

    """
    name: str
    pose: HomogeneousTransformationMatrix
    mesh_path: Optional[Path] = None
    box_scale: Optional[Scale] = None
    center_mesh: bool = True
    color: Color = field(default_factory=lambda: Color(0.1, 0.2, 0.8, 1.0))


@dataclass
class ObjectKnowledge(defs.Region3DWithName):
    """Knowledge representation for a single object.

    This class extends Region3DWithName to add support for object components
    and features. Each object can have multiple components (physical parts)
    and features (characteristics).
    """

    components: List[Any] = field(default_factory=list)
    """List of component objects that make up this object"""

    features: List[Any] = field(default_factory=list)
    """List of features associated with this object"""

    mesh_ros_package: str = ""
    """ROS Package name where a mesh of this object is located"""

    mesh_relative_path: str = ""
    """Relative path to the actual mesh file. This path is relative to mesh_ros_package!"""

    def is_frame_in_camera_coordinates(self) -> bool:
        """Check whether the object is defined in camera coordinates.

        :return: True if the object is defined in camera coordinates, False otherwise.
        """
        return self.frame is None or self.frame == ""


@dataclass(eq=False)
class PredefinedObject(SemanticAnnotation):
    body: Body = field(default=None)


class BaseObjectKnowledgeBase:
    """Base class for managing object knowledge.

    This class provides functionality to store and manage knowledge about
    different objects. Each object is stored as an ObjectKnowledge instance
    and can be accessed by its name.
    """

    def __init__(self) -> None:
        """Initialize an empty object knowledge base."""

        """Dictionary mapping object names to their knowledge"""
        self.entries: Dict[str, ObjectKnowledge] = dict()

        self.world = World()
        root = Body(name=PrefixedName(name="root", prefix="world"))
        with self.world.modify_world():
            self.world.add_body(body=root)

    @staticmethod
    def _center_mesh_origin(mesh: FileMesh) -> None:
        """Shift mesh origin to the center of its local bounding box."""
        bb = mesh.local_frame_bounding_box
        center_x = (bb.min_x + bb.max_x) / 2
        center_y = (bb.min_y + bb.max_y) / 2
        center_z = (bb.min_z + bb.max_z) / 2
        mesh.origin = HomogeneousTransformationMatrix.from_xyz_rpy(
            -center_x, -center_y, -center_z, 0, 0, 0
        )

    def build_objects(
        self, root: Body, specs: List[Any]
    ) -> Dict[str, Connection6DoF]:
        """Create bodies, connections, annotations, and poses from object specs.

        Each spec must provide these attributes:
        - name: object name
        - pose: HomogeneousTransformationMatrix for world->object connection
        - mesh_path: optional Path to mesh file
        - box_scale: optional Scale for primitive box
        - center_mesh: bool to center mesh origin
        - color: Color for primitive box
        """
        connections: Dict[str, Connection6DoF] = {}

        with self.world.modify_world():
            for spec in specs:
                shapes: List[Any] = []
                collision: ShapeCollection

                if spec.mesh_path is not None:
                    mesh = FileMesh(
                        origin=HomogeneousTransformationMatrix(),
                        filename=str(spec.mesh_path),
                    )
                    if spec.center_mesh:
                        self._center_mesh_origin(mesh)
                    box = mesh.local_frame_bounding_box.as_shape()
                    shapes = [box, mesh]
                    collision = ShapeCollection([box])
                else:
                    if spec.box_scale is None:
                        raise ValueError(
                            f"ObjectSpec {spec.name} requires mesh_path or box_scale."
                        )
                    box = Box(scale=spec.box_scale, color=spec.color)
                    shapes = [box]
                    collision = ShapeCollection([box])

                body = Body(
                    name=PrefixedName(name=spec.name),
                    visual=ShapeCollection(shapes),
                    collision=collision,
                )
                connection = Connection6DoF.create_with_dofs(
                    parent=root, child=body, world=self.world
                )
                self.world.add_connection(connection)
                self.world.add_semantic_annotation(PredefinedObject(body=body))
                connections[spec.name] = connection

        # Set origins in a separate modification block so FK is compiled first
        with self.world.modify_world():
            for spec in specs:
                connections[spec.name].origin = spec.pose

        return connections

    def get_predefined_object_bodies(self) -> List[Body]:
        """Get list of pre-defined objects."""
        predefined_object_annotations = self.world.get_semantic_annotations_by_type(
            PredefinedObject
        )
        return list(
            [
                predefined_object.body
                for predefined_object in predefined_object_annotations
            ]
        )

    def add_entry(self, entry: ObjectKnowledge) -> None:
        """Add a single object knowledge entry.

        :param entry: The object knowledge entry to add
        :raises Exception: If the entry has no name attribute
        """
        if not hasattr(entry, "name"):
            raise Exception("Can't read name from ObjectKnowledge")

        self.entries[entry.name] = entry

    def add_entries(self, entries: List[ObjectKnowledge]) -> None:
        """Add multiple object knowledge entries.

        :param entries: List of object knowledge entries to add
        """
        for entry in entries:
            self.add_entry(entry)

    @staticmethod
    def has_parthood_childs(object_knowledge: ObjectKnowledge) -> bool:
        """Check if an object has any components or features.

        :param object_knowledge: The object knowledge to check
        :return: True if the object has components or features
        """
        return (
            len(object_knowledge.features) > 0 or len(object_knowledge.components) > 0
        )
