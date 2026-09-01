from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional, Any, Union

import numpy as np
import trimesh.boolean
from trimesh.collision import CollisionManager
from typing_extensions import ClassVar, List, TYPE_CHECKING, Iterable, Tuple, Type

from krrood.entity_query_language.predicate import (
    Predicate,
    RenderedFields,
    Symbol,
    SymbolicFunction,
    symbolic_callable_to_function,
    symbolic_function,
    Relation,
    Triple,
)
from krrood.entity_query_language.utils import camel_case_to_words
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.english import (
    Conjunctions,
    Prepositions,
)
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    clause,
    Copula,
    Noun,
    Verb,
)
from krrood.inheritance_path_length import inheritance_path_length
from random_events.interval import Interval
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.datastructures.variables import SpatialVariables
from semantic_digital_twin.spatial_computations.ik_solver import (
    MaxIterationsException,
    UnreachableException,
)
from semantic_digital_twin.spatial_computations.raytracer import RayTracer
from semantic_digital_twin.spatial_types import Vector3, Point3, math
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.exceptions import RelationStatedAboutNothing
from semantic_digital_twin.world_description.geometry import (
    Color,
    VolumetricBoundingBox,
)
from semantic_digital_twin.world_description.world_entity import (
    Body,
    Region,
    KinematicStructureEntity,
)

if TYPE_CHECKING:
    from semantic_digital_twin.world import World
    from semantic_digital_twin.robots.robot_parts import (
        Camera,
    )


@dataclass(eq=False)
class Stable(Predicate):
    """
    Whether a body stays where it is once physics runs.

    Answered by simulating the world for ten seconds and comparing the body's
    coordinates before and after.
    """

    obj: Body
    """
    The body whose stability is asked about.
    """

    def __call__(self) -> bool:
        raise NotImplementedError("Needs multiverse")

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is stable"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(Noun(fields["obj"]), Copula(), Adjective("stable"))


stable = symbolic_callable_to_function(Stable)
"""
Whether a body stays where it is.

The function spelling of :class:`Stable`.
"""


@dataclass(eq=False)
class InContactWith(Triple):
    """
    Whether two bodies are touching, by how close their collision geometry comes.

    Touching is a judgement about a distance rather than a distance, so the distance is
    what :meth:`compute_distance` answers and :attr:`maximum_distance` is where the
    judgement is stated.
    """

    body1: Body
    """
    The first body.
    """

    body2: Body
    """
    The other body.
    """

    maximum_distance: float = 0.001
    """
    How close the two have to come before they count as touching, in metres.
    """

    @property
    def subject(self) -> Body:
        return self.body1

    @property
    def object(self) -> Body:
        return self.body2

    def __call__(self) -> bool:
        distance = self.compute_distance()
        return distance is not None and distance < self.maximum_distance

    def compute_distance(self) -> Optional[float]:
        """
        :return: How far apart the two bodies' collision geometry is, or ``None`` when
            the collision detector reports no result for the pair at all.
        """
        detector = self.body1._world.collision_manager.collision_detector
        result = detector.check_collision_between_bodies(self.body1, self.body2)
        if result is None:
            return None
        return result.distance

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is in contact with the other body"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["body1"]),
            Copula(),
            Prepositions.IN,
            Noun.bare("contact"),
            Prepositions.WITH,
            Noun(fields["body2"]),
        )


contact = symbolic_callable_to_function(InContactWith)
"""
Whether two bodies are touching.

The function spelling of :class:`InContactWith`.
"""


@symbolic_function
def get_visible_bodies(camera: Camera) -> List[KinematicStructureEntity]:
    """
    Get all bodies and regions that are visible from the given camera using a
    segmentation mask.

    :param camera: The camera for which the visible objects should be returned
    :return: A list of bodies/regions that are visible from the camera
    """
    rt = RayTracer(camera._world)
    rt.update_scene()

    seg = rt.create_segmentation_mask(
        camera.root_T_forward_view,
        resolution=256,
        min_distance=0.2,
        field_of_view=camera.field_of_view,
    )
    indices = np.unique(seg)
    indices = indices[indices > -1]
    bodies = [camera._world.kinematic_structure[i] for i in indices]

    return bodies


@dataclass(eq=False)
class VisibleTo(Triple):
    """
    Whether a camera can see something.
    """

    obj: KinematicStructureEntity
    """
    The thing that may be in view.
    """

    camera: Camera
    """
    The camera looking.
    """

    @property
    def subject(self) -> KinematicStructureEntity:
        return self.obj

    @property
    def object(self) -> Camera:
        return self.camera

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the thing is visible to the camera"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["obj"]),
            Copula(),
            Adjective("visible"),
            Prepositions.TO,
            Noun(fields["camera"]),
        )

    def __call__(self) -> bool:
        return self.obj in get_visible_bodies(self.camera)


def visible(camera: Camera, obj: KinematicStructureEntity) -> bool:
    """
    Whether a body or region is visible to a camera.

    Keeps the camera first, as every caller writes it, where the relation reads the
    other way round -- the thing is visible *to* the camera.

    :param camera: The camera looking.
    :param obj: The thing that may be in view.
    """
    return symbolic_callable_to_function(VisibleTo)(obj=obj, camera=camera)


@symbolic_function
def occluding_bodies(camera: Camera, body: Body) -> List[Body]:
    """
    Determines the bodies that occlude a given body in the scene as seen from a
    specified camera.

    This function uses a ray-tracing approach to check occlusion. Every body that hides
    anything from the target body is an occluding body.

    :param camera: The camera for which the occluding bodies should be returned
    :param body: The body for which the occluding bodies should be returned
    :return: A list of bodies that are occluding the given body.
    """
    camera_pose = camera.root_T_forward_view

    # create a world only containing the target body
    world_without_occlusion = deepcopy(body._world)
    root = Body(name=PrefixedName("root"))
    with world_without_occlusion.modify_world():
        world_without_occlusion.clear()
        world_without_occlusion.add_body(root)
        copied_body = Body.from_json(body.to_json())
        root_T_body = body.global_transform
        root_T_body.reference_frame = root
        root_to_copied_body = FixedConnection(
            parent=root,
            child=copied_body,
            parent_T_connection_expression=root_T_body,
        )
        world_without_occlusion.add_connection(root_to_copied_body)

    # get segmentation mask without occlusion
    ray_tracer_without_occlusion = RayTracer(world_without_occlusion)
    ray_tracer_without_occlusion.update_scene()
    segmentation_mask_without_occlusion = (
        ray_tracer_without_occlusion.create_segmentation_mask(
            camera_pose,
            resolution=256,
            min_distance=0.1,
            field_of_view=camera.field_of_view,
        )
    )

    # get segmentation mask with occlusion
    ray_tracer_with_occlusion = RayTracer(camera._world)
    ray_tracer_with_occlusion.update_scene()
    segmentation_mask_with_occlusion = (
        ray_tracer_with_occlusion.create_segmentation_mask(
            camera_pose,
            resolution=256,
            min_distance=0.1,
            field_of_view=camera.field_of_view,
        )
    )

    # pixels where the target body is visible when nothing else is in the scene
    target_pixels = segmentation_mask_without_occlusion == copied_body.index

    # whatever covers those pixels in the real scene (except the target itself)
    # is occluding the target
    indices = np.unique(segmentation_mask_with_occlusion[target_pixels])
    indices = indices[(indices > -1) & (indices != body.index)]
    bodies = [camera._world.kinematic_structure[i] for i in indices]
    return bodies


@dataclass(eq=False)
class Reachable(Predicate):
    """
    Whether a kinematic chain can put its tip at a pose, answered by inverse kinematics.
    """

    pose: HomogeneousTransformationMatrix
    """
    The pose to reach.
    """

    root: Body
    """
    The root of the kinematic chain.
    """

    tip: Body
    """
    The end of the kinematic chain that has to arrive at the pose.
    """

    maximum_iterations: int = 1000
    """
    How long the solver may search before the pose counts as out of reach.
    """

    def __call__(self) -> bool:
        try:
            self.root._world.compute_inverse_kinematics(
                root=self.root,
                tip=self.tip,
                target=self.pose,
                max_iterations=self.maximum_iterations,
            )
        except (MaxIterationsException, UnreachableException):
            return False
        return True

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the pose is reachable by the tip"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["pose"]),
            Copula(),
            Adjective("reachable"),
            Prepositions.BY,
            Noun(fields["tip"]),
        )


reachable = symbolic_callable_to_function(Reachable)
"""
Whether a kinematic chain can put its tip at a pose.

The function spelling of
:class:`Reachable`.
"""


@symbolic_function
def compute_euclidean_planar_distance(
    body1: Body, body2: Body, ignore_dimension: Vector3
):
    """
    Computes the Euclidean distance between two bodies in 2D space, ignoring a specific
    dimension specified by the user. The ignored dimension is set to zero before the
    distance calculation. This function can be used to handle scenarios where
    computations are restricted to certain spatial planes.

    :param body1: The first body to compute the distance from. It uses the global pose
        of the body to extract the position.
    :param body2: The second body to compute the distance to. It also utilizes the
        global pose of the body to extract the position.
    :param ignore_dimension: Specifies which dimension (x, y, or z) should be ignored in
        the computation. The ignored dimension is set to zero for both positions prior
        to calculating the distance.
    :return: The Euclidean distance between the two bodies in the 2D plane after
        ignoring the specified dimension.
    """
    body1_position = body1.global_pose.to_position()
    body2_position = body2.global_pose.to_position()

    if np.allclose(ignore_dimension, Vector3.X()):
        body1_position.x = 0.0
        body2_position.x = 0.0
    elif np.allclose(ignore_dimension, Vector3.Y()):
        body1_position.y = 0.0
        body2_position.y = 0.0
    elif np.allclose(ignore_dimension, Vector3.Z()):
        body1_position.z = 0.0
        body2_position.z = 0.0

    return body1_position.euclidean_distance(body2_position)


@dataclass(eq=False)
class SupportedBy(Triple):
    """
    Whether one body rests on another.

    Read from how far the two bodies' bounding boxes overlap vertically: enough overlap
    is unhandled clipping rather than support, which is what
    :attr:`maximum_intersection_height` draws the line at.
    """

    supported: Body
    """
    The body that may be resting.
    """

    supporting: Body
    """
    The body that may be holding it up.
    """

    maximum_intersection_height: float = 0.1
    """
    How far the two may overlap vertically, in metres, before the reading is refused as
    unhandled clipping.
    """

    @property
    def subject(self) -> Body:
        return self.supported

    @property
    def object(self) -> Body:
        return self.supporting

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the supported body is supported by the supporting body"*.

        :attr:`maximum_intersection_height` is a tolerance of the reading rather than
        part of the claim, so it is left unspoken.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["supported"]),
            Copula(),
            Adjective("supported"),
            Prepositions.BY,
            Noun(fields["supporting"]),
        )

    def __call__(self) -> bool:
        if Below(
            self.supported.center_of_mass,
            self.supporting.center_of_mass,
            self.supported.global_transform,
        )():
            return False
        supported_bounding_box = (
            self.supported.collision.as_bounding_box_collection_at_origin(
                HomogeneousTransformationMatrix(reference_frame=self.supported)
            ).event
        )
        supporting_bounding_box = (
            self.supporting.collision.as_bounding_box_collection_at_origin(
                HomogeneousTransformationMatrix(reference_frame=self.supported)
            ).event
        )

        intersection = (supported_bounding_box & supporting_bounding_box).bounding_box()

        if intersection.is_empty():
            return False

        z_intersection: Interval = intersection[SpatialVariables.z.value]
        size = sum([si.upper - si.lower for si in z_intersection.simple_sets])
        return size < self.maximum_intersection_height


is_supported_by = symbolic_callable_to_function(SupportedBy)
"""
Whether one body rests on another.

The function spelling of :class:`SupportedBy`.
"""


@dataclass(eq=False)
class Supports(Predicate):
    """
    Whether anything in the world rests on a body.
    """

    supporting_body: Body
    """
    The body that may be holding something up.
    """

    maximum_intersection_height: float = 0.1
    """
    How far two bodies may overlap vertically, in metres, before the reading is refused
    as unhandled clipping.
    """

    def __call__(self) -> bool:
        for candidate in self.supporting_body._world.bodies_with_collision:
            if candidate is self.supporting_body:
                continue
            if SupportedBy(
                candidate, self.supporting_body, self.maximum_intersection_height
            )():
                return True
        return False

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is supporting a body"*, naming what is held up, which the
        class name leaves implicit.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["supporting_body"]),
            Copula(),
            Adjective("supporting"),
            Noun("body"),
        )


is_supporting = symbolic_callable_to_function(Supports)
"""
Whether anything in the world rests on a body.

The function spelling of
:class:`Supports`.
"""

# %% where a relation allows a thing to be

Placed = Union[Point3, Pose, HomogeneousTransformationMatrix, KinematicStructureEntity]
"""
Anything the world can say the place of: a point, a pose, or something standing in it.
"""

AXES: Tuple[SpatialVariables, ...] = VolumetricBoundingBox.axes()
"""
The world's own axes, in the order a bounding box states its bounds along them.
"""

STRAIGHT_ALONG_AN_AXIS = 1e-9
"""
How far a direction may fall short of lying along one of the world's axes and still be
read as lying along it.

A direction is a unit vector, so a component within this of one leaves the other two
within a rounding error of zero.
"""


def position_of(placed: Placed) -> Point3:
    """
    Where something stands.

    :param placed: The point, pose, or thing standing in the world to read.
    """
    if isinstance(placed, Point3):
        return placed
    if isinstance(placed, (Pose, HomogeneousTransformationMatrix)):
        return placed.to_position()
    return placed.global_pose.to_position()


def space_between(
    lower: np.ndarray, upper: np.ndarray, reference_frame: KinematicStructureEntity
) -> VolumetricBoundingBox:
    """
    The stretch of the world between two corners, either of which may be infinite.

    :param lower: The lower corner, as ``(x, y, z)`` in metres.
    :param upper: The upper corner, as ``(x, y, z)`` in metres.
    :param reference_frame: The frame those corners are measured in.
    """
    return VolumetricBoundingBox.from_array_bounds(
        lower,
        upper,
        HomogeneousTransformationMatrix.from_xyz_rpy(reference_frame=reference_frame),
    )


@dataclass(eq=False)
class PlacementRelation(Relation, ABC):
    """
    A relation that says where the thing it is asserted about may be.

    Answering that stretch of the world is what lets a search act on the relation before
    anything has been found: a look reads less picture rather than filtering what it
    read. So a placement relation is read two ways. Stated about something it answers
    whether that thing is where it says; stated about nothing it is the constraint alone
    -- which is why every one of them declares the thing it is about optional, and
    raises rather than guessing when asked whether it holds without one.
    """

    @property
    @abstractmethod
    def allowed_space(self) -> VolumetricBoundingBox:
        """
        The stretch of the world this relation leaves the thing it is about, unbounded
        along every axis it does not constrain.

        Read from the relation's other operands alone, never from that thing, and never
        smaller than what the relation allows: a search may read more than it strictly
        has to, and :meth:`allows` is what settles the rest.
        """

    def allows(self, place: Point3) -> bool:
        """
        Whether something standing at a place satisfies this relation.

        :param place: Where the thing stands.
        """
        return self.allowed_space.contains(place)

    def allowed_part_of(
        self, space: VolumetricBoundingBox
    ) -> Optional[VolumetricBoundingBox]:
        """
        The smallest box holding the part of a stretch of the world this relation
        allows.

        Asked about a stretch that is already bounded rather than about the world, a
        relation can answer more tightly than :attr:`allowed_space` can: a direction
        read from where a camera stands runs across the world's own axes, so no axis-
        aligned box holds everything it allows, while the part of a bounded stretch that
        lies on that side of a thing is itself bounded.

        :param space: The stretch being narrowed.
        :return: The part of it this relation allows, or None where it allows none of
            it.
        """
        return space.intersection_with(self.allowed_space)

    def _stated(self, operand: Optional[Any], name: str) -> Any:
        """
        :param operand: What the statement holds that operand to be.
        :param name: What the relation calls it.
        :raises RelationStatedAboutNothing: If the statement holds it to be nothing.
        :return: The operand.
        """
        if operand is None:
            raise RelationStatedAboutNothing(type(self).__name__, name)
        return operand


@dataclass(eq=False)
class InsideRegion(Triple, PlacementRelation):
    """
    Whether a body lies in a region, by what fraction of its collision volume falls
    inside the region's area.

    How much counts as inside is a judgement rather than a measurement, so the fraction
    is what :meth:`compute_contained_fraction` answers and
    :attr:`minimum_contained_fraction` is where the judgement is stated.
    """

    body: Optional[Body] = None
    """
    The body that may be in the region, or None where the relation is stated about
    nothing and is read as the region alone.
    """

    region: Optional[Region] = None
    """
    The region it may be in.
    """

    minimum_contained_fraction: float = 0.5
    """
    How much of the body has to lie inside the region before it counts as being in it.
    """

    @property
    def subject(self) -> Body:
        return self.body

    @property
    def object(self) -> Region:
        return self.region

    def __call__(self) -> bool:
        return self.compute_contained_fraction() >= self.minimum_contained_fraction

    @property
    def allowed_space(self) -> VolumetricBoundingBox:
        """
        The extent of the region itself, which is where a thing has to stand to be in
        it.
        """
        region = self._stated(self.region, "region")
        return region.area.as_bounding_box_collection_in_frame(
            region.global_transform.reference_frame
        ).bounding_box()

    def compute_contained_fraction(self) -> float:
        """
        :return: The fraction (0.0..1.0) of the body's volume lying in the region.
        """
        # Retrieve meshes in local frames
        local_body_mesh = self._stated(self.body, "body").collision.combined_mesh
        local_region_mesh = self._stated(self.region, "region").area.combined_mesh

        # Transform copies of the meshes into the world frame
        body_mesh = local_body_mesh.copy().apply_transform(
            self.body.global_transform.to_np()
        )
        region_mesh = local_region_mesh.copy().apply_transform(
            self.region.global_transform.to_np()
        )
        intersection = trimesh.boolean.intersection([body_mesh, region_mesh])

        # no body volume -> zero fraction
        body_volume = body_mesh.volume
        if body_volume <= 1e-12:
            return 0.0

        return intersection.volume / body_volume

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is inside the region"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["body"]),
            Copula(),
            Prepositions.INSIDE,
            Noun(fields["region"]),
        )


is_body_in_region = symbolic_callable_to_function(InsideRegion)
"""
Whether a body lies in a region.

The function spelling of :class:`InsideRegion`.
"""


@dataclass(eq=False)
class KinematicStructureEntitySpatialRelation(Predicate, ABC):
    """
    Base class for spatial relations between two KinematicStructureEntity instances.

    Implementations typically compare the centers of mass computed from the KSE's
    collision geometry.
    """

    body: KinematicStructureEntity
    """
    The KSE for which the check should be done.
    """

    other: KinematicStructureEntity
    """
    The other KSE.
    """


@dataclass(eq=False)
class PointSpatialRelation(Triple, PlacementRelation, ABC):
    """
    A relation between the places of two things.

    Either side may be given as a point outright or as something the world places, since
    what the relation reads of each is only where it stands.
    """

    point: Optional[Placed] = None
    """
    The thing the relation is asserted about, or None where it is asserted about nothing
    and read as the stretch of the world it allows.
    """

    other: Optional[Placed] = None
    """
    The thing it is placed with respect to.
    """

    @property
    def subject(self) -> Optional[Placed]:
        return self.point

    @property
    def object(self) -> Optional[Placed]:
        return self.other


@dataclass(eq=False)
class ViewDependentSpatialRelation(PointSpatialRelation, ABC):
    """
    A spatial relation between two places, read from somewhere in particular.

    Which way is left, above or in front depends on where it is being seen from, so the
    relation carries that spot as an operand of its own. Each direction is one axis of
    that spot and one side of it, which is all that tells the six of them apart.
    """

    axis: ClassVar[SpatialVariables]
    """
    The axis of the point of view this direction runs along.
    """

    positive_side: ClassVar[bool]
    """
    Whether the thing has to lie on the positive side of that axis, or the negative one.
    """

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the point is left of the other point, seen from the point of view"*,
        with the direction taken from the relation's own name.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        direction = camel_case_to_words(cls.__name__).lower()
        return clause(
            Noun(fields["point"]),
            Copula(),
            Adjective(direction),
            Noun(fields["other"]),
            Prepositions.FROM,
            Noun(fields["point_of_view"]),
        )

    point_of_view: Optional[HomogeneousTransformationMatrix] = None
    """
    The reference spot from where to look at the bodies.
    """
    eps: float = 1e-12
    """
    A small value to avoid division by zero.
    """
    spatial_relation_result: bool = False

    def __call__(self) -> bool:
        self.spatial_relation_result = self.allows(
            position_of(self._stated(self.point, "point"))
        )
        return self.spatial_relation_result

    def allows(self, place: Point3) -> bool:
        """
        Whether something standing at a place lies this way from the other one.

        Answered exactly, from the signed distance along the direction itself, rather
        than from :attr:`allowed_space`, which is only as tight as an axis-aligned box
        can be about a direction that runs across the world's own axes.

        :param place: Where the thing stands.
        """
        return self._distance_towards(place) > 0.0

    @property
    def allowed_space(self) -> VolumetricBoundingBox:
        """
        Everything on this side of the other thing.

        Bounded on the one axis the direction runs along, and unbounded everywhere else
        -- including on every axis, where the direction runs across the world's own,
        since no box then holds exactly what the relation allows.
        """
        direction = self._direction()
        other = position_of(self._stated(self.other, "other"))
        place = other.to_np()[:3]
        lower, upper = np.full(3, -np.inf), np.full(3, np.inf)
        for index, component in enumerate(direction):
            if abs(abs(component) - 1.0) > STRAIGHT_ALONG_AN_AXIS:
                continue
            if component > 0.0:
                lower[index] = place[index]
            else:
                upper[index] = place[index]
        return space_between(lower, upper, other.reference_frame)

    def allowed_part_of(
        self, space: VolumetricBoundingBox
    ) -> Optional[VolumetricBoundingBox]:
        """
        The part of a stretch of the world that lies on this side of the other thing.

        A direction read from anywhere but straight along the world's own axes leaves a
        half space, which :attr:`allowed_space` can only answer as everything. Cut
        against a stretch that is already bounded it is bounded too, and its corners are
        the corners of that stretch on this side of the dividing plane together with
        wherever that plane crosses its edges.

        :param space: The stretch being narrowed.
        :return: The part of it on this side, or None where none of it is.
        """
        corners = self._corners_of(space)
        if not np.isfinite(corners).all():
            return super().allowed_part_of(space)
        other = position_of(self._stated(self.other, "other")).to_np()[:3]
        beyond = (corners - other) @ self._direction()
        allowed = [*corners[beyond > 0.0], *self._crossings(corners, beyond)]
        if not allowed:
            return None
        return space_between(
            np.min(allowed, axis=0),
            np.max(allowed, axis=0),
            space.origin.reference_frame,
        )

    @staticmethod
    def _corners_of(space: VolumetricBoundingBox) -> np.ndarray:
        """
        :param space: The stretch to read.
        :return: Its eight corners, as ``(8, 3)`` world coordinates in metres, ordered
            so that two differing along one axis alone are an edge of it.
        """
        intervals = (space.x_interval, space.y_interval, space.z_interval)
        return np.array(
            list(
                itertools.product(
                    *((interval.lower, interval.upper) for interval in intervals)
                )
            )
        )

    @staticmethod
    def _crossings(corners: np.ndarray, beyond: np.ndarray) -> List[np.ndarray]:
        """
        Where the plane dividing the two sides crosses the edges of a stretch.

        :param corners: The stretch's corners, as :meth:`_corners_of` orders them.
        :param beyond: How far along the direction each corner lies from the plane.
        :return: One point per edge the plane crosses.
        """
        crossings = []
        for one, other in itertools.combinations(range(len(corners)), 2):
            if bin(one ^ other).count("1") != 1 or beyond[one] * beyond[other] >= 0.0:
                continue
            reached = beyond[one] / (beyond[one] - beyond[other])
            crossings.append(corners[one] + reached * (corners[other] - corners[one]))
        return crossings

    def _direction(self) -> np.ndarray:
        """
        :return: The way, in world coordinates, the thing has to lie from the other one,
            as a unit vector.
        """
        point_of_view = self._stated(self.point_of_view, "point_of_view")
        axis = point_of_view.to_np()[:3, AXES.index(self.axis)]
        towards = 1.0 if self.positive_side else -1.0
        return towards * axis / (np.linalg.norm(axis) + self.eps)

    def _distance_towards(self, place: Point3) -> float:
        """
        :param place: Where the thing stands.
        :return: How far along the direction that place lies from the other thing, in
            metres, negative where it lies against it.
        """
        other = position_of(self._stated(self.other, "other")).to_np()[:3]
        return float(np.dot(self._direction(), place.to_np()[:3] - other))


@dataclass(eq=False)
class LeftOf(ViewDependentSpatialRelation):
    """
    The "left" direction is taken as the +Y axis of the point of view.
    """

    axis: ClassVar[SpatialVariables] = SpatialVariables.y
    positive_side: ClassVar[bool] = True


@dataclass(eq=False)
class RightOf(ViewDependentSpatialRelation):
    """
    The "right" direction is taken as the -Y axis of the point of view.
    """

    axis: ClassVar[SpatialVariables] = SpatialVariables.y
    positive_side: ClassVar[bool] = False


@dataclass(eq=False)
class Above(ViewDependentSpatialRelation):
    """
    The "above" direction is taken as the +Z axis of the point of view.
    """

    axis: ClassVar[SpatialVariables] = SpatialVariables.z
    positive_side: ClassVar[bool] = True


@dataclass(eq=False)
class Below(ViewDependentSpatialRelation):
    """
    The "below" direction is taken as the -Z axis of the point of view.
    """

    axis: ClassVar[SpatialVariables] = SpatialVariables.z
    positive_side: ClassVar[bool] = False


@dataclass(eq=False)
class Behind(ViewDependentSpatialRelation):
    """
    The "behind" direction is taken as the -X axis of the point of view.
    """

    axis: ClassVar[SpatialVariables] = SpatialVariables.x
    positive_side: ClassVar[bool] = False


@dataclass(eq=False)
class InFrontOf(ViewDependentSpatialRelation):
    """
    The "in front of" direction is taken as the +X axis of the point of view.
    """

    axis: ClassVar[SpatialVariables] = SpatialVariables.x
    positive_side: ClassVar[bool] = True


@dataclass(eq=False)
class Between(PlacementRelation):
    """
    Whether something lies between two others.

    Between is the stretch from one to the other, and how far to either side of the line
    joining them still counts is a judgement rather than a measurement, so
    :attr:`maximum_sideways_fraction` is where that judgement is stated.
    """

    body: Optional[Placed] = None
    """
    The thing that may lie between the two, or None where the relation is asserted about
    nothing and read as the stretch it allows.
    """

    one: Optional[Placed] = None
    """
    One of the two it may lie between.
    """

    other: Optional[Placed] = None
    """
    The other of the two.
    """

    maximum_sideways_fraction: float = 0.5
    """
    How far to either side of the line joining the two a thing may lie and still count
    as between them, as a fraction of how far apart they are.

    Half by default, so what counts as between two things is as wide across as they are
    far apart. Stated as a fraction rather than a distance because how wide *between*
    reads is set by the two things themselves: an arm's length apart it is a corridor, a
    millimetre apart it is a point.
    """

    @property
    def subject(self) -> Optional[Placed]:
        return self.body

    def __call__(self) -> bool:
        return self.allows(position_of(self._stated(self.body, "body")))

    def allows(self, place: Point3) -> bool:
        """
        Whether something standing at a place lies between the two.

        Answered exactly: the place has to fall between them along the line joining
        them, and no further from that line than the fraction allows.

        :param place: Where the thing stands.
        """
        one, other = self._places()
        stands_at = place.to_np()[:3]
        line = other - one
        length = float(np.linalg.norm(line))
        if length == 0.0:
            return False
        along = float(np.dot(stands_at - one, line)) / length**2
        if not 0.0 <= along <= 1.0:
            return False
        sideways = float(np.linalg.norm(stands_at - (one + along * line)))
        return sideways <= self.maximum_sideways_fraction * length

    @property
    def allowed_space(self) -> VolumetricBoundingBox:
        """
        The stretch from one to the other, widened to either side by as much as the
        fraction allows a thing to stand off the line joining them.
        """
        one, other = self._places()
        reach = self.maximum_sideways_fraction * float(np.linalg.norm(other - one))
        return space_between(
            np.minimum(one, other) - reach,
            np.maximum(one, other) + reach,
            position_of(self.one).reference_frame,
        )

    def _places(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        :return: Where the two things it may lie between stand, in metres.
        """
        return (
            position_of(self._stated(self.one, "one")).to_np()[:3],
            position_of(self._stated(self.other, "other")).to_np()[:3],
        )

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is between the one and the other"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["body"]),
            Copula(),
            Prepositions.BETWEEN,
            Noun(fields["one"]),
            Conjunctions.AND,
            Noun(fields["other"]),
        )


@dataclass(eq=False)
class Near(Triple, PlacementRelation):
    """
    Whether something stands within a given distance of a place.

    How near is near is the caller's to say rather than the relation's, so
    :attr:`radius` has to be stated.
    """

    body: Optional[Placed] = None
    """
    The thing that may stand near the place, or None where the relation is asserted
    about nothing and read as the stretch it allows.
    """

    place: Optional[Placed] = None
    """
    The place it may stand near, which may be given as a point, a pose, or something the
    world places.
    """

    radius: float = field(kw_only=True)
    """
    How far from that place, in metres, a thing may stand and still be near it.
    """

    @property
    def subject(self) -> Optional[Placed]:
        return self.body

    @property
    def object(self) -> Optional[Placed]:
        return self.place

    def __call__(self) -> bool:
        return self.allows(position_of(self._stated(self.body, "body")))

    def allows(self, place: Point3) -> bool:
        """
        Whether something standing at a place is within the radius of this one.

        Answered exactly, as the distance itself rather than as the box around it.

        :param place: Where the thing stands.
        """
        return float(np.linalg.norm(place.to_np()[:3] - self._place())) <= self.radius

    @property
    def allowed_space(self) -> VolumetricBoundingBox:
        """
        The box the radius reaches into, which is the smallest one holding everything
        within that distance of the place.
        """
        place = position_of(self._stated(self.place, "place"))
        stands_at = place.to_np()[:3]
        return space_between(
            stands_at - self.radius, stands_at + self.radius, place.reference_frame
        )

    def _place(self) -> np.ndarray:
        """
        :return: Where the place it is measured from stands, in metres.
        """
        return position_of(self._stated(self.place, "place")).to_np()[:3]

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is within the radius of the place"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["body"]),
            Copula(),
            Prepositions.WITHIN,
            Noun(fields["radius"]),
            Prepositions.OF,
            Noun(fields["place"]),
        )


@dataclass(eq=False)
class Colored(Triple):
    """
    Whether a body is drawn in a colour.

    What colour a thing is, is knowledge about the thing rather than about whatever
    looks at it, so it is asked of the world the same way a spatial relation is.
    """

    body: Body
    """
    The body whose colour is asked about.
    """

    color: Color
    """
    The colour it may be.
    """

    @property
    def subject(self) -> Body:
        return self.body

    @property
    def object(self) -> Color:
        return self.color

    def __call__(self) -> bool:
        return any(
            shape.color == self.color
            for shape in (*self.body.visual, *self.body.collision)
        )

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is colored the color"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["body"]),
            Copula(),
            Adjective("colored"),
            Noun(fields["color"]),
        )


@dataclass(eq=False)
class InsideOf(KinematicStructureEntitySpatialRelation):
    """
    Whether one thing lies inside another, by what fraction of its volume falls within
    the other's bounding box.

    How much counts as inside is a judgement rather than a measurement, so the fraction
    is what :meth:`compute_containment_ratio` answers and
    :attr:`minimum_containment_ratio` is where the judgement is stated.
    """

    minimum_containment_ratio: float = 0.5
    """
    How much of the body has to lie inside the other before it counts as being in it.

    Half by default: a thing more than half swallowed is in, and one less than half
    swallowed is merely overlapping. Callers that want the fraction itself rather than a
    verdict read :meth:`compute_containment_ratio`.
    """

    containment_ratio: float = 0.0
    """
    What the last call measured, kept so a caller can read it off the relation it just
    evaluated.
    """

    def __call__(self) -> bool:
        self.containment_ratio = self.compute_containment_ratio()
        return self.containment_ratio >= self.minimum_containment_ratio

    def compute_containment_ratio(self) -> float:
        """
        Compute the containment ratio of self.body inside self.other.
        """
        if self.other.combined_mesh is None:
            return 0.0

        # Get meshes in their local (body) frames
        mesh_a_local = self.body.combined_mesh
        mesh_b_local = self.other.combined_mesh

        # Check if either mesh is empty
        if (
            mesh_a_local is None
            or mesh_a_local.is_empty
            or mesh_b_local is None
            or mesh_b_local.is_empty
        ):
            return 0.0

        # Transform meshes from body frame to world frame
        mesh_a = mesh_a_local.copy()
        mesh_a.apply_transform(self.body.global_transform.to_np())

        mesh_b = mesh_b_local.copy()
        mesh_b.apply_transform(self.other.global_transform.to_np())

        # Use bounding box of mesh_b to check if mesh_a is inside mesh_b
        mesh_b_bbox = mesh_b.bounding_box

        if not mesh_b_bbox.is_watertight:
            return 0.0

        inside = mesh_b_bbox.contains(mesh_a.vertices)
        if len(inside) == 0:
            return 0.0
        return sum(inside) / len(inside)

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the body is inside the other"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(
            Noun(fields["body"]),
            Copula(),
            Prepositions.INSIDE,
            Noun(fields["other"]),
        )


@dataclass
class ContainsType(Predicate):
    """
    Predicate that checks if any object in the iterable is of the given type.
    """

    iterable: Iterable
    """
    Iterable to check for objects of the given type.
    """

    obj_type: Type
    """
    Object type to check for.
    """

    def __call__(self) -> bool:
        return any(isinstance(obj, self.obj_type) for obj in self.iterable)

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return clause(
            Noun(fields["iterable"]),
            Verb("contain"),
            Noun("instance"),
            Prepositions.OF,
            Noun(fields["obj_type"]),
        )


@dataclass(eq=False)
class PlaceIsOccupied(Predicate):
    """
    Whether anything already stands in a stretch of the world.

    The stretch is a box at a pose, tested against every collidable body's own collision
    mesh.
    """

    box: VolumetricBoundingBox
    """
    The stretch of space asked about, in its own local frame.
    """

    pose: Pose
    """
    Where that box stands.
    """

    world: World
    """
    The world whose collidable bodies are tested against it.
    """

    allowed_bodies: Optional[List[Body]] = None
    """
    Bodies that may stand there without the place counting as occupied.
    """

    def __call__(self) -> bool:
        ignored = set(self.allowed_bodies or [])

        # Build a mesh for the region box at its current pose
        region_box_shape = self.box.as_shape()  # returns a Box centered at the region
        region_mesh = region_box_shape.mesh.copy()
        region_mesh.apply_transform(
            self.world.transform(self.pose, self.world.root).to_np()
        )

        # Prepare collision manager with the region mesh
        cm = CollisionManager()
        cm.add_object("region", region_mesh)

        # Iterate over collidable bodies and test collision
        for body in self.world.bodies_with_collision:
            if body in ignored:
                continue

            mesh_local = getattr(body.collision, "combined_mesh", None)
            if mesh_local is None or getattr(mesh_local, "is_empty", False):
                continue

            # Transform body mesh into world frame
            body_mesh = mesh_local.copy()
            body_mesh.apply_transform(body.global_pose.to_np())

            # Early exit on first collision
            if cm.in_collision_single(body_mesh):
                return True

        return False

    @classmethod
    def _verbalization_fragment_(cls, fields: RenderedFields) -> VerbalizationFragment:
        """
        Reads as *"the place is occupied"*.

        :param fields: The rendered fragment for each field, keyed by field name.
        """
        return clause(Noun(fields["box"]), Copula(), Adjective("occupied"))


is_place_occupied = symbolic_callable_to_function(PlaceIsOccupied)
"""
Whether anything already stands in a stretch of the world.

The function spelling of
:class:`PlaceIsOccupied`.
"""


@symbolic_function
def allclose(array1: np.ndarray, array2: np.ndarray, atol=1e-3) -> bool:
    """
    Symbolic wrapper around `np.allclose`.
    """
    return np.allclose(array1, array2, atol=atol)
