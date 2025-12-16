from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Iterable, Optional, Self, Tuple

import numpy as np
from probabilistic_model.probabilistic_circuit.rx.helper import uniform_measure_of_event
from random_events.interval import closed
from random_events.product_algebra import Event, SimpleEvent
from typing_extensions import List

from krrood.entity_query_language.entity import entity, let
from krrood.entity_query_language.quantify_entity import an
from krrood.ormatic.utils import classproperty
from .mixins import (
    HasBody,
    HasSupportingSurface,
    HasRegion,
    HasDrawers,
    HasDoors,
    HasHandle,
    HasCase,
    HasHinge,
    HasActiveConnection,
    HasRevoluteConnection,
    HasLeftRightDoor,
    HasSlider,
    HasHoles,
)
from ..datastructures.prefixed_name import PrefixedName
from ..datastructures.variables import SpatialVariables
from ..exceptions import InvalidPlaneDimensions
from ..reasoning.predicates import InsideOf
from ..spatial_types import Point3, TransformationMatrix, Vector3
from ..spatial_types.derivatives import DerivativeMap
from ..utils import Direction
from ..world import World
from ..world_description.connections import FixedConnection, RevoluteConnection
from ..world_description.degree_of_freedom import DegreeOfFreedom
from ..world_description.geometry import Scale
from ..world_description.shape_collection import BoundingBoxCollection, ShapeCollection
from ..world_description.world_entity import (
    SemanticAnnotation,
    Body,
    KinematicStructureEntity,
)


@dataclass(eq=False)
class IsPerceivable:
    """
    A mixin class for semantic annotations that can be perceived.
    """

    class_label: Optional[str] = field(default=None, kw_only=True)
    """
    The exact class label of the perceived object.
    """


@dataclass(eq=False)
class Handle(HasBody):

    @classmethod
    def create_with_new_body_in_world(
        cls,
        name: PrefixedName,
        world: World,
        parent: KinematicStructureEntity,
        parent_T_self: Optional[TransformationMatrix] = None,
        *,
        scale: Scale = Scale(0.1, 0.02, 0.02),
        thickness: float = 0.005,
    ) -> Self:
        handle_event = cls._create_handle_geometry(scale=scale).as_composite_set()

        inner_box = cls._create_handle_geometry(
            scale=scale, thickness=thickness
        ).as_composite_set()

        handle_event -= inner_box

        handle_body = Body(name=name)
        collision = BoundingBoxCollection.from_event(
            handle_body, handle_event
        ).as_shapes()
        handle_body.collision = collision
        handle_body.visual = collision
        return cls._create_with_fixed_connection_in_world(
            name, world, handle_body, parent, parent_T_self
        )

    @classmethod
    def _create_handle_geometry(
        cls, scale: Scale, thickness: float = 0.0
    ) -> SimpleEvent:
        """
        Create a box event representing the handle.

        :param scale: The scale of the handle.
        :param thickness: The thickness of the handle walls.
        """

        x_interval = closed(0, scale.x - thickness)
        y_interval = closed(
            -scale.y / 2 + thickness,
            scale.y / 2 - thickness,
        )

        z_interval = closed(-scale.z / 2, scale.z / 2)

        return SimpleEvent(
            {
                SpatialVariables.x.value: x_interval,
                SpatialVariables.y.value: y_interval,
                SpatialVariables.z.value: z_interval,
            }
        )


@dataclass(eq=False)
class Fridge(
    HasCase,
    HasDoors,
):
    """
    A semantic annotation representing a fridge that has a door and a body.
    """

    @classproperty
    def opening_direction(self) -> Direction:
        return Direction.NEGATIVE_X


@dataclass(eq=False)
class Aperture(HasRegion):
    """
    A semantic annotation that represents an opening in a physical entity.
    An example is like a hole in a wall that can be used to enter a room.
    """


@dataclass(eq=False)
class Hinge(HasBody):
    """
    A hinge is a physical entity that connects two bodies and allows one to rotate around a fixed axis.
    """


@dataclass(eq=False)
class Slider(HasBody):
    """
    A Slider is a physical entity that connects two bodies and allows one to linearly translate along a fixed axis.
    """


@dataclass(eq=False)
class Door(HasBody, HasHandle, HasHinge):
    """
    A door is a physical entity that has covers an opening, has a movable body and a handle.
    """

    @classmethod
    def create_with_new_body_in_world(
        cls,
        name: PrefixedName,
        world: World,
        parent: KinematicStructureEntity,
        parent_T_self: Optional[TransformationMatrix] = None,
        *,
        scale: Scale = Scale(0.03, 1, 2),
    ) -> Self:
        if not (scale.x < scale.y and scale.x < scale.z):
            raise InvalidPlaneDimensions(scale)

        door_event = scale.to_simple_event().as_composite_set()
        door_body = Body(name=name)
        bounding_box_collection = BoundingBoxCollection.from_event(
            door_body, door_event
        )
        collision = bounding_box_collection.as_shapes()
        door_body.collision = collision
        door_body.visual = collision
        return cls._create_with_fixed_connection_in_world(
            name, world, door_body, parent, parent_T_self
        )


@dataclass(eq=False)
class DoubleDoor(SemanticAnnotation, HasLeftRightDoor):
    """
    A semantic annotation that represents a double door with left and right doors.
    """


@dataclass(eq=False)
class Drawer(HasCase, HasHandle, HasSlider):

    @property
    def opening_direction(self) -> Direction:
        return Direction.Z


############################### subclasses to Furniture
@dataclass(eq=False)
class Furniture(SemanticAnnotation, ABC): ...


@dataclass(eq=False)
class Table(Furniture, HasBody):
    """
    A semantic annotation that represents a table.
    """

    def points_on_table(self, amount: int = 100) -> List[Point3]:
        """
        Get points that are on the table.

        :amount: The number of points to return.
        :returns: A list of points that are on the table.
        """
        area_of_table = BoundingBoxCollection.from_shapes(self.body.collision)
        event = area_of_table.event
        p = uniform_measure_of_event(event)
        p = p.marginal(SpatialVariables.xy)
        samples = p.sample(amount)
        z_coordinate = np.full(
            (amount, 1), max([b.max_z for b in area_of_table]) + 0.01
        )
        samples = np.concatenate((samples, z_coordinate), axis=1)
        return [Point3(*s, reference_frame=self.body) for s in samples]


@dataclass(eq=False)
class Cabinet(HasCase, Furniture, HasDrawers, HasDoors):
    @property
    def opening_direction(self) -> Direction:
        return Direction.NEGATIVE_X


@dataclass(eq=False)
class Dresser(HasCase, Furniture, HasDrawers, HasDoors):
    @property
    def opening_direction(self) -> Direction:
        return Direction.NEGATIVE_X


@dataclass(eq=False)
class Cupboard(HasCase, Furniture, HasDoors):
    @property
    def opening_direction(self) -> Direction:
        return Direction.NEGATIVE_X


@dataclass(eq=False)
class Wardrobe(HasCase, Furniture, HasDrawers, HasDoors):
    @property
    def opening_direction(self) -> Direction:
        return Direction.NEGATIVE_X


@dataclass(eq=False)
class Floor(HasSupportingSurface):

    @classmethod
    def create_with_new_body_in_world(
        cls,
        name: PrefixedName,
        world: World,
        parent: KinematicStructureEntity,
        parent_T_self: Optional[TransformationMatrix] = None,
        *,
        scale: Scale = Scale(),
    ) -> Self:
        """
        Create a Floor semantic annotation with a new body defined by the given scale.

        :param name: The name of the floor body.
        :param scale: The scale defining the floor polytope.
        """
        polytope = scale.to_bounding_box().get_points()
        self = cls.create_with_new_body_from_polytope(
            name=name, floor_polytope=polytope
        )
        self._create_with_fixed_connection_in_world(
            name, world, self.body, parent, parent_T_self
        )
        return self

    @classmethod
    def create_with_new_body_from_polytope(
        cls, name: PrefixedName, floor_polytope: List[Point3]
    ) -> Self:
        """
        Create a Floor semantic annotation with a new body defined by the given list of Point3.

        :param name: The name of the floor body.
        :param floor_polytope: A list of 3D points defining the floor poly
        """
        room_body = Body.from_3d_points(name=name, points_3d=floor_polytope)
        return cls(body=room_body)


@dataclass(eq=False)
class Room(SemanticAnnotation):
    """
    A semantic annotation that represents a closed area with a specific purpose
    """

    floor: Floor
    """
    The room's floor.
    """


@dataclass(eq=False)
class Wall(HasBody, HasHoles):

    @classmethod
    def create_with_new_body_in_world(
        cls,
        name: PrefixedName,
        world: World,
        parent: KinematicStructureEntity,
        parent_T_self: Optional[TransformationMatrix] = None,
        *,
        scale: Scale = Scale(),
    ) -> Self:
        if not (scale.x < scale.y and scale.x < scale.z):
            raise InvalidPlaneDimensions(scale)

        wall_body = Body(name=name)
        wall_event = cls._create_wall_event(scale).as_composite_set()
        wall_collision = BoundingBoxCollection.from_event(
            wall_body, wall_event
        ).as_shapes()

        wall_body.collision = wall_collision
        wall_body.visual = wall_collision

        return cls._create_with_fixed_connection_in_world(
            name, world, wall_body, parent, parent_T_self
        )

    @property
    def doors(self) -> Iterable[Door]:
        door = let(Door, self._world.semantic_annotations)
        query = an(entity(door), InsideOf(self.body, door.entry_way.region)() > 0.1)
        return query.evaluate()

    @classmethod
    def _create_wall_event(cls, scale: Scale) -> SimpleEvent:
        """
        Return the collision shapes for the wall. A wall event is created based on the scale of the wall, and
        doors are removed from the wall event. The resulting bounding box collection is converted to shapes.
        """

        x_interval = closed(-scale.x / 2, scale.x / 2)
        y_interval = closed(-scale.y / 2, scale.y / 2)
        z_interval = closed(0, scale.z)

        return SimpleEvent(
            {
                SpatialVariables.x.value: x_interval,
                SpatialVariables.y.value: y_interval,
                SpatialVariables.z.value: z_interval,
            }
        )
