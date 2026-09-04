from __future__ import annotations

from abc import ABC
from copy import deepcopy
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Any

import numpy as np
import numpy.typing as npt
import trimesh.boolean
from trimesh.collision import CollisionManager
from typing_extensions import List, TYPE_CHECKING, Iterable, Type

from krrood.entity_query_language.predicate import (
    Predicate,
    RenderedFields,
    Symbol,
    SymbolicFunction,
    symbolic_callable_to_function,
    symbolic_function,
    Triple,
)
from krrood.entity_query_language.utils import camel_case_to_words
from krrood.entity_query_language.verbalization.fragments.base import (
    VerbalizationFragment,
)
from krrood.entity_query_language.verbalization.vocabulary.english import Prepositions
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
from semantic_digital_twin.datastructures.types import NpMatrix4x4
from semantic_digital_twin.spatial_types import Vector3, Point3, math
from semantic_digital_twin.spatial_types.numeric import NumericTransform
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
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
        # the same reading as Below(), taken numerically: a detector tick asks this of
        # every candidate pair in the world, and building a symbolic relation per pair
        # does not hold the tick budget
        rests_below = (
            ViewDependentSpatialRelation.signed_distance_along_axis(
                self.supported.numeric_global_transform.to_np(),
                ViewAxis.VERTICAL,
                self.supported.numeric_center_of_mass.to_np(),
                self.supporting.numeric_center_of_mass.to_np(),
                VIEW_DIRECTION_EPS,
            )
            < 0.0
        )
        if rests_below:
            return False

        supported_origin = NumericTransform.identity(self.supported)
        boxes_of_supported = (
            self.supported.collision.as_bounding_box_collection_at_origin(
                supported_origin
            )
        )
        boxes_of_supporting = (
            self.supporting.collision.as_bounding_box_collection_at_origin(
                supported_origin
            )
        )
        # bodies whose enclosing regions miss each other cannot intersect box by box
        # either, and most candidate pairs a detector tick asks about are such a pair
        if not boxes_of_supported.enclosing_bounds.overlaps(
            boxes_of_supporting.enclosing_bounds
        ):
            return False

        intersection = (
            boxes_of_supported.event & boxes_of_supporting.event
        ).bounding_box()

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


@dataclass(eq=False)
class InsideRegion(Triple):
    """
    Whether a body lies in a region, by what fraction of its collision volume falls
    inside the region's area.

    How much counts as inside is a judgement rather than a measurement, so the fraction
    is what :meth:`compute_contained_fraction` answers and
    :attr:`minimum_contained_fraction` is where the judgement is stated.
    """

    body: Body
    """
    The body that may be in the region.
    """

    region: Region
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

    def compute_contained_fraction(self) -> float:
        """
        :return: The fraction (0.0..1.0) of the body's volume lying in the region.
        """
        # a body whose enclosing region misses the region's own shares no volume with
        # it, and the exact boolean below is far too dear to reach for such a pair
        if not self.body.numeric_global_bounds.overlaps(
            self.region.numeric_global_bounds
        ):
            return 0.0

        # Retrieve meshes in local frames
        local_body_mesh = self.body.collision.combined_mesh
        local_region_mesh = self.region.area.combined_mesh

        # Transform copies of the meshes into the world frame
        body_mesh = local_body_mesh.copy().apply_transform(
            self.body.numeric_global_transform.to_np()
        )
        region_mesh = local_region_mesh.copy().apply_transform(
            self.region.numeric_global_transform.to_np()
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
class PointSpatialRelation(Predicate, ABC):
    """
    Check if the point is spatially related to the other point.
    """

    point: Point3
    """
    The point for which the check should be done.
    """

    other: Point3
    """
    The other point.
    """


VIEW_DIRECTION_EPS = 1e-12
"""
Guards a point of view's direction against division by a degenerate axis.
"""


class ViewAxis(IntEnum):
    """
    Axis of a point of view that a spatial relation is measured along.
    """

    DEPTH = 0
    """
    Points ahead of the point of view; behind and in front of are measured along it.
    """

    LATERAL = 1
    """
    Points to the point of view's side; left of and right of are measured along it.
    """

    VERTICAL = 2
    """
    Points up from the point of view; above and below are measured along it.
    """


@dataclass(eq=False)
class ViewDependentSpatialRelation(PointSpatialRelation, ABC):
    """
    A spatial relation between two points, read from somewhere in particular.

    Which way is left, above or in front depends on where it is being seen from, so the
    relation carries that spot as an operand of its own.
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

    point_of_view: HomogeneousTransformationMatrix
    """
    The reference spot from where to look at the bodies.
    """
    eps: float = VIEW_DIRECTION_EPS
    """
    A small value to avoid division by zero.
    """
    spatial_relation_result: bool = False

    def _signed_distance_along_direction(self, index: ViewAxis) -> float:
        """
        Calculate the spatial relation between self.point and self.other with respect to
        a given reference point (self.point_of_semantic_annotation) and a specified axis
        index. This function computes the signed distance along a specified direction
        derived from the reference point to compare the positions.

        :param index: The index of the axis in the transformation matrix along which the
            spatial relation is computed.
        :return: The signed distance between the first and the second points along the
            given direction.
        """
        return self.signed_distance_along_axis(
            self.point_of_view.to_np(),
            index,
            self.point.to_np(),
            self.other.to_np(),
            self.eps,
        )

    @staticmethod
    def signed_distance_along_axis(
        reference_T_point_of_view: NpMatrix4x4,
        axis: ViewAxis,
        point: npt.NDArray[np.float64],
        other: npt.NDArray[np.float64],
        eps: float,
    ) -> float:
        """
        How far ``point`` lies past ``other`` along one axis of a point of view.

        Works entirely in numpy, so a caller holding numeric geometry never has to build
        a symbolic expression to compare two positions.

        :param reference_T_point_of_view: The spot the two points are looked at from.
        :param axis: Which of the point of view's axes to measure along.
        :param point: The point being placed, as a homogeneous coordinate.
        :param other: The point it is placed relative to, as a homogeneous coordinate.
        :param eps: Guards against dividing by a degenerate axis of length zero.
        """
        direction = reference_T_point_of_view[:3, axis]
        direction = direction / (np.linalg.norm(direction) + eps)
        return float(direction @ (point[:3] - other[:3]))


@dataclass(eq=False)
class LeftOf(ViewDependentSpatialRelation):
    """
    The "left" direction is taken as the -Y axis of the given point of
    semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = (
            self._signed_distance_along_direction(ViewAxis.LATERAL) > 0.0
        )
        return self.spatial_relation_result


@dataclass(eq=False)
class RightOf(ViewDependentSpatialRelation):
    """
    The "right" direction is taken as the +Y axis of the given point of
    semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = (
            self._signed_distance_along_direction(ViewAxis.LATERAL) < 0.0
        )
        return self.spatial_relation_result


@dataclass(eq=False)
class Above(ViewDependentSpatialRelation):
    """
    The "above" direction is taken as the +Z axis of the given point of
    semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = (
            self._signed_distance_along_direction(ViewAxis.VERTICAL) > 0.0
        )
        return self.spatial_relation_result


@dataclass(eq=False)
class Below(ViewDependentSpatialRelation):
    """
    The "below" direction is taken as the -Z axis of the given point of
    semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = (
            self._signed_distance_along_direction(ViewAxis.VERTICAL) < 0.0
        )
        return self.spatial_relation_result


@dataclass(eq=False)
class Behind(ViewDependentSpatialRelation):
    """
    The "behind" direction is defined as the -X axis of the given point of semantic
    annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = (
            self._signed_distance_along_direction(ViewAxis.DEPTH) < 0.0
        )
        return self.spatial_relation_result


@dataclass(eq=False)
class InFrontOf(ViewDependentSpatialRelation):
    """
    The "in front of" direction is defined as the +X axis of the given point of semantic
    annotation.
    """

    def __call__(self) -> bool:
        self.result = self._signed_distance_along_direction(ViewAxis.DEPTH) > 0.0
        return self.result


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

        Both bodies' geometry is carried into the world frame as plain coordinates, so
        neither the meshes themselves nor a box enclosing them is ever built.
        """
        body_mesh = self.body.combined_mesh
        if body_mesh is None or body_mesh.is_empty:
            return 0.0

        world_P_body = self.body.numeric_global_transform.transform_points(
            body_mesh.vertices
        )
        inside = self.other.numeric_global_bounds.contains(world_P_body)
        if len(inside) == 0:
            return 0.0
        return float(inside.sum()) / len(inside)

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
