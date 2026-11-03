from __future__ import annotations

import numpy as np
import pytest

import krrood.symbolic_math.symbolic_math as sm
from krrood.adapters.json_serializer import from_json, to_json
from krrood_spatial_math.affine_point import AffinePoint2D, CartesianPoint, CoordinateT
from krrood_spatial_math.cartesian_frame_2d import CartesianFrame2D
from krrood_spatial_math.cartesian_frame_3d import ValueInCartesianFrame3D
from krrood_spatial_math.coordinate_system import (
    CoordinateSystemT,
    RigidCoordinateChange,
)
from krrood_spatial_math.exceptions import (
    FramesOnDifferentPlanesError,
    MirroredPlaneFramesError,
    XAxisNormalToPlaneError,
)
from krrood_spatial_math.space import EuclideanSpace2D
from krrood_spatial_math.spatial_types import (
    HomogeneousTransformationMatrix,
    HomogeneousTransformationMatrix2D,
    CartesianPoint2D,
    CartesianPoint3D,
    Pose,
    Pose2D,
    XYPlane2D,
    XYPlaneFrame2D,
)

from .dataset.frames import KnownFrames, NamedFrame, Room
from .dataset.mounted_frames import MountedFrame

# %% frames in one room


@pytest.fixture
def floor_frame(room) -> NamedFrame:
    return NamedFrame("floor", space=room)


def mounted_on(
    floor_frame: NamedFrame, name: str, **pose_on_floor: float
) -> MountedFrame:
    """
    :param floor_frame: The frame the new frame is fixed on.
    :param name: What the new frame is called.
    :param pose_on_floor: The x, y, z, roll, pitch and yaw of the new frame on the
        floor.
    :return: A frame fixed on the floor, in the floor's room.
    """
    return MountedFrame(
        name,
        space=floor_frame.space,
        mount_T_self=HomogeneousTransformationMatrix.from_xyz_rpy(
            **pose_on_floor, reference_frame=floor_frame
        ),
    )


@pytest.fixture
def robot_base_frame(floor_frame) -> MountedFrame:
    return mounted_on(floor_frame, "robot base", x=1, y=2, yaw=0.5)


@pytest.fixture
def upside_down_frame(floor_frame) -> MountedFrame:
    return mounted_on(floor_frame, "upside down", x=3, roll=np.pi)


@pytest.fixture
def shelf_frame(floor_frame) -> MountedFrame:
    return mounted_on(floor_frame, "shelf", x=1, z=2)


@pytest.fixture
def wall_frame(floor_frame) -> MountedFrame:
    return mounted_on(floor_frame, "wall", roll=np.pi / 2)


def coordinates(*values: sm.Scalar) -> np.ndarray:
    """
    :param values: Constant symbolic scalars.
    :return: Their numbers, in the order given.
    """
    return np.concatenate([value.to_np() for value in values])


# %% the plane a frame's x- and y-axes span


def test_a_frames_xy_plane_is_a_two_dimensional_euclidean_space():
    assert issubclass(XYPlane2D, EuclideanSpace2D)


def test_a_plane_lies_in_the_space_of_its_frame(floor_frame, room):
    assert XYPlane2D(floor_frame).ambient_space is room


def test_a_frame_moved_within_a_plane_spans_that_plane(floor_frame, robot_base_frame):
    assert XYPlane2D(robot_base_frame) == XYPlane2D(floor_frame)


def test_a_frame_turned_upside_down_spans_the_same_plane(
    floor_frame, upside_down_frame
):
    assert XYPlane2D(upside_down_frame) == XYPlane2D(floor_frame)


def test_a_frame_lifted_off_a_plane_spans_another_plane(floor_frame, shelf_frame):
    assert XYPlane2D(shelf_frame) != XYPlane2D(floor_frame)


def test_a_tilted_frame_spans_another_plane(floor_frame, wall_frame):
    assert XYPlane2D(wall_frame) != XYPlane2D(floor_frame)


def test_frames_in_no_known_space_share_a_plane_only_with_themselves(
    table_frame, camera_frame
):
    assert XYPlane2D(table_frame) == XYPlane2D(table_frame)
    assert XYPlane2D(table_frame) != XYPlane2D(camera_frame)


def test_frames_in_different_spaces_span_different_planes(floor_frame):
    other_floor_frame = NamedFrame("other floor", space=Room())

    assert XYPlane2D(other_floor_frame) != XYPlane2D(floor_frame)


def test_equal_planes_hash_alike(floor_frame, robot_base_frame):
    assert hash(XYPlane2D(robot_base_frame)) == hash(XYPlane2D(floor_frame))


# %% the frame a plane's values are given in


def test_a_plane_frame_is_a_two_dimensional_cartesian_frame():
    assert issubclass(XYPlaneFrame2D, CartesianFrame2D)


def test_a_plane_frame_lies_on_the_xy_plane_of_its_frame(floor_frame):
    assert XYPlaneFrame2D(floor_frame).space == XYPlane2D(floor_frame)


def test_a_plane_frame_is_called_like_its_frame(floor_frame):
    assert XYPlaneFrame2D(floor_frame).name == floor_frame.name


def test_the_plane_frames_of_one_frame_are_one_frame(floor_frame):
    plane_frame = XYPlaneFrame2D(floor_frame)
    plane_frame_copy = XYPlaneFrame2D(floor_frame)

    assert plane_frame == plane_frame_copy
    assert plane_frame.id == plane_frame_copy.id
    assert hash(plane_frame) == hash(plane_frame_copy)


def test_the_plane_frames_of_two_frames_on_one_plane_are_two_frames(
    floor_frame, robot_base_frame
):
    plane_frame = XYPlaneFrame2D(floor_frame)
    other_plane_frame = XYPlaneFrame2D(robot_base_frame)

    assert plane_frame != other_plane_frame
    assert plane_frame.id != other_plane_frame.id


def test_a_plane_frame_is_told_apart_from_its_frame(floor_frame):
    assert XYPlaneFrame2D(floor_frame).id != floor_frame.id


# %% values on a frame's plane

planar_values = [CartesianPoint2D, Pose2D]


@pytest.mark.parametrize("planar_value", planar_values)
def test_a_planar_value_is_given_in_the_frame_on_its_reference_frames_plane(
    planar_value, floor_frame
):
    value = planar_value(reference_frame=floor_frame)

    assert value.coordinate_system == XYPlaneFrame2D(floor_frame)


@pytest.mark.parametrize("planar_value", planar_values)
def test_a_planar_value_keeps_its_reference_frame(planar_value, floor_frame):
    assert planar_value(reference_frame=floor_frame).reference_frame is floor_frame


@pytest.mark.parametrize("planar_value", planar_values)
def test_a_planar_value_without_a_reference_frame_has_no_coordinate_system(
    planar_value,
):
    assert planar_value().coordinate_system is None


@pytest.mark.parametrize("planar_value", planar_values)
def test_a_planar_value_is_no_value_given_in_a_three_dimensional_frame(planar_value):
    assert not issubclass(planar_value, ValueInCartesianFrame3D)


def test_a_two_dimensional_point_is_an_affine_point_of_a_two_dimensional_cartesian_frame():
    assert issubclass(CartesianPoint2D, AffinePoint2D)
    assert (
        CartesianPoint2D.get_type_of_generic_parameter(CoordinateSystemT)
        is CartesianFrame2D
    )


def test_a_two_dimensional_point_is_a_cartesian_point():
    assert issubclass(CartesianPoint2D, CartesianPoint)


def test_the_euclidean_distance_between_two_dimensional_points_is_measured_on_their_plane():
    origin = CartesianPoint2D(1, 2)
    other = CartesianPoint2D(4, 6)

    assert float(origin.euclidean_distance(other)) == 5.0


def test_a_two_dimensional_point_stores_its_coordinates_as_symbolic_scalars():
    assert CartesianPoint2D.get_type_of_generic_parameter(CoordinateT) is sm.Scalar


# %% rigid changes between frames on one plane


def test_a_planar_transformation_is_a_rigid_change_of_two_dimensional_frames():
    assert issubclass(HomogeneousTransformationMatrix2D, RigidCoordinateChange)
    assert (
        HomogeneousTransformationMatrix2D.get_type_of_generic_parameter(
            CoordinateSystemT
        )
        is CartesianFrame2D
    )


def test_a_planar_transformation_changes_between_the_plane_frames_of_its_frames(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D(
        reference_frame=floor_frame, child_frame=robot_base_frame
    )

    assert (
        floor_T_robot_base.source_coordinate_system,
        floor_T_robot_base.target_coordinate_system,
    ) == (XYPlaneFrame2D(robot_base_frame), XYPlaneFrame2D(floor_frame))


def test_a_planar_transformation_without_frames_has_no_coordinate_systems():
    transformation = HomogeneousTransformationMatrix2D()

    assert (
        transformation.source_coordinate_system,
        transformation.target_coordinate_system,
    ) == (None, None)


def test_a_change_within_one_plane_becomes_the_planar_transformation_of_its_motion(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D.from_transformation(
        robot_base_frame.mount_T_self
    )

    assert floor_T_robot_base.reference_frame is floor_frame
    assert floor_T_robot_base.child_frame is robot_base_frame
    assert np.allclose(
        coordinates(floor_T_robot_base.x, floor_T_robot_base.y, floor_T_robot_base.yaw),
        [1, 2, 0.5],
    )


@pytest.mark.parametrize("frame_off_the_floor", ["shelf_frame", "wall_frame"])
def test_a_change_between_two_planes_has_no_planar_transformation(
    frame_off_the_floor, request
):
    frame = request.getfixturevalue(frame_off_the_floor)

    with pytest.raises(FramesOnDifferentPlanesError):
        HomogeneousTransformationMatrix2D.from_transformation(frame.mount_T_self)


def test_a_change_to_a_frame_facing_the_other_side_of_a_plane_has_no_planar_transformation(
    upside_down_frame,
):
    with pytest.raises(MirroredPlaneFramesError):
        HomogeneousTransformationMatrix2D.from_transformation(
            upside_down_frame.mount_T_self
        )


def test_a_symbolic_change_becomes_a_planar_transformation_unchecked(floor_frame):
    height = sm.FloatVariable(name="height")
    lifted = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=1, z=height, reference_frame=floor_frame
    )

    floor_T_lifted = HomogeneousTransformationMatrix2D.from_transformation(lifted)

    assert np.allclose(floor_T_lifted.x.to_np(), [1])


def test_a_planar_transformation_moves_a_point_into_its_reference_frame(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D.from_xy_yaw(
        x=1,
        y=2,
        yaw=np.pi / 2,
        reference_frame=floor_frame,
        child_frame=robot_base_frame,
    )

    point_on_floor = floor_T_robot_base @ CartesianPoint2D(
        1, 0, reference_frame=robot_base_frame
    )

    assert point_on_floor.reference_frame is floor_frame
    assert np.allclose(coordinates(point_on_floor.x, point_on_floor.y), [1, 3])


def test_a_planar_transformation_moves_a_pose_into_its_reference_frame(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D.from_xy_yaw(
        x=1,
        y=2,
        yaw=np.pi / 2,
        reference_frame=floor_frame,
        child_frame=robot_base_frame,
    )

    pose_on_floor = floor_T_robot_base @ Pose2D.from_xy_yaw(
        x=1, yaw=0.25, reference_frame=robot_base_frame
    )

    assert pose_on_floor.reference_frame is floor_frame
    assert np.allclose(
        coordinates(pose_on_floor.x, pose_on_floor.y, pose_on_floor.yaw),
        [1, 3, np.pi / 2 + 0.25],
    )


def test_composed_planar_transformations_change_from_the_first_source_to_the_last_target(
    floor_frame, robot_base_frame, upside_down_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D.from_xy_yaw(
        x=1, yaw=np.pi / 2, reference_frame=floor_frame, child_frame=robot_base_frame
    )
    robot_base_T_other = HomogeneousTransformationMatrix2D.from_xy_yaw(
        x=1, reference_frame=robot_base_frame, child_frame=upside_down_frame
    )

    floor_T_other = floor_T_robot_base @ robot_base_T_other

    assert floor_T_other.reference_frame is floor_frame
    assert floor_T_other.child_frame is upside_down_frame
    assert np.allclose(
        coordinates(floor_T_other.x, floor_T_other.y, floor_T_other.yaw),
        [1, 1, np.pi / 2],
    )


def test_a_point_changed_there_and_back_on_a_plane_keeps_its_coordinates(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D.from_xy_yaw(
        x=1, y=2, yaw=0.5, reference_frame=floor_frame, child_frame=robot_base_frame
    )
    point = CartesianPoint2D(3, 4, reference_frame=robot_base_frame)

    point_copy = floor_T_robot_base.inverse() @ (floor_T_robot_base @ point)

    assert point_copy.reference_frame is robot_base_frame
    assert np.allclose(point_copy.to_np(), point.to_np())


def test_a_planar_transformation_moves_a_point_as_its_change_does(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = robot_base_frame.mount_T_self
    point = CartesianPoint2D(3, 4, reference_frame=robot_base_frame)

    point_on_floor = (
        HomogeneousTransformationMatrix2D.from_transformation(floor_T_robot_base)
        @ point
    )

    expected = CartesianPoint2D.from_cartesian_point_3d(
        floor_T_robot_base @ point.to_cartesian_point_3d()
    )
    assert np.allclose(point_on_floor.to_np(), expected.to_np())


def test_a_planar_transformation_keeps_its_motion_and_frames_in_json(
    floor_frame, robot_base_frame
):
    floor_T_robot_base = HomogeneousTransformationMatrix2D.from_xy_yaw(
        x=1, y=2, yaw=0.5, reference_frame=floor_frame, child_frame=robot_base_frame
    )
    known_frames = KnownFrames()
    known_frames.add(floor_frame.id, floor_frame)
    known_frames.add(robot_base_frame.id, robot_base_frame)

    copy = from_json(to_json(floor_T_robot_base), **known_frames.create_kwargs())

    assert copy.reference_frame is floor_frame
    assert copy.child_frame is robot_base_frame
    assert np.allclose(copy.to_np(), floor_T_robot_base.to_np())


# %% a pose flattened onto its frame's plane


def test_a_flattened_pose_faces_the_way_its_x_axis_points_on_the_plane(floor_frame):
    pose = Pose.from_xyz_rpy(
        x=1, y=2, z=3, roll=0.3, pitch=0.2, yaw=0.5, reference_frame=floor_frame
    )

    pose_on_floor = Pose2D.from_pose(pose)

    x_axis = pose.rotation_matrix.to_np()[:2, 0]
    assert np.allclose(
        coordinates(pose_on_floor.x, pose_on_floor.y, pose_on_floor.yaw),
        [1, 2, np.arctan2(x_axis[1], x_axis[0])],
    )


def test_a_pose_whose_x_axis_is_normal_to_the_plane_cannot_be_flattened(
    floor_frame,
):
    pose = Pose.from_xyz_rpy(pitch=np.pi / 2, reference_frame=floor_frame)

    with pytest.raises(XAxisNormalToPlaneError):
        Pose2D.from_pose(pose)
