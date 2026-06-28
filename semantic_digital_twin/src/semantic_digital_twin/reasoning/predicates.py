from __future__ import annotations

from abc import ABC
from copy import deepcopy
from dataclasses import dataclass

import numpy as np
import trimesh.boolean
from trimesh.collision import CollisionManager
from typing_extensions import List, Self, TYPE_CHECKING, Iterable, Type

from krrood.entity_query_language.predicate import (
    Predicate,
    SymbolicFunction,
    Symbol,
    functional_form,
)
from krrood.entity_query_language.verbalization.fragments.base import WordFragment
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Adjective,
    All,
    clause,
    Copula,
    Noun,
    Preposition,
    Verb,
)
from random_events.interval import Interval
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.datastructures.variables import SpatialVariables
from semantic_digital_twin.spatial_computations.ik_solver import (
    MaxIterationsException,
    UnreachableException,
)
from semantic_digital_twin.spatial_computations.raytracer import RayTracer
from semantic_digital_twin.spatial_types import Vector3, Point3
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import BoundingBox
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
    """Whether an object is stable in the world.

    Stable means its position will not change after simulating physics in the world (simulating for
    10 seconds and comparing the coordinates before and after).
    """

    body: Body
    """The body whose stability is checked."""

    def __call__(self) -> bool:
        raise NotImplementedError("Needs multiverse")

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "<body> is stable" -- an adjective, so the name-based verb-first default would read wrong.
        return clause(Noun(operands.body), Copula(), Adjective("stable"))


stable = functional_form(Stable)


@dataclass(eq=False)
class Contact(Predicate):
    """Whether two bodies are in contact."""

    body1: Body
    """The first body."""

    body2: Body
    """The second body."""

    threshold: float = 0.001
    """The maximum distance at which the two bodies count as in contact."""

    def __call__(self) -> bool:
        tcd = self.body1._world.collision_manager.collision_detector
        result = tcd.check_collision_between_bodies(self.body1, self.body2)

        if result is None:
            return False
        return result.distance < self.threshold

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "<body1> is in contact with <body2>" -- a copular relation read with prepositions.
        return clause(
            Noun(operands.body1),
            Copula(),
            Preposition.IN,
            WordFragment(text="contact"),  # bare noun -- "in contact", not "in a contact"
            Preposition.WITH,
            Noun(operands.body2),
        )


contact = functional_form(Contact)


@dataclass(eq=False)
class GetVisibleBodies(SymbolicFunction):
    """The bodies and regions visible from a camera, computed from a segmentation mask."""

    camera: Camera
    """The camera the visible bodies are seen from."""

    def __call__(self) -> List[KinematicStructureEntity]:
        camera = self.camera
        rt = RayTracer(camera._world)
        rt.update_scene()

        # This ignores the camera orientation and sets it to identity
        cam_pose = np.eye(4, dtype=float)
        cam_pose[:3, 3] = camera.root.global_transform.to_np()[:3, 3]

        seg = rt.create_segmentation_mask(
            HomogeneousTransformationMatrix(
                cam_pose, reference_frame=camera._world.root
            ),
            resolution=256,
            min_distance=0.2,
        )
        indices = np.unique(seg)
        indices = indices[indices > -1]
        bodies = [camera._world.kinematic_structure[i] for i in indices]

        return bodies


get_visible_bodies = functional_form(GetVisibleBodies)


@dataclass(eq=False)
class Visible(Predicate):
    """Whether a body or region is visible from a camera."""

    camera: Camera
    """The camera the visibility is checked from."""

    object: KinematicStructureEntity
    """The body or region whose visibility is checked."""

    def __call__(self) -> bool:
        return self.object in get_visible_bodies(self.camera)

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "<object> is visible from <camera>" -- an adjective relation with a preposition.
        return clause(
            Noun(operands.object),
            Copula(),
            Adjective("visible"),
            Preposition.FROM,
            Noun(operands.camera),
        )


visible = functional_form(Visible)


@dataclass(eq=False)
class OccludingBodies(SymbolicFunction):
    """The bodies that occlude a given body in the scene as seen from a camera.

    Determined by ray tracing: every body that hides anything from the target body is occluding it.
    """

    camera: Camera
    """The camera the occlusion is seen from."""

    body: Body
    """The body whose occluders are computed."""

    def __call__(self) -> List[Body]:
        camera = self.camera
        body = self.body

        # get camera pose
        camera_pose = np.eye(4, dtype=float)
        camera_pose[:3, 3] = camera.root.global_transform.to_np()[:3, 3]
        camera_pose = HomogeneousTransformationMatrix(
            camera_pose, reference_frame=camera._world.root
        )

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
                camera_pose, resolution=256, min_distance=0.1
            )
        )

        # get segmentation mask with occlusion
        ray_tracer_with_occlusion = RayTracer(camera._world)
        ray_tracer_with_occlusion.update_scene()
        segmentation_mask_with_occlusion = (
            ray_tracer_with_occlusion.create_segmentation_mask(
                camera_pose, resolution=256, min_distance=0.1
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


occluding_bodies = functional_form(OccludingBodies)


@dataclass(eq=False)
class Reachable(Predicate):
    """Whether a kinematic chain can reach a given pose, determined by inverse kinematics."""

    pose: HomogeneousTransformationMatrix
    """The pose to reach."""

    root: Body
    """The root of the kinematic chain."""

    tip: Body
    """The tip (end effector) of the kinematic chain."""

    def __call__(self) -> bool:
        try:
            self.root._world.compute_inverse_kinematics(
                root=self.root, tip=self.tip, target=self.pose, max_iterations=1000
            )
        except MaxIterationsException:
            return False
        except UnreachableException:
            return False
        return True

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "<pose> is reachable by <tip>" -- an adjective relation; the reacher is the tip operand.
        return clause(
            Noun(operands.pose),
            Copula(),
            Adjective("reachable"),
            Preposition.BY,
            Noun(operands.tip),
        )


reachable = functional_form(Reachable)


@dataclass(eq=False)
class EuclideanPlanarDistance(SymbolicFunction):
    """The Euclidean distance between two bodies in a plane, ignoring one dimension.

    The ignored dimension is set to zero on both positions before the distance is computed, so the
    calculation is restricted to the chosen spatial plane.
    """

    body1: Body
    """The first body, whose global pose gives its position."""

    body2: Body
    """The second body, whose global pose gives its position."""

    ignore_dimension: Vector3
    """The dimension (x, y or z) set to zero before the distance is computed."""

    def __call__(self):
        body1_position = self.body1.global_pose.to_position()
        body2_position = self.body2.global_pose.to_position()

        if np.allclose(self.ignore_dimension, Vector3.X()):
            body1_position.x = 0.0
            body2_position.x = 0.0
        elif np.allclose(self.ignore_dimension, Vector3.Y()):
            body1_position.y = 0.0
            body2_position.y = 0.0
        elif np.allclose(self.ignore_dimension, Vector3.Z()):
            body1_position.z = 0.0
            body2_position.z = 0.0

        return body1_position.euclidean_distance(body2_position)


compute_euclidean_planar_distance = functional_form(EuclideanPlanarDistance)


@dataclass(eq=False)
class IsSupportedBy(Predicate):
    """Whether one object is supported by another object."""

    supported_body: Body
    """The object that is supported."""

    supporting_body: Body
    """The object that potentially supports the first object."""

    max_intersection_height: float = 0.1
    """Maximum height of the intersection between the two objects; above it the check returns False
    due to unhandled clipping."""

    def __call__(self) -> bool:
        if Below(
            self.supported_body.center_of_mass,
            self.supporting_body.center_of_mass,
            self.supported_body.global_transform,
        )():
            return False
        bounding_box_supported_body = (
            self.supported_body.collision.as_bounding_box_collection_at_origin(
                HomogeneousTransformationMatrix(reference_frame=self.supported_body)
            ).event
        )
        bounding_box_supporting_body = (
            self.supporting_body.collision.as_bounding_box_collection_at_origin(
                HomogeneousTransformationMatrix(reference_frame=self.supported_body)
            ).event
        )

        intersection = (
            bounding_box_supported_body & bounding_box_supporting_body
        ).bounding_box()

        if intersection.is_empty():
            return False

        z_intersection: Interval = intersection[SpatialVariables.z.value]
        size = sum([si.upper - si.lower for si in z_intersection.simple_sets])
        return size < self.max_intersection_height


is_supported_by = functional_form(IsSupportedBy)


@dataclass(eq=False)
class IsSupporting(Predicate):
    """Whether any body in the world is supported by a given supporting body.

    Iterates over the bodies in the world and checks each with :class:`IsSupportedBy`; bodies for
    which the computation fails are skipped.
    """

    supporting_body: Body
    """The body checked for supporting any other body in the world."""

    max_intersection_height: float = 0.1
    """The maximum allowable intersection height for a body to count as supported."""

    def __call__(self) -> bool:
        for candidate in self.supporting_body._world.bodies_with_collision:
            if candidate is self.supporting_body:
                continue
            if is_supported_by(
                candidate, self.supporting_body, self.max_intersection_height
            ):
                return True

        return False


is_supporting = functional_form(IsSupporting)


@dataclass(eq=False)
class BodyInRegionFraction(SymbolicFunction):
    """The fraction (0.0..1.0) of a body's collision volume that lies inside a region's volume.

    Both meshes are defined in their local frames and are transformed into a common world frame using
    their global poses before the boolean intersection is computed.
    """

    body: Body
    """The body whose contained volume fraction is computed."""

    region: Region
    """The region the body is tested against."""

    def __call__(self) -> float:
        # Retrieve meshes in local frames
        body_mesh_local = self.body.collision.combined_mesh
        region_mesh_local = self.region.area.combined_mesh

        # Transform copies of the meshes into the world frame
        body_mesh = body_mesh_local.copy().apply_transform(
            self.body.global_transform.to_np()
        )
        region_mesh = region_mesh_local.copy().apply_transform(
            self.region.global_transform.to_np()
        )
        intersection = trimesh.boolean.intersection([body_mesh, region_mesh])

        # no body volume -> zero fraction
        body_volume = body_mesh.volume
        if body_volume <= 1e-12:
            return 0.0

        return intersection.volume / body_volume


is_body_in_region = functional_form(BodyInRegionFraction)


@dataclass
class KinematicStructureEntitySpatialRelation(Symbol, ABC):
    """
    Base class for spatial relations between two KinematicStructureEntity instances.
    Implementations typically compare the centers of mass computed from the KSE's collision geometry.
    """

    body: KinematicStructureEntity
    """
    The KSE for which the check should be done.
    """

    other: KinematicStructureEntity
    """
    The other KSE.
    """


@dataclass
class PointSpatialRelation(Symbol, ABC):
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


@dataclass
class ViewDependentSpatialRelation(PointSpatialRelation, ABC):

    point_of_view: HomogeneousTransformationMatrix
    """
    The reference spot from where to look at the bodies.
    """

    eps: float = 1e-12
    """
    A small value to avoid division by zero.
    """

    spatial_relation_result: bool = False

    def _signed_distance_along_direction(self, index: int) -> float:
        """
        Calculate the spatial relation between self.point and self.other with respect to a given
        reference point (self.point_of_semantic_annotation) and a specified axis index. This function computes the
        signed distance along a specified direction derived from the reference point
        to compare the positions.

        :param index: The index of the axis in the transformation matrix along which
            the spatial relation is computed.
        :return: The signed distance between the first and the second points along the given direction.
        """
        ref_np = self.point_of_view.to_np()
        front_world = ref_np[:3, index]
        front_norm = front_world / (np.linalg.norm(front_world) + self.eps)
        front_norm = Vector3(
            x=front_norm[0],
            y=front_norm[1],
            z=front_norm[2],
            reference_frame=self.point_of_view.reference_frame,
        )

        s_body = front_norm.dot(self.point.to_vector3())
        s_other = front_norm.dot(self.other.to_vector3())
        return (s_body - s_other).compile()()


@dataclass
class LeftOf(ViewDependentSpatialRelation):
    """
    The "left" direction is taken as the -Y axis of the given point of semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = self._signed_distance_along_direction(1) > 0.0
        return self.spatial_relation_result


@dataclass
class RightOf(ViewDependentSpatialRelation):
    """
    The "right" direction is taken as the +Y axis of the given point of semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = self._signed_distance_along_direction(1) < 0.0
        return self.spatial_relation_result


@dataclass
class Above(ViewDependentSpatialRelation):
    """
    The "above" direction is taken as the +Z axis of the given point of semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = self._signed_distance_along_direction(2) > 0.0
        return self.spatial_relation_result


@dataclass
class Below(ViewDependentSpatialRelation):
    """
    The "below" direction is taken as the -Z axis of the given point of semantic_annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = self._signed_distance_along_direction(2) < 0.0
        return self.spatial_relation_result


@dataclass
class Behind(ViewDependentSpatialRelation):
    """
    The "behind" direction is defined as the -X axis of the given point of semantic annotation.
    """

    def __call__(self) -> bool:
        self.spatial_relation_result = self._signed_distance_along_direction(0) < 0.0
        return self.spatial_relation_result


@dataclass
class InFrontOf(ViewDependentSpatialRelation):
    """
    The "in front of" direction is defined as the +X axis of the given point of semantic annotation.
    """

    def __call__(self) -> bool:
        self.result = self._signed_distance_along_direction(0) > 0.0
        return self.result


@dataclass
class InsideOf(KinematicStructureEntitySpatialRelation):
    """
    The "inside of" relation is defined as the fraction of the volume of self.body
    that lies within the bounding box of self.other.

    Readily, `InsideOf(a,b) = 1.` means that `a` is completely inside `b`.
    """

    containment_ratio: float = 0.0

    def __call__(self) -> float:
        self.containment_ratio = self.compute_containment_ratio()
        return self.containment_ratio

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
    def _verbalization_fragment_(cls, operands: Self):
        return clause(
            Noun(operands.iterable),
            Verb("contain"),
            Noun("instance"),
            Preposition.OF,
            Noun(operands.obj_type),
        )


@dataclass(eq=False)
class IsPlaceOccupied(Predicate):
    """Whether a place (a box at a pose) intersects any collidable body in the world.

    The box is converted to a mesh at its pose and tested against each body's world-aligned collision
    mesh with trimesh's collision manager, excluding the allowed bodies.
    """

    box: BoundingBox
    """The place as an axis-aligned box in its own local frame."""

    pose: Pose
    """The pose the box is placed at."""

    world: World
    """The world providing the bodies with enabled collisions."""

    allowed_bodies: List[Body] = None
    """Bodies to ignore during the check."""

    def __call__(self) -> bool:
        allowed_bodies = set(self.allowed_bodies or [])

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
            if body in allowed_bodies:
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


is_place_occupied = functional_form(IsPlaceOccupied)


@dataclass(eq=False)
class AllClose(Predicate):
    """Whether two arrays are element-wise equal within a tolerance (wraps :func:`numpy.allclose`)."""

    array1: np.ndarray
    """The first array."""

    array2: np.ndarray
    """The second array."""

    atol: float = 1e-3
    """The absolute tolerance."""

    def __call__(self) -> bool:
        return np.allclose(self.array1, self.array2, atol=self.atol)

    @classmethod
    def _verbalization_fragment_(cls, operands: Self):
        # "all elements of <array1> are close to <array2>" -- the All quantifier makes the subject
        # "elements" plural and agrees the copula; the morphology pass does the inflection.
        return clause(
            All(),
            Noun("element"),
            Preposition.OF,
            Noun(operands.array1),
            Copula(),
            Adjective("close"),
            Preposition.TO,
            Noun(operands.array2),
        )


allclose = functional_form(AllClose)
