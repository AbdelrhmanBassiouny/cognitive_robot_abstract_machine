"""
Replaying a recorded rosbag into a world.

A recording of the robot is a stream of transform and joint state messages. The player
samples that stream at a fixed period along the recording's own clock into frames, and a
frame poses the free bodies of the world the recording names and positions the joints it
names. Reading the recording needs no ROS installation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from pathlib import Path

import numpy as np
from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore
from typing_extensions import Dict, Iterator, List, Optional

from segmind.exceptions import RecordingHoldsNothingToReplay, ReferenceFrameNotRecorded
from segmind.players.data_player import FilePlayer, FrameData, FrameDataGenerator
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world_description.connections import (
    ActiveConnection1DOF,
    Connection6DoF,
)
from semantic_digital_twin.world_description.world_entity import Body

# %% what a recording carries


class RosbagTopic(StrEnum):
    """
    The topics a recording of the robot is replayed from.
    """

    STATIC_TRANSFORMS = "/tf_static"
    TRANSFORMS = "/tf"
    JOINT_STATES = "/joint_states"


class RosbagMessageType(StrEnum):
    """
    The message types published on the replayed topics.
    """

    TRANSFORMS = "tf2_msgs/msg/TFMessage"
    JOINT_STATES = "sensor_msgs/msg/JointState"


NANOSECONDS_PER_SECOND = 1_000_000_000
"""
A recording stamps its messages in nanoseconds; a frame is stated in seconds.
"""

DEFAULT_REFERENCE_FRAME = "map"
"""
The frame the recordings root their transform tree in unless another is named.
"""

message_definitions = get_typestore(Stores.ROS2_HUMBLE)
"""
The message definitions a recording is read with.
"""

# %% the transform tree


@dataclass
class TransformTree:
    """
    The latest known pose of every frame in its parent, as the recording published them.
    """

    parent_of: Dict[str, str] = field(default_factory=dict)
    """
    The frame each frame hangs off.
    """

    transform_to: Dict[str, np.ndarray] = field(default_factory=dict)
    """
    Each frame's pose in its parent, as a 4x4 homogeneous transformation.
    """

    def record(self, transform) -> None:
        """
        Keep a stamped transform as the latest pose of its child frame.

        :param transform: The ``geometry_msgs/msg/TransformStamped`` message.
        """
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        self.parent_of[transform.child_frame_id] = transform.header.frame_id
        self.transform_to[transform.child_frame_id] = (
            HomogeneousTransformationMatrix.from_xyz_quaternion(
                translation.x,
                translation.y,
                translation.z,
                rotation.x,
                rotation.y,
                rotation.z,
                rotation.w,
            ).to_np()
        )

    def knows(self, frame: str) -> bool:
        """
        Whether the recording has published a transform to or from a frame.
        """
        return frame in self.parent_of or frame in self.parent_of.values()

    def pose_of(self, frame: str, reference_frame: str) -> Optional[np.ndarray]:
        """
        Compose the chain from a frame up to the one it is wanted in.

        :param frame: The frame whose pose is wanted.
        :param reference_frame: The frame to express it in.
        :return: The pose as a 4x4 homogeneous transformation, or ``None`` if the chain
            does not reach the reference frame.
        """
        pose = np.eye(4)
        current = frame
        while current != reference_frame:
            if current not in self.parent_of:
                return None
            pose = self.transform_to[current] @ pose
            current = self.parent_of[current]
        return pose

    def poses_in(self, reference_frame: str) -> Dict[str, np.ndarray]:
        """
        The pose of every frame whose chain reaches the reference frame.

        :param reference_frame: The frame to express the poses in.
        """
        poses = {}
        for frame in self.parent_of:
            pose = self.pose_of(frame, reference_frame)
            if pose is not None:
                poses[frame] = pose
        return poses


# %% the player


@dataclass(eq=False)
class RosbagPlayer(FilePlayer):
    """
    Plays an episode from a rosbag holding the robot's transform tree and joint states.

    ``file_path`` is the directory of the recording. A frame is a snapshot of the latest
    transform of every frame and the latest position of every joint, taken every
    ``sampling_period`` from the first transform or joint state message to the last; a
    frame's time is the recording's own.
    """

    reference_frame: str = DEFAULT_REFERENCE_FRAME
    """
    The frame of the recording that stands for the world's root; poses are expressed in
    it.
    """

    sampling_period: timedelta = field(
        default_factory=lambda: timedelta(milliseconds=100)
    )
    """
    How far apart along the recording's clock the frames are taken.
    """

    body_name_of_frame: Dict[str, str] = field(default_factory=dict)
    """
    The body each frame of the recording names, where the two are not spelled the same.

    A frame not listed names the body of its own name.
    """

    def get_frame_data_generator(self) -> FrameDataGenerator:
        """
        Sample the recording into frames, refusing a recording with nothing to replay.

        :raises RecordingHoldsNothingToReplay: If the recording carries none of the
            replayed topics.
        """
        with Reader(self.recording) as reader:
            recorded_topics = [
                topic for topic in RosbagTopic if str(topic) in reader.topics
            ]
        if not recorded_topics:
            raise RecordingHoldsNothingToReplay(
                self.recording, [str(topic) for topic in RosbagTopic]
            )
        return self._sample()

    @property
    def recording(self) -> Path:
        """
        The directory of the recording.
        """
        return Path(self.file_path)

    def _sample(self) -> Iterator[FrameData]:
        tree = TransformTree()
        joint_positions: Dict[str, float] = {}
        first_sample_time: Optional[float] = None
        sample_count = 0
        last_message_time = 0.0
        period = self.sampling_period.total_seconds()

        def next_sample_time() -> float:
            return first_sample_time + sample_count * period

        def frame_at(sample_time: float) -> FrameData:
            if not tree.knows(self.reference_frame):
                raise ReferenceFrameNotRecorded(self.reference_frame, self.recording)
            return FrameData(
                time=sample_time,
                objects_data=tree.poses_in(self.reference_frame),
                frame_idx=sample_count,
                joint_positions=dict(joint_positions),
            )

        with Reader(self.recording) as reader:
            connections = [
                connection
                for connection in reader.connections
                if connection.topic in {str(topic) for topic in RosbagTopic}
            ]
            for connection, timestamp, raw in reader.messages(connections=connections):
                message = message_definitions.deserialize_cdr(raw, connection.msgtype)
                if connection.topic == RosbagTopic.STATIC_TRANSFORMS:
                    for transform in message.transforms:
                        tree.record(transform)
                    continue
                message_time = timestamp / NANOSECONDS_PER_SECOND
                last_message_time = message_time
                if first_sample_time is None:
                    first_sample_time = message_time
                while next_sample_time() < message_time:
                    yield frame_at(next_sample_time())
                    sample_count += 1
                if connection.topic == RosbagTopic.TRANSFORMS:
                    for transform in message.transforms:
                        tree.record(transform)
                else:
                    joint_positions.update(zip(message.name, message.position))
            if first_sample_time is None:
                return
            while next_sample_time() <= last_message_time:
                yield frame_at(next_sample_time())
                sample_count += 1

    def get_objects_poses(self, frame_data: FrameData) -> Dict[Body, Pose]:
        """
        The pose of every free body a frame of the recording names, in the world's root.

        A body is free when its parent connection is a :class:`Connection6DoF`; a robot
        link, whose frame the recording also publishes, is positioned by its joint
        instead.

        :param frame_data: The frame data.
        :return: The poses of the free bodies.
        """
        poses: Dict[Body, Pose] = {}
        for frame, matrix in frame_data.objects_data.items():
            body = self._free_body_named_by(frame)
            if body is None:
                continue
            pose = HomogeneousTransformationMatrix(
                data=matrix, reference_frame=self.world.root
            ).to_pose()
            pose.timestamp = frame_data.time
            poses[body] = pose
        return poses

    def get_joint_positions(
        self, frame_data: FrameData
    ) -> Dict[ActiveConnection1DOF, float]:
        """
        The position of every joint of the world a frame of the recording names.

        :param frame_data: The frame data.
        :return: The position of each named connection.
        """
        joints = self._joints_by_name()
        return {
            joints[name]: position
            for name, position in frame_data.joint_positions.items()
            if name in joints
        }

    def _free_body_named_by(self, frame: str) -> Optional[Body]:
        body = self._bodies_by_name().get(self.body_name_of_frame.get(frame, frame))
        if body is None or not isinstance(body.parent_connection, Connection6DoF):
            return None
        return body

    def _bodies_by_name(self) -> Dict[str, Body]:
        return {body.name.name: body for body in self.world.bodies}

    def _joints_by_name(self) -> Dict[str, ActiveConnection1DOF]:
        return {
            connection.name.name: connection
            for connection in self.world.connections
            if isinstance(connection, ActiveConnection1DOF)
        }

    def _pause(self):
        """
        Nothing beyond the paused status is needed to hold a recording.
        """

    def _resume(self):
        """
        Nothing beyond the playing status is needed to resume a recording.
        """
