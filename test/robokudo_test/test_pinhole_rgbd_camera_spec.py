from __future__ import annotations

# %% Imports
import numpy as np

from robokudo.descriptors.worlds.pinhole_rgbd_camera import (
    PinholeRGBDCameraSpec,
)
from semantic_digital_twin.datastructures.camera_model import (
    CameraModality,
    CameraRange,
    PinholeCameraModel,
)
from semantic_digital_twin.datastructures.camera_resolution import CameraResolution
from semantic_digital_twin.datastructures.field_of_view import FieldOfView
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.world import World
from robokudo.world_descriptor import BaseWorldDescriptor
from ..semantic_digital_twin_test.conftest import table_world

# %% Standard configuration


def test_pinhole_rgbd_camera_spec_uses_standard_imaging_configuration() -> None:
    pose = HomogeneousTransformationMatrix()

    camera_spec = PinholeRGBDCameraSpec(pose=pose)

    expected_camera_model = PinholeCameraModel.from_field_of_view(
        resolution=CameraResolution(),
        field_of_view=FieldOfView(),
    )
    assert camera_spec.name == PinholeRGBDCameraSpec.name
    assert camera_spec.pose is pose
    assert camera_spec.camera_model == expected_camera_model
    assert camera_spec.camera_range == CameraRange(
        minimum_distance=0.05,
        maximum_distance=8.0,
    )
    assert camera_spec.modalities == (
        CameraModality.COLOR,
        CameraModality.DEPTH,
        CameraModality.SEGMENTATION,
    )


def test_pinhole_rgbd_camera_specs_have_independent_camera_data() -> None:
    first_spec = PinholeRGBDCameraSpec(pose=HomogeneousTransformationMatrix())
    second_spec = PinholeRGBDCameraSpec(pose=HomogeneousTransformationMatrix())

    assert first_spec.camera_model is not second_spec.camera_model
    assert first_spec.camera_range is not second_spec.camera_range


# %% Configurable dataclass fields


def test_pinhole_rgbd_camera_spec_accepts_camera_field_overrides() -> None:
    """
    Dataclass construction retains caller-supplied camera settings.
    """
    pose = HomogeneousTransformationMatrix()
    camera_model = PinholeCameraModel.from_field_of_view(
        resolution=CameraResolution(), field_of_view=FieldOfView()
    )
    camera_range = CameraRange(minimum_distance=0.1, maximum_distance=2.0)
    modalities = (CameraModality.COLOR,)
    camera_spec = PinholeRGBDCameraSpec(
        pose=pose,
        camera_model=camera_model,
        camera_range=camera_range,
        modalities=modalities,
    )
    assert camera_spec.pose is pose
    assert camera_spec.camera_model is camera_model
    assert camera_spec.camera_range is camera_range
    assert camera_spec.modalities == modalities


# %% Camera identity


def test_pinhole_rgbd_camera_spec_accepts_arbitrary_frame_name() -> None:
    """
    Callers can select a frame name outside the default camera identity.
    """
    frame_name = "custom_camera/optical_frame"
    camera_spec = PinholeRGBDCameraSpec(
        pose=HomogeneousTransformationMatrix(), name=frame_name
    )
    assert camera_spec.name == frame_name


# %% Optical mounting poses


def test_standalone_camera_uses_configured_optical_pose(table_world: World) -> None:
    """
    A standalone camera's pose directly defines its optical root in the world.
    """
    spec = PinholeRGBDCameraSpec(
        pose=HomogeneousTransformationMatrix.from_xyz_rpy(
            x=0.2, y=0.3, z=0.4, roll=0.5, pitch=0.6, yaw=0.7
        ),
    )
    camera = BaseWorldDescriptor(world=table_world).build_camera(table_world.root, spec)
    np.testing.assert_allclose(
        camera.root.global_transform.to_np(),
        table_world.root.global_transform.to_np() @ spec.pose.to_np(),
        atol=1e-12,
    )
    assert camera.root.parent_connection.parent is table_world.root


def test_mounted_camera_preserves_parent_relative_optical_pose(
    table_world: World,
) -> None:
    """
    A camera mounted on a moving body follows that parent without changing its offset.
    """
    descriptor = BaseWorldDescriptor(world=table_world)
    mount_spec = PinholeRGBDCameraSpec(
        name="mount", pose=HomogeneousTransformationMatrix.from_xyz_rpy(y=0.4, yaw=0.5)
    )
    mount = descriptor.build_camera(table_world.root, mount_spec).root
    spec = PinholeRGBDCameraSpec(
        pose=HomogeneousTransformationMatrix.from_xyz_rpy(x=0.1, roll=0.3)
    )
    camera = descriptor.build_camera(mount, spec)
    with table_world.modify_world():
        mount.parent_connection.origin = HomogeneousTransformationMatrix(
            data=HomogeneousTransformationMatrix.from_xyz_rpy(y=0.8, pitch=0.7),
            reference_frame=table_world.root,
            child_frame=mount,
        )
    np.testing.assert_allclose(
        camera.root.global_transform.to_np(),
        mount.global_transform.to_np() @ spec.pose.to_np(),
        atol=1e-12,
    )
    assert camera.root.parent_connection.parent is mount
