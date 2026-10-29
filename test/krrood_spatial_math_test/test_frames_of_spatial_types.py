from __future__ import annotations

import json

import numpy as np
import pytest

from krrood.adapters.json_serializer import from_json, to_json
from krrood_spatial_math.exceptions import (
    MissingCartesianFrame3DResolver,
    ReferenceFrameMismatchError,
)
from krrood_spatial_math.coordinate_system import (
    CoordinateRepresentation,
    CoordinateSystemT,
    RigidCoordinateChange,
)
from krrood_spatial_math.cartesian_frame_3d import CartesianFrame3D
from krrood_spatial_math.spatial_types import (
    AxisAngle,
    HomogeneousTransformationMatrix,
    Point2,
    Point3,
    Pose,
    Pose2D,
    Quaternion,
    RotationMatrix,
    SpatialType,
    Vector3,
)

from .dataset.frames import KnownFrames

# %% combining values expressed in frames


def test_a_transformation_from_parts_in_different_frames_raises(
    table_frame, camera_frame
):
    position = Point3(1, 2, 3, reference_frame=table_frame)
    rotation = RotationMatrix.from_rpy(yaw=0.5, reference_frame=camera_frame)

    with pytest.raises(ReferenceFrameMismatchError):
        HomogeneousTransformationMatrix.from_point_rotation_matrix(position, rotation)


def test_a_transformed_point_is_expressed_in_the_transformations_frame(
    table_frame, camera_frame
):
    table_T_camera = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=1, reference_frame=table_frame, child_frame=camera_frame
    )

    point_in_table = table_T_camera @ Point3(0, 2, 3, reference_frame=camera_frame)

    assert point_in_table.reference_frame is table_frame
    assert np.allclose(point_in_table.to_np()[:3], [1, 2, 3])


def test_a_point_changed_there_and_back_keeps_its_coordinates(
    table_frame, camera_frame
):
    table_T_camera = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=1, y=2, yaw=0.5, reference_frame=table_frame, child_frame=camera_frame
    )
    point_in_camera = Point3(0, 2, 3, reference_frame=camera_frame)

    point_copy = table_T_camera.inverse() @ (table_T_camera @ point_in_camera)

    assert point_copy.reference_frame is camera_frame
    assert np.allclose(point_copy.to_np(), point_in_camera.to_np())


def test_a_transformation_applies_to_a_point_without_a_frame(table_frame, camera_frame):
    table_T_camera = HomogeneousTransformationMatrix(
        reference_frame=table_frame, child_frame=camera_frame
    )

    point_in_table = table_T_camera @ Point3(0, 2, 3)

    assert point_in_table.reference_frame is table_frame


# %% serializing the frames of a value


def test_a_deserialized_point_refers_to_the_readers_frame(table_frame):
    point = Point3(1, 2, 3, reference_frame=table_frame)
    data = json.loads(json.dumps(to_json(point)))
    known_frames = KnownFrames()
    known_frames.add(table_frame.id, table_frame)

    point_copy = from_json(data, **known_frames.create_kwargs())

    assert point_copy.reference_frame is table_frame
    assert np.allclose(point_copy.to_np(), point.to_np())


def test_a_transformation_keeps_both_of_its_frames(table_frame, camera_frame):
    table_T_camera = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=1, reference_frame=table_frame, child_frame=camera_frame
    )
    known_frames = KnownFrames()
    known_frames.add(table_frame.id, table_frame)
    known_frames.add(camera_frame.id, camera_frame)

    copy = from_json(to_json(table_T_camera), **known_frames.create_kwargs())

    assert copy.reference_frame is table_frame
    assert copy.child_frame is camera_frame


def test_a_point_referring_to_a_frame_cannot_be_read_without_a_resolver(
    table_frame,
):
    data = to_json(Point3(1, 2, 3, reference_frame=table_frame))

    with pytest.raises(MissingCartesianFrame3DResolver):
        from_json(data)


def test_a_point_without_a_frame_is_read_without_a_resolver():
    point = Point3(1, 2, 3)

    point_copy = from_json(to_json(point))

    assert point_copy.reference_frame is None
    assert np.allclose(point_copy.to_np(), point.to_np())


# %% a spatial value as coordinates given in a frame


def test_a_spatial_value_is_a_coordinate_representation_in_a_reference_frame():
    assert issubclass(SpatialType, CoordinateRepresentation)
    assert (
        SpatialType.get_type_of_generic_parameter(CoordinateSystemT) is CartesianFrame3D
    )


@pytest.mark.parametrize(
    "spatial_type",
    [
        Point2,
        Point3,
        Vector3,
        Quaternion,
        AxisAngle,
        RotationMatrix,
        HomogeneousTransformationMatrix,
        Pose,
        Pose2D,
    ],
)
def test_a_spatial_value_is_given_in_its_reference_frame(spatial_type, table_frame):
    value = spatial_type(reference_frame=table_frame)

    assert value.coordinate_system is table_frame


# %% a point on a frame's plane as a planar point


def test_a_point2_is_a_planar_point_of_a_reference_frame():
    assert Point2.get_type_of_generic_parameter(CoordinateSystemT) is CartesianFrame3D


# %% a transformation as a change between two frames


def test_a_transformation_binds_reference_frames_as_its_coordinate_systems():
    assert (
        HomogeneousTransformationMatrix.get_type_of_generic_parameter(CoordinateSystemT)
        is CartesianFrame3D
    )


def test_a_transformation_is_a_rigid_coordinate_change():
    assert issubclass(HomogeneousTransformationMatrix, RigidCoordinateChange)


def test_a_transformation_changes_from_its_child_frame_to_its_reference_frame(
    table_frame, camera_frame
):
    table_T_camera = HomogeneousTransformationMatrix(
        reference_frame=table_frame, child_frame=camera_frame
    )

    assert (
        table_T_camera.source_coordinate_system,
        table_T_camera.target_coordinate_system,
    ) == (camera_frame, table_frame)


def test_an_inverted_transformation_changes_back_to_its_child_frame(
    table_frame, camera_frame
):
    camera_T_table = HomogeneousTransformationMatrix(
        reference_frame=table_frame, child_frame=camera_frame
    ).inverse()

    assert (
        camera_T_table.source_coordinate_system,
        camera_T_table.target_coordinate_system,
    ) == (table_frame, camera_frame)


def test_composed_transformations_change_from_the_first_source_to_the_last_target(
    table_frame, camera_frame, gripper_frame
):
    table_T_camera = HomogeneousTransformationMatrix(
        reference_frame=table_frame, child_frame=camera_frame
    )
    camera_T_gripper = HomogeneousTransformationMatrix(
        reference_frame=camera_frame, child_frame=gripper_frame
    )

    table_T_gripper = table_T_camera @ camera_T_gripper

    assert (
        table_T_gripper.source_coordinate_system,
        table_T_gripper.target_coordinate_system,
    ) == (gripper_frame, table_frame)
