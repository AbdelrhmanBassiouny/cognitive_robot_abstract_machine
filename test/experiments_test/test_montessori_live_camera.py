"""
Reading the camera as the live robot publishes it, and writing one look as a capture.

Runs against a node of its own with the streams published from this process, so it needs
ROS but no camera and no robot.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

rclpy = pytest.importorskip("rclpy")

from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, CompressedImage
from tf2_ros import StaticTransformBroadcaster
from typing_extensions import Callable, Iterator, List

from experiments.montessori.perception.camera import (
    CameraIntrinsics,
    CameraTopic,
    DepthQuantization,
)
from experiments.montessori.perception.capture_from_camera import (
    LIVE_CAMERA_TAKE,
    take_name,
    write_capture,
)
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.exceptions import NoSceneAvailable
from experiments.montessori.perception.live_camera import LiveCamera
from experiments.montessori.perception.node import MontessoriPerceptionNode
from experiments.montessori.perception.recorded_setup import perception_pipeline
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)

from .test_montessori_camera import (
    COLOR_FORMAT_FIELD,
    DEPTH_FORMAT_FIELD,
    encode_compressed_depth,
)
from .test_montessori_measured_plane import LEAN, leaned_capture

# %% the scene this process publishes

REFERENCE_FRAME = "map"
"""
The frame the camera's pose is asked for in.
"""

CAMERA_FRAME = "camera_color_optical_frame"
"""
The frame the published calibration says the images are taken in.
"""

INTRINSIC_MATRIX = np.array(
    [[1117.0, 0.0, 960.0], [0.0, 1117.0, 540.0], [0.0, 0.0, 1.0]]
)
"""
The calibration the camera publishes.
"""

CAMERA_POSE = HomogeneousTransformationMatrix.from_xyz_quaternion(
    0.5, -0.2, 1.4, 1.0, 0.0, 0.0, 0.0
).to_np()
"""
Where the transform tree stands the camera, a half turn about x at a stated place.
"""

COLOR_IMAGE = np.full((4, 6, 3), (10, 200, 30), dtype=np.uint8)
"""
The colour image published, blue/green/red, which is the order its format field says the
payload is stored in.
"""

DEPTH_MILLIMETRES = np.full((4, 6), 880, dtype=np.uint16)
"""
The depth image published, in millimetres.
"""

DEPTH_QUANTIZATION = DepthQuantization(0, 0.0, 0.0)
"""
A header for a depth image stored in millimetres, which needs no quantization undone.
"""

PUBLISH_PERIOD = 0.05
"""
How often the streams are re-published while a test waits, in seconds.
"""

ARRIVAL_TIMEOUT = 5.0
"""
How long a test waits for a message to cross the middleware, in seconds.
"""


@pytest.fixture(scope="module")
def ros() -> Iterator[None]:
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node(ros: None) -> Iterator[Node]:
    node = rclpy.create_node("live_camera_test")
    yield node
    node.destroy_node()


class PublishedCamera:
    """
    Publishes the camera's three streams and its pose the way the robot does.
    """

    def __init__(self, node: Node):
        self.camera_info = node.create_publisher(
            CameraInfo, CameraTopic.CAMERA_INFO, qos_profile_sensor_data
        )
        self.depth = node.create_publisher(
            CompressedImage, CameraTopic.DEPTH, qos_profile_sensor_data
        )
        self.color = node.create_publisher(
            CompressedImage, CameraTopic.COLOR, qos_profile_sensor_data
        )
        self.transforms = StaticTransformBroadcaster(node)

    def publish_camera_info(self) -> None:
        message = CameraInfo()
        message.header.frame_id = CAMERA_FRAME
        message.k = INTRINSIC_MATRIX.flatten().tolist()
        self.camera_info.publish(message)

    def publish_depth(self) -> None:
        message = CompressedImage()
        message.format = DEPTH_FORMAT_FIELD
        message.data = encode_compressed_depth(DEPTH_MILLIMETRES, DEPTH_QUANTIZATION)
        self.depth.publish(message)

    def publish_color(self) -> None:
        message = CompressedImage()
        message.format = COLOR_FORMAT_FIELD
        message.data = cv2.imencode(".png", COLOR_IMAGE)[1].tobytes()
        self.color.publish(message)

    def publish_pose(self) -> None:
        x, y, z = CAMERA_POSE[:3, 3]
        transform = TransformStamped()
        transform.header.frame_id = REFERENCE_FRAME
        transform.child_frame_id = CAMERA_FRAME
        transform.transform.translation.x = float(x)
        transform.transform.translation.y = float(y)
        transform.transform.translation.z = float(z)
        transform.transform.rotation.x = 1.0
        transform.transform.rotation.w = 0.0
        self.transforms.sendTransform(transform)

    def publish_all(self) -> None:
        self.publish_camera_info()
        self.publish_depth()
        self.publish_color()
        self.publish_pose()


@pytest.fixture
def published(node: Node) -> PublishedCamera:
    return PublishedCamera(node)


def spin_until(
    node: Node, publish: Callable[[], None], arrived: Callable[[], bool]
) -> None:
    """
    Re-publish and spin until what a test waits for has arrived.

    :param node: The node to spin.
    :param publish: Publishes what is waited for, again each turn.
    :param arrived: Whether it has arrived.
    :raises TimeoutError: If it never does.
    """
    deadline = time.monotonic() + ARRIVAL_TIMEOUT
    while time.monotonic() < deadline:
        publish()
        rclpy.spin_once(node, timeout_sec=PUBLISH_PERIOD)
        if arrived():
            return
    raise TimeoutError(f"nothing arrived within {ARRIVAL_TIMEOUT} s")


# %% the streams


def test_every_stream_is_missing_before_anything_has_arrived(node: Node):
    camera = LiveCamera(node=node)

    assert camera.missing_inputs() == [
        str(CameraTopic.CAMERA_INFO),
        str(CameraTopic.DEPTH),
        str(CameraTopic.COLOR),
    ]


def test_a_stream_stops_being_missing_once_a_message_has_arrived_on_it(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(node, published.publish_depth, lambda: camera.depth is not None)

    assert camera.missing_inputs() == [
        str(CameraTopic.CAMERA_INFO),
        str(CameraTopic.COLOR),
    ]


def test_the_calibration_is_read_as_intrinsics_and_the_frame_it_names(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(
        node, published.publish_camera_info, lambda: camera.camera_info is not None
    )

    assert camera.intrinsics == CameraIntrinsics.from_camera_info_matrix(
        INTRINSIC_MATRIX
    )
    assert camera.camera_frame == CAMERA_FRAME


def test_a_colour_image_completes_a_look_and_is_handed_to_the_callback(
    node: Node, published: PublishedCamera
):
    completed: List[CompressedImage] = []
    camera = LiveCamera(node=node, color_callback=completed.append)

    spin_until(node, published.publish_color, lambda: len(completed) > 0)

    assert completed[0] is camera.color


def test_the_images_are_decoded_as_published(node: Node, published: PublishedCamera):
    camera = LiveCamera(node=node)

    spin_until(
        node,
        published.publish_all,
        lambda: camera.color is not None and camera.depth is not None,
    )

    np.testing.assert_array_equal(camera.color_image, COLOR_IMAGE)
    np.testing.assert_allclose(camera.depth_image, DEPTH_MILLIMETRES / 1000.0)


# %% where the camera stands


def test_the_pose_is_unknown_until_the_calibration_names_the_camera_frame(
    node: Node,
):
    camera = LiveCamera(node=node)

    assert camera.pose_in(REFERENCE_FRAME) is None


def test_the_camera_stands_where_the_transform_tree_puts_it(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(
        node,
        published.publish_all,
        lambda: camera.pose_in(REFERENCE_FRAME) is not None,
    )

    np.testing.assert_allclose(camera.pose_in(REFERENCE_FRAME), CAMERA_POSE, atol=1e-9)


def test_a_frame_carries_the_images_the_calibration_and_the_pose(
    node: Node, published: PublishedCamera
):
    camera = LiveCamera(node=node)

    spin_until(
        node,
        published.publish_all,
        lambda: camera.frame_in(REFERENCE_FRAME) is not None,
    )
    frame = camera.frame_in(REFERENCE_FRAME)

    np.testing.assert_array_equal(frame.color, camera.color_image)
    np.testing.assert_array_equal(frame.depth, camera.depth_image)
    assert frame.intrinsics == camera.intrinsics
    np.testing.assert_allclose(frame.reference_frame_T_camera, CAMERA_POSE, atol=1e-9)


# %% writing a look as a capture


def test_a_capture_taken_off_the_camera_reads_back_as_the_look_it_was_taken_from(
    node: Node, published: PublishedCamera, tmp_path: Path
):
    timer = node.create_timer(PUBLISH_PERIOD, published.publish_all)

    capture = write_capture(
        node,
        "live_look",
        reference_frame=REFERENCE_FRAME,
        timeout_seconds=ARRIVAL_TIMEOUT,
        directory=tmp_path,
    )
    node.destroy_timer(timer)

    read_back = SceneCapture.load("live_look", tmp_path)
    assert read_back.intrinsics == CameraIntrinsics.from_camera_info_matrix(
        INTRINSIC_MATRIX
    )
    assert read_back.reference_frame == REFERENCE_FRAME
    assert read_back.color_format == COLOR_FORMAT_FIELD
    np.testing.assert_allclose(read_back.reference_frame_T_camera, CAMERA_POSE)
    frame = read_back.to_frame()
    np.testing.assert_array_equal(frame.color, COLOR_IMAGE)
    np.testing.assert_allclose(frame.depth, DEPTH_MILLIMETRES / 1000.0)
    assert capture.recorded_from == read_back.recorded_from
    assert read_back.recorded_from.startswith(LIVE_CAMERA_TAKE)


def test_a_capture_names_the_moment_it_was_taken_at():
    assert take_name(datetime(2026, 9, 11, 18, 24, 5)) == (
        f"{LIVE_CAMERA_TAKE}_20260911_182405"
    )


def test_writing_a_capture_reports_what_never_arrived_when_the_camera_is_silent(
    node: Node, tmp_path: Path
):
    with pytest.raises(NoSceneAvailable) as raised:
        write_capture(node, "silent", timeout_seconds=0.2, directory=tmp_path)

    assert raised.value.missing_inputs == [
        str(CameraTopic.CAMERA_INFO),
        str(CameraTopic.DEPTH),
        str(CameraTopic.COLOR),
    ]


# %% the stated pose is checked against the table on the first placed look


def test_the_node_reports_how_far_the_stated_pose_is_off_on_its_first_placed_look(
    node: Node,
):
    perception = MontessoriPerceptionNode(node=node, pipeline=perception_pipeline())

    error = perception.check_camera_pose(leaned_capture().to_frame())

    assert perception.camera_pose_error is error
    assert not error.within_tolerance
    assert error.tilt == pytest.approx(LEAN, abs=0.5)
