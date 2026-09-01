"""
A small episode written into a rosbag, for tests of the rosbag player.

The recordings taken off the real robot are gigabytes and gitignored, so a test writes
the few messages it needs into a bag of its own and replays that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from rosbags.rosbag2 import StoragePlugin, Writer
from rosbags.typesys import Stores, get_typestore
from typing_extensions import Dict, List, Tuple

from segmind.players.rosbag_player import (
    NANOSECONDS_PER_SECOND,
    RosbagMessageType,
    RosbagTopic,
)

# %% messages

typestore = get_typestore(Stores.ROS2_HUMBLE)
"""
The message definitions the bag is written with.
"""

BAG_FORMAT_VERSION = 9
"""
The rosbag2 metadata version written.
"""


def _stamp(time: float):
    seconds = int(time)
    return typestore.types["builtin_interfaces/msg/Time"](
        sec=seconds, nanosec=int(round((time - seconds) * NANOSECONDS_PER_SECOND))
    )


def _header(time: float, frame: str):
    return typestore.types["std_msgs/msg/Header"](stamp=_stamp(time), frame_id=frame)


# %% what an episode holds


@dataclass(frozen=True)
class RecordedTransform:
    """
    The pose of one frame in its parent, as a transform message states it.
    """

    parent_frame: str
    """
    The frame the pose is stated in.
    """

    child_frame: str
    """
    The frame whose pose it is.
    """

    translation: Tuple[float, float, float]
    """
    Position of the child frame in the parent frame.
    """

    rotation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    """
    Orientation of the child frame in the parent frame, as a quaternion ``(x, y, z,
    w)``.
    """

    def to_message(self, time: float):
        """
        Build the stamped transform message for this transform at a time.

        :param time: The time in seconds the transform is published at.
        """
        types = typestore.types
        return types["geometry_msgs/msg/TransformStamped"](
            header=_header(time, self.parent_frame),
            child_frame_id=self.child_frame,
            transform=types["geometry_msgs/msg/Transform"](
                translation=types["geometry_msgs/msg/Vector3"](*self.translation),
                rotation=types["geometry_msgs/msg/Quaternion"](*self.rotation),
            ),
        )


@dataclass(frozen=True)
class TransformsAt:
    """
    The transforms one message publishes at one time.
    """

    time: float
    """
    The time in seconds the message is published at.
    """

    transforms: List[RecordedTransform]
    """
    The transforms the message carries.
    """


@dataclass(frozen=True)
class JointPositionsAt:
    """
    The joint positions one message publishes at one time.
    """

    time: float
    """
    The time in seconds the message is published at.
    """

    positions: Dict[str, float]
    """
    The position of each joint, by the joint's name.
    """


@dataclass
class RecordedEpisode:
    """
    The transforms and joint states of an episode, and how to write them into a bag.
    """

    static_transforms: List[RecordedTransform] = field(default_factory=list)
    """
    Transforms published once, on the static transform topic.
    """

    transforms: List[TransformsAt] = field(default_factory=list)
    """
    Transforms published over time.
    """

    joint_positions: List[JointPositionsAt] = field(default_factory=list)
    """
    Joint positions published over time.
    """

    def write(self, directory: Path) -> Path:
        """
        Write the episode as a rosbag.

        :param directory: Where to write the bag; must not exist yet.
        :return: The directory of the bag.
        """
        with Writer(
            directory, version=BAG_FORMAT_VERSION, storage_plugin=StoragePlugin.MCAP
        ) as writer:
            self._write_static_transforms(writer)
            self._write_transforms(writer)
            self._write_joint_positions(writer)
        return directory

    def _write_static_transforms(self, writer: Writer) -> None:
        if not self.static_transforms:
            return
        connection = writer.add_connection(
            str(RosbagTopic.STATIC_TRANSFORMS),
            str(RosbagMessageType.TRANSFORMS),
            typestore=typestore,
        )
        time = self._first_time()
        message = typestore.types[str(RosbagMessageType.TRANSFORMS)](
            transforms=[
                transform.to_message(time) for transform in self.static_transforms
            ]
        )
        writer.write(connection, _nanoseconds(time), _serialized(message))

    def _write_transforms(self, writer: Writer) -> None:
        if not self.transforms:
            return
        connection = writer.add_connection(
            str(RosbagTopic.TRANSFORMS),
            str(RosbagMessageType.TRANSFORMS),
            typestore=typestore,
        )
        for published in self.transforms:
            message = typestore.types[str(RosbagMessageType.TRANSFORMS)](
                transforms=[
                    transform.to_message(published.time)
                    for transform in published.transforms
                ]
            )
            writer.write(connection, _nanoseconds(published.time), _serialized(message))

    def _write_joint_positions(self, writer: Writer) -> None:
        if not self.joint_positions:
            return
        connection = writer.add_connection(
            str(RosbagTopic.JOINT_STATES),
            str(RosbagMessageType.JOINT_STATES),
            typestore=typestore,
        )
        for published in self.joint_positions:
            message = typestore.types[str(RosbagMessageType.JOINT_STATES)](
                header=_header(published.time, ""),
                name=list(published.positions),
                position=np.array(list(published.positions.values()), dtype=float),
                velocity=np.array([], dtype=float),
                effort=np.array([], dtype=float),
            )
            writer.write(connection, _nanoseconds(published.time), _serialized(message))

    def _first_time(self) -> float:
        times = [published.time for published in self.transforms] + [
            published.time for published in self.joint_positions
        ]
        return min(times, default=0.0)


def _nanoseconds(time: float) -> int:
    return int(round(time * NANOSECONDS_PER_SECOND))


def _serialized(message) -> bytes:
    return typestore.serialize_cdr(message, message.__msgtype__)
