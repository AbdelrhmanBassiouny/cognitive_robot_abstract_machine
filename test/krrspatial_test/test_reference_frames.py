from __future__ import annotations

import json

import numpy as np
import pytest

from krrood.adapters.json_serializer import from_json, to_json
from krrood.patterns.exceptions import InterfaceInstantiationError
from krrspatial.exceptions import (
    MissingReferenceFrameResolver,
    ReferenceFrameMismatchError,
)
from krrspatial.reference_frame import ReferenceFrame
from krrspatial.spatial_types import (
    HomogeneousTransformationMatrix,
    Point3,
    RotationMatrix,
)

from .dataset.frames import KnownFrames

# %% the frame interface


def test_a_reference_frame_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        ReferenceFrame()


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

    with pytest.raises(MissingReferenceFrameResolver):
        from_json(data)


def test_a_point_without_a_frame_is_read_without_a_resolver():
    point = Point3(1, 2, 3)

    point_copy = from_json(to_json(point))

    assert point_copy.reference_frame is None
    assert np.allclose(point_copy.to_np(), point.to_np())
