"""
The camera as the live robot publishes it: its streams, its calibration, and where the
transform tree says it stands.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, CompressedImage
from typing_extensions import Callable, List, Optional

from experiments.montessori.perception.camera import (
    CameraIntrinsics,
    CameraTopic,
    RgbdFrame,
    decode_compressed_color_image,
    decode_compressed_depth_image,
)
from semantic_digital_twin.adapters.ros.tfwrapper import TFWrapper
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)

TRANSFORM_WAIT = Duration(seconds=0.2)
"""
How long one lookup waits for the transform tree to answer for the camera's frame.
"""


@dataclass
class CameraPoseLookup:
    """
    Reads where the camera stands from the transform tree the robot publishes.

    Reads the newest transform rather than the one stamped on an image: this camera is
    bolted to the robot's own table, so its pose does not move between a frame being
    taken and being read, and asking for a past stamp only risks falling off the back of
    the transform buffer.
    """

    node: Node
    """
    The node the transform tree is listened to on.
    """

    _transforms: TFWrapper = field(init=False)
    """
    The listener on the transform tree.
    """

    def __post_init__(self) -> None:
        self._transforms = TFWrapper(node=self.node)

    def pose_of(self, camera_frame: str, reference_frame: str) -> Optional[np.ndarray]:
        """
        :param camera_frame: The frame the camera reports its images in.
        :param reference_frame: The frame to express the camera's pose in.
        :return: The camera's pose as a 4x4 homogeneous transformation, or None while
            the transform tree cannot yet answer for that frame.
        """
        if not self._transforms.wait_for_transform(
            reference_frame, camera_frame, Time(), TRANSFORM_WAIT
        ):
            return None
        transform = self._transforms.lookup_transform(
            reference_frame, camera_frame
        ).transform
        return HomogeneousTransformationMatrix.from_xyz_quaternion(
            transform.translation.x,
            transform.translation.y,
            transform.translation.z,
            transform.rotation.x,
            transform.rotation.y,
            transform.rotation.z,
            transform.rotation.w,
        ).to_np()


@dataclass
class LiveCamera:
    """
    The newest of everything the camera publishes, as it arrives.

    Holds each stream's latest message so that one look can be assembled from a colour
    image, the depth image published closest before it, the calibration both were taken
    with and the pose the transform tree gives the camera.
    """

    node: Node
    """
    The node the streams are subscribed on.
    """

    color_callback: Optional[Callable[[CompressedImage], None]] = None
    """
    Called with each colour image once it is held, or None to hold it silently.

    A colour image is the last of a look to arrive, so this is where a look is complete.
    """

    camera_info: Optional[CameraInfo] = field(init=False, default=None)
    """
    The camera's newest calibration, or None until one has arrived.
    """

    depth: Optional[CompressedImage] = field(init=False, default=None)
    """
    The newest depth image, or None until one has arrived.
    """

    color: Optional[CompressedImage] = field(init=False, default=None)
    """
    The newest colour image, or None until one has arrived.
    """

    _poses: CameraPoseLookup = field(init=False)
    """
    Reads where the camera stands.
    """

    def __post_init__(self) -> None:
        self._poses = CameraPoseLookup(node=self.node)
        self.node.create_subscription(
            CameraInfo,
            CameraTopic.CAMERA_INFO,
            self._on_camera_info,
            qos_profile_sensor_data,
        )
        self.node.create_subscription(
            CompressedImage, CameraTopic.DEPTH, self._on_depth, qos_profile_sensor_data
        )
        self.node.create_subscription(
            CompressedImage, CameraTopic.COLOR, self._on_color, qos_profile_sensor_data
        )

    def _on_camera_info(self, message: CameraInfo) -> None:
        self.camera_info = message

    def _on_depth(self, message: CompressedImage) -> None:
        self.depth = message

    def _on_color(self, message: CompressedImage) -> None:
        self.color = message
        if self.color_callback is not None:
            self.color_callback(message)

    @property
    def intrinsics(self) -> CameraIntrinsics:
        """
        How the camera projects, as it last reported it.
        """
        return CameraIntrinsics.from_camera_info_matrix(self.camera_info.k)

    @property
    def color_image(self) -> np.ndarray:
        """
        The newest colour image decoded, blue/green/red.
        """
        return decode_compressed_color_image(self.color.data, self.color.format)

    @property
    def depth_image(self) -> np.ndarray:
        """
        The newest depth image decoded, in metres, zero where the sensor returned no
        reading.
        """
        return decode_compressed_depth_image(self.depth.data, self.depth.format)

    @property
    def camera_frame(self) -> str:
        """
        The frame the camera last reported its images in.
        """
        return self.camera_info.header.frame_id

    def pose_in(self, reference_frame: str) -> Optional[np.ndarray]:
        """
        Where the camera stands.

        :param reference_frame: The frame to express its pose in.
        :return: Its pose as a 4x4 homogeneous transformation, or None while either the
            calibration naming its frame or the transform tree has yet to answer.
        """
        if self.camera_info is None:
            return None
        return self._poses.pose_of(self.camera_frame, reference_frame)

    def frame_in(self, reference_frame: str) -> Optional[RgbdFrame]:
        """
        The newest look, assembled from the newest colour image, the depth image
        published closest before it, the calibration and the camera's pose.

        :param reference_frame: The frame to express the camera's pose in.
        :return: The frame, or None while a stream or the camera's pose has yet to
            arrive.
        """
        if self.missing_inputs():
            return None
        reference_frame_T_camera = self.pose_in(reference_frame)
        if reference_frame_T_camera is None:
            return None
        return RgbdFrame(
            color=self.color_image,
            depth=self.depth_image,
            intrinsics=self.intrinsics,
            reference_frame_T_camera=reference_frame_T_camera,
        )

    def missing_inputs(self) -> List[str]:
        """
        The streams nothing has arrived on yet.
        """
        missing = []
        if self.camera_info is None:
            missing.append(str(CameraTopic.CAMERA_INFO))
        if self.depth is None:
            missing.append(str(CameraTopic.DEPTH))
        if self.color is None:
            missing.append(str(CameraTopic.COLOR))
        return missing
