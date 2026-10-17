"""
Storing objects whose parts were split off, and giving the next object of the same shape
those parts without finding them again.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
import trimesh
from sqlalchemy.orm import Session

from krrood.ormatic.utils import create_engine
from semantic_digital_twin.orm.ormatic_interface import Base
from semantic_digital_twin.part_finding.annotation_part_finder import (
    AnnotationPartFinder,
)
from semantic_digital_twin.part_finding.decomposed_objects import (
    DecomposedObject,
    DecomposedObjectStore,
    ShapeFingerprint,
)
from semantic_digital_twin.part_finding.locating import KnownPartLocator, LocatedPart
from semantic_digital_twin.pipeline.part_finding import UseDecomposedObjects
from semantic_digital_twin.semantic_annotations.semantic_annotations import (
    Handle,
    Mug,
    Pot,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world_description.geometry import Cylinder, Mesh
from semantic_digital_twin.world_description.mesh_file_storage import MeshFileStorage

from .test_locating import annotate, mug_with_handle

# %% fixtures


@pytest.fixture
def session():
    session = Session(create_engine("sqlite:///:memory:"))
    Base.metadata.create_all(bind=session.bind)
    yield session
    Base.metadata.drop_all(session.bind)
    session.close()


def decomposed_mug() -> tuple[Mug, ShapeFingerprint]:
    """
    :return: A mug whose handle was split off, and the shape it had before.
    """
    mesh, handle_faces = mug_with_handle()
    mug = annotate(mesh, Mug)
    fingerprint = ShapeFingerprint.of_body(mug.root)
    AnnotationPartFinder(
        locator=KnownPartLocator(parts=[LocatedPart("handle", handle_faces, 1.0)]),
        decomposer=None,
    ).find_parts(mug)
    return mug, fingerprint


@pytest.fixture
def store(session, tmp_path) -> DecomposedObjectStore:
    """
    :return: A store holding one mug whose handle was split off.
    """
    store = DecomposedObjectStore(session=session, mesh_directory=tmp_path)
    store.add(DecomposedObject.of(*decomposed_mug()))
    return store


def stretched(mesh: trimesh.Trimesh, factors: list[float]) -> trimesh.Trimesh:
    """
    :param mesh: A mesh.
    :param factors: How much to stretch it along x, y and z.
    :return: A copy of the mesh, stretched about its origin.
    """
    copy = mesh.copy()
    copy.apply_scale(factors)
    return copy


# %% recognizing a shape however it is scaled


def test_a_fingerprint_is_the_same_however_the_shape_is_stretched():
    mesh, _ = mug_with_handle()

    original = ShapeFingerprint.of_mesh(mesh)
    larger = ShapeFingerprint.of_mesh(stretched(mesh, [1.25, 1.25, 1.75]))

    assert larger.matches(original)
    np.testing.assert_allclose(
        larger.maximum, np.multiply(original.maximum, [1.25, 1.25, 1.75])
    )


def test_a_fingerprint_is_the_same_for_a_point_halfway_between_rounding_steps():
    """
    A RoboCasa pot scaled to 0.8 in a task once got another fingerprint than the same
    pot loaded alone, because one of its points lies, relative to its extent, exactly
    halfway between two rounding steps, and scaling moved it by the last bit.
    """
    box = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    box.apply_translation([0.5, 0.5, 0.5])
    vertices = np.vstack([box.vertices, [0.12345, 0.5, 0.5]])
    faces = np.vstack([box.faces, [[0, 1, len(box.vertices)]]])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    assert ShapeFingerprint.of_mesh(stretched(mesh, [0.8, 0.8, 0.8])).matches(
        ShapeFingerprint.of_mesh(mesh)
    )


def test_a_fingerprint_tells_apart_shapes_of_the_same_triangles():
    mesh, _ = mug_with_handle()
    bent = mesh.copy()
    bent.vertices[0] += [0.01, 0.0, 0.0]

    assert not ShapeFingerprint.of_mesh(bent).matches(ShapeFingerprint.of_mesh(mesh))


def test_a_fingerprint_tells_shapes_apart():
    mesh, _ = mug_with_handle()

    assert not ShapeFingerprint.of_mesh(
        trimesh.creation.box(extents=[0.1, 0.1, 0.1])
    ).matches(ShapeFingerprint.of_mesh(mesh))


def test_a_fingerprint_maps_points_of_its_shape_onto_a_stretched_copy():
    mesh, _ = mug_with_handle()
    larger = stretched(mesh, [1.25, 1.25, 1.75])

    stretch = ShapeFingerprint.of_mesh(mesh).stretch_to(
        ShapeFingerprint.of_mesh(larger)
    )

    np.testing.assert_allclose(
        trimesh.transform_points(mesh.vertices, stretch), larger.vertices, atol=1e-9
    )


# %% storing a decomposed object


def test_a_stored_object_is_found_by_its_shape(store):
    mesh, _ = mug_with_handle()

    found = store.find(ShapeFingerprint.of_mesh(mesh))

    assert found.whole_type is Mug
    assert isinstance(found.whole.handle, Handle)


def test_a_stored_object_is_found_after_the_mesh_files_of_its_process_are_gone(
    session, tmp_path
):
    store = DecomposedObjectStore(session=session, mesh_directory=tmp_path)
    mug, fingerprint = decomposed_mug()
    process_files = {
        Path(shape.filename).parent
        for body in mug._world.bodies
        for shape in [*body.visual, *body.collision]
        if isinstance(shape, Mesh)
        and Path(shape.filename).is_relative_to(MeshFileStorage().root)
    }

    store.add(DecomposedObject.of(mug, fingerprint))
    for directory in process_files:
        shutil.rmtree(directory)
    found = store.find(fingerprint)

    assert process_files
    assert len(found.whole.handle.root.collision.combined_mesh.faces) > 0


def test_an_object_of_a_shape_never_stored_is_not_found(store):
    box = trimesh.creation.box(extents=[0.1, 0.1, 0.1])

    assert store.find(ShapeFingerprint.of_mesh(box)) is None


def test_the_store_knows_the_types_of_the_objects_it_holds(store):
    assert store.whole_types() == {Mug}


# %% giving a loaded object its stored parts


def test_a_mug_of_a_stored_shape_gets_the_stored_handle(store):
    mesh, handle_faces = mug_with_handle()
    mug = annotate(mesh, Mug)
    root = mug.root

    UseDecomposedObjects(store=store).apply(mug._world)

    assert isinstance(mug.handle, Handle)
    assert mug.root is root
    assert len(mug._world.bodies) == 2
    assert len(mug.handle.root.visual.combined_mesh.faces) == len(handle_faces)
    assert len(mug.root.visual.combined_mesh.faces) == len(mesh.faces) - len(
        handle_faces
    )


def test_a_mug_holding_liquid_gets_the_stored_handle_and_keeps_its_liquid(store):
    """
    RoboCasa shows the liquid in a mug or pot of some tasks as a translucent cylinder of
    the object's body, which is not part of the object's shape.
    """
    mesh, _ = mug_with_handle()
    mug = annotate(mesh, Mug)
    liquid = Cylinder(
        origin=HomogeneousTransformationMatrix(reference_frame=mug.root),
        width=0.06,
        height=0.002,
    )
    mug.root.visual.shapes.append(liquid)

    UseDecomposedObjects(store=store).apply(mug._world)

    assert isinstance(mug.handle, Handle)
    assert any(shape is liquid for shape in mug.root.visual)


def test_the_stored_handle_is_stretched_to_fit_a_larger_mug(store):
    mesh, handle_faces = mug_with_handle()
    factors = [1.25, 1.25, 1.75]
    mug = annotate(stretched(mesh, factors), Mug)

    UseDecomposedObjects(store=store).apply(mug._world)

    expected = stretched(mesh.submesh([handle_faces], append=True), factors)
    np.testing.assert_allclose(
        mug.handle.root.collision.combined_mesh.bounds, expected.bounds, atol=1e-9
    )


def test_an_object_of_another_type_is_left_as_it_is(store):
    mesh, _ = mug_with_handle()
    pot = annotate(mesh, Pot)

    UseDecomposedObjects(store=store).apply(pot._world)

    assert pot.handles == []
    assert len(pot._world.bodies) == 1


def test_a_mug_of_another_shape_is_left_as_it_is(store):
    mug = annotate(trimesh.creation.annulus(r_min=0.03, r_max=0.04, height=0.1), Mug)

    UseDecomposedObjects(store=store).apply(mug._world)

    assert mug.handle is None
    assert len(mug._world.bodies) == 1


def test_a_mug_that_has_a_handle_already_is_left_as_it_is(store):
    mesh, handle_faces = mug_with_handle()
    mug = annotate(mesh, Mug)
    AnnotationPartFinder(
        locator=KnownPartLocator(parts=[LocatedPart("handle", handle_faces, 1.0)]),
        decomposer=None,
    ).find_parts(mug)
    handle = mug.handle

    UseDecomposedObjects(store=store).apply(mug._world)

    assert mug.handle is handle
    assert len(mug._world.bodies) == 2
