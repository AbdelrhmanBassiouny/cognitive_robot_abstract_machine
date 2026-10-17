"""
Objects whose parts were split off, stored with their annotations in a database, so that
the next object of the same shape is given those parts without finding them again.

Finding a part, such as the handle of a mug, asks a vision-language model and splitting
it off decomposes the pieces into convex hulls, which takes seconds per object. A
dataset such as RoboCasa loads the same few hundred meshes over and over, often scaled
differently in each scene, so the decomposition is done once per mesh and stored; an
object of the same shape, however it is stretched along each axis, is then given the
stored pieces, stretched to fit.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import trimesh
from numpy.typing import NDArray
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing_extensions import List, Optional, Type

from krrood.ormatic.data_access_objects.helper import to_dao
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.part_finding.relationships import PartRelationshipInspector
from semantic_digital_twin.semantic_annotations.mixins import (
    HasRootBody,
    PartWholeRelationship,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import FixedConnection
from semantic_digital_twin.world_description.geometry import Mesh
from semantic_digital_twin.world_description.inertial_properties import Inertial
from semantic_digital_twin.world_description.mesh_file_storage import MeshFileStorage
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

# %% recognizing a shape however it is scaled


@dataclass
class ShapeFingerprint:
    """
    What identifies the shape of an object's mesh however much it is stretched along
    each axis of its frame, and how far it extends.
    """

    key: str
    """
    A digest of the mesh's triangles and the number of its vertices, which two meshes of
    the same shape share; meshes of different shapes may share it too.
    """

    moments: List[float]
    """
    The means of x, y and z of the mesh's vertices squeezed into the unit cube, of their
    squares and of their products xy, yz and zx, which tell apart meshes of the same
    triangles but different shapes and are the same for every copy of the mesh stretched
    along the axes.
    """

    minimum: List[float]
    """
    The smallest x, y and z of the mesh's vertices.
    """

    maximum: List[float]
    """
    The largest x, y and z of the mesh's vertices.
    """

    tolerance: float = 1e-6
    """
    How much the :attr:`moments` of two fingerprints of the same shape may differ, which
    absorbs the rounding errors of scaling a mesh and of writing it to a file; moving a
    single point of a mesh of a few thousand points by a hundredth of its size changes
    them by more.

    Rounding the squeezed vertices instead would split the fingerprints of a shape with
    a point halfway between two rounding steps.
    """

    @classmethod
    def of_mesh(cls, mesh: trimesh.Trimesh) -> ShapeFingerprint:
        """
        :param mesh: The mesh of an object, in the frame of its root body.
        :return: The fingerprint of the mesh.
        """
        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        minimum, maximum = vertices.min(axis=0), vertices.max(axis=0)
        squeezed = (vertices - minimum) / cls._extent(minimum, maximum)
        digest = hashlib.sha256()
        digest.update(np.asarray(mesh.faces, dtype=np.int64).tobytes())
        digest.update(np.int64(len(vertices)).tobytes())
        products = squeezed * np.roll(squeezed, -1, axis=1)
        return cls(
            key=digest.hexdigest(),
            moments=np.concatenate(
                [
                    squeezed.mean(axis=0),
                    (squeezed**2).mean(axis=0),
                    products.mean(axis=0),
                ]
            ).tolist(),
            minimum=minimum.tolist(),
            maximum=maximum.tolist(),
        )

    def matches(self, other: ShapeFingerprint) -> bool:
        """
        :param other: The fingerprint of another mesh.
        :return: Whether the other mesh is a copy of this one, stretched along the axes.
        """
        return self.key == other.key and np.allclose(
            self.moments, other.moments, rtol=0.0, atol=self.tolerance
        )

    @classmethod
    def of_body(cls, body: Body) -> Optional[ShapeFingerprint]:
        """
        :param body: The root body of an object.
        :return: The fingerprint of the body's meshes, the visual ones if it has any;
            ``None`` if it has no meshes.
        """
        meshes = cls.meshes_of(body.visual) or cls.meshes_of(body.collision)
        if not meshes:
            return None
        return cls.of_mesh(
            trimesh.util.concatenate(
                [
                    shape.mesh.copy().apply_transform(shape.origin.to_np())
                    for shape in meshes
                ]
            )
        )

    @staticmethod
    def meshes_of(shapes: ShapeCollection) -> list[Mesh]:
        """
        The shapes that make up an object, leaving out the boxes and cylinders RoboCasa
        adds to an object's body, such as the liquid a pot holds in some tasks.

        :param shapes: The visual or collision shapes of a body.
        :return: Its meshes.
        """
        return [shape for shape in shapes if isinstance(shape, Mesh)]

    def stretch_to(self, other: ShapeFingerprint) -> NDArray[np.float64]:
        """
        :param other: The fingerprint of a stretched copy of this shape.
        :return: The transformation that maps each point of this shape onto the
            matching point of the copy, as a 4x4 matrix.
        """
        own_minimum, other_minimum = np.array(self.minimum), np.array(other.minimum)
        factors = self._extent(other_minimum, np.array(other.maximum)) / self._extent(
            own_minimum, np.array(self.maximum)
        )
        stretch = np.diag([*factors, 1.0])
        stretch[:3, 3] = other_minimum - factors * own_minimum
        return stretch

    @staticmethod
    def _extent(
        minimum: NDArray[np.float64], maximum: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        """
        :param minimum: The smallest x, y and z of a mesh.
        :param maximum: The largest x, y and z of a mesh.
        :return: The mesh's size along each axis, one along an axis it is flat in.
        """
        extent = maximum - minimum
        return np.where(extent > 0, extent, 1.0)


# %% an object whose parts were split off


@dataclass
class DecomposedObject:
    """
    An object whose parts were split off, together with the shape it had before, so that
    another object of that shape can be given the same parts.
    """

    fingerprint: ShapeFingerprint
    """
    The shape of the object's root body before its parts were split off.
    """

    whole_type: Type[PartWholeRelationship]
    """
    The type of the object's annotation.
    """

    world: World
    """
    The world of the object, with its annotation, the annotations of its parts and the
    bodies they were split into.
    """

    @classmethod
    def of(
        cls, whole: PartWholeRelationship, fingerprint: ShapeFingerprint
    ) -> DecomposedObject:
        """
        :param whole: The annotation of an object whose parts were split off, the only
            annotation of its type in its world.
        :param fingerprint: The shape of the object's root body before the parts were
            split off.
        :return: The object, ready to be stored.
        """
        return cls(fingerprint=fingerprint, whole_type=type(whole), world=whole._world)

    @cached_property
    def whole(self) -> PartWholeRelationship:
        """
        :return: The annotation of the object.
        """
        [whole] = [
            annotation
            for annotation in self.world.semantic_annotations
            if type(annotation) is self.whole_type
        ]
        return whole

    def give_parts_to(
        self, whole: PartWholeRelationship, fingerprint: ShapeFingerprint
    ) -> list[HasRootBody]:
        """
        Give an object of the same shape as this one this object's parts, stretched to
        fit, unless it has some of them already.

        The object's root body is given this object's shapes without the parts, keeping
        the visual shapes of its own that are not meshes, such as a liquid it holds;
        each part becomes a new body fixed to the root body and an annotation of the
        part's type added to the object's annotation.

        :param whole: The annotation of the object, of type :attr:`whole_type`.
        :param fingerprint: The shape of the object's root body.
        :return: The parts added, none if the object has some of them already.
        """
        relationships = [
            relationship
            for relationship in PartRelationshipInspector.all_of_type(self.whole_type)
            if relationship.is_filled_in(self.whole)
        ]
        if any(relationship.is_filled_in(whole) for relationship in relationships):
            return []
        stretch = self.fingerprint.stretch_to(fingerprint)
        root = whole.root
        world = root._world
        parts = []
        with world.modify_world():
            root.update_shapes(
                visual=ShapeCollection(
                    [
                        *self._stretched(self.whole.root.visual, stretch, root),
                        *[
                            shape
                            for shape in root.visual
                            if not isinstance(shape, Mesh)
                        ],
                    ],
                    reference_frame=root,
                ),
                collision=self._stretched(self.whole.root.collision, stretch, root),
            )
            for relationship in relationships:
                for stored_part in relationship.parts_of(self.whole):
                    part = self._add_part(whole, stored_part, stretch)
                    whole.add(part, field_name=relationship.name)
                    parts.append(part)
        return parts

    def _add_part(
        self,
        whole: PartWholeRelationship,
        stored_part: HasRootBody,
        stretch: NDArray[np.float64],
    ) -> HasRootBody:
        """
        Must be called while the world of ``whole`` is being modified.

        :param whole: The annotation of the object the part is given to.
        :param stored_part: The part of this object.
        :param stretch: Maps this object's shape onto the shape of ``whole``'s object.
        :return: A copy of the part, fixed to the root body of ``whole`` and added to
            its world, but not yet to ``whole``.
        """
        root = whole.root
        body = Body(
            name=PrefixedName(type(stored_part).__name__.lower(), str(root.name)),
            inertial=Inertial.negligible(),
        )
        root_T_part = stretch @ self.whole.root._world.compute_forward_kinematics_np(
            self.whole.root, stored_part.root
        )
        body.visual = self._stretched(stored_part.root.visual, root_T_part, body)
        body.collision = self._stretched(stored_part.root.collision, root_T_part, body)
        root._world.add_connection(FixedConnection(parent=root, child=body))
        part = type(stored_part)(root=body)
        root._world.add_semantic_annotation(part)
        return part

    @staticmethod
    def _stretched(
        shapes: ShapeCollection, transform: NDArray[np.float64], body: Body
    ) -> ShapeCollection:
        """
        :param shapes: The shapes of a body of this object.
        :param transform: Maps points of that body's frame onto the frame of ``body``.
        :return: The shapes as meshes of ``body``, mapped by ``transform``, each keeping
            its colors, surface finish and simulator properties.
        """
        stretched = []
        for shape in shapes:
            mesh = shape.mesh.copy()
            mesh.apply_transform(transform @ shape.origin.to_np())
            copy = Mesh.from_trimesh(
                mesh=mesh,
                origin=HomogeneousTransformationMatrix(reference_frame=body),
                finish=shape.finish,
            )
            copy.simulator_additional_properties = list(
                shape.simulator_additional_properties
            )
            stretched.append(copy)
        return ShapeCollection(stretched, reference_frame=body)


# %% where decomposed objects are kept


@dataclass
class DecomposedObjectStore:
    """
    The decomposed objects kept in a database.

    ..note:: The data access objects are generated into
        :mod:`semantic_digital_twin.orm.ormatic_interface` from the classes of this
        package, this one among them, so they are imported where they are used.
    """

    session: Session
    """
    The session of the database the objects are kept in.
    """

    mesh_directory: Path
    """
    Where the mesh files of the objects kept are copied to.

    The database keeps the file name of a mesh, not its triangles, and the meshes split
    off an object are written to files that are removed when the process writing them
    exits.
    """

    def add(self, decomposed: DecomposedObject) -> None:
        """
        Keep a decomposed object.

        :param decomposed: The object.
        """
        self._keep_mesh_files(decomposed.world)
        self.session.add(to_dao(decomposed))
        self.session.commit()

    def _keep_mesh_files(self, world: World) -> None:
        """
        Copy the files of the meshes of a world's bodies that last only as long as this
        process into :attr:`mesh_directory`, and have the meshes read from the copies.

        :param world: The world of an object about to be kept.
        """
        process_files = MeshFileStorage().root
        for body in world.bodies:
            for shape in [*body.visual, *body.collision]:
                if not isinstance(shape, Mesh):
                    continue
                file = Path(shape.filename)
                if not file.is_relative_to(process_files):
                    continue
                directory = MeshFileStorage.create_mesh_directory(self.mesh_directory)
                shutil.copytree(file.parent, directory, dirs_exist_ok=True)
                shape.filename = str(directory / file.name)

    def find(self, fingerprint: ShapeFingerprint) -> Optional[DecomposedObject]:
        """
        :param fingerprint: The shape of an object.
        :return: The decomposed object of that shape kept most recently, if any.
        """
        from semantic_digital_twin.orm.ormatic_interface import (
            DecomposedObjectDAO,
            ShapeFingerprintDAO,
        )

        candidates = self.session.scalars(
            select(DecomposedObjectDAO)
            .join(DecomposedObjectDAO.fingerprint)
            .where(ShapeFingerprintDAO.key == fingerprint.key)
            .order_by(DecomposedObjectDAO.database_id.desc())
        )
        for candidate in candidates:
            if candidate.fingerprint.from_dao().matches(fingerprint):
                return candidate.from_dao()
        return None

    def whole_types(self) -> set[Type[PartWholeRelationship]]:
        """
        :return: The types of the annotations of the objects kept.
        """
        from semantic_digital_twin.orm.ormatic_interface import DecomposedObjectDAO

        return set(self.session.scalars(select(DecomposedObjectDAO.whole_type)))
