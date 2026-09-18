"""
A small episode written into a rosbag, for tests of the rosbag player.

The recordings taken off the real robot are gigabytes and gitignored, so a test writes
the few messages it needs into a bag of its own and replays that.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from rosbags.rosbag2 import StoragePlugin, Writer
from typing_extensions import Any, Dict, List, Tuple

from segmind.players.rosbag_player import (
    MESSAGE_DEFINITIONS,
    NANOSECONDS_PER_SECOND,
    RosbagMessageType,
    RosbagTopic,
)

# %% messages

BAG_FORMAT_VERSION = 9
"""
The rosbag2 metadata version written.
"""

UNSTAMPED_FRAME = ""
"""
The frame a message that describes no frame of its own states in its header.
"""


def stamp_of(time: float) -> Any:
    """
    Build the time message for an instant of the recording's own clock.

    :param time: The time in seconds.
    """
    seconds = int(time)
    return MESSAGE_DEFINITIONS.types[RosbagMessageType.TIME](
        sec=seconds, nanosec=int(round((time - seconds) * NANOSECONDS_PER_SECOND))
    )


def header_of(time: float, frame: str) -> Any:
    """
    Build the header a stamped message carries.

    :param time: The time in seconds the message is published at.
    :param frame: The frame the message states its content in.
    """
    return MESSAGE_DEFINITIONS.types[RosbagMessageType.HEADER](
        stamp=stamp_of(time), frame_id=frame
    )


def nanoseconds_of(time: float) -> int:
    """
    The instant a bag stamps a message at, from the time in seconds.

    :param time: The time in seconds.
    """
    return int(round(time * NANOSECONDS_PER_SECOND))


def serialized(message: Any) -> bytes:
    """
    The bytes a bag stores a message as.

    :param message: The message to serialize.
    """
    return MESSAGE_DEFINITIONS.serialize_cdr(message, message.__msgtype__)


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

    def to_message(self, time: float) -> Any:
        """
        Build the stamped transform message for this transform at a time.

        :param time: The time in seconds the transform is published at.
        """
        types = MESSAGE_DEFINITIONS.types
        return types[RosbagMessageType.STAMPED_TRANSFORM](
            header=header_of(time, self.parent_frame),
            child_frame_id=self.child_frame,
            transform=types[RosbagMessageType.TRANSFORM](
                translation=types[RosbagMessageType.VECTOR](*self.translation),
                rotation=types[RosbagMessageType.QUATERNION](*self.rotation),
            ),
        )


@dataclass(frozen=True)
class PublishedMessage(ABC):
    """
    One message of the episode, and the time it is published at.
    """

    time: float
    """
    The time in seconds the message is published at.
    """

    @property
    def stamped_at(self) -> int:
        """
        The instant the bag stamps the message at, in nanoseconds.
        """
        return nanoseconds_of(self.time)

    @abstractmethod
    def to_message(self) -> Any:
        """
        Build the message, of the type its own topic carries.
        """


@dataclass(frozen=True)
class TransformsAt(PublishedMessage):
    """
    The transforms one message publishes at one time.
    """

    transforms: List[RecordedTransform] = field(default_factory=list)
    """
    The transforms the message carries.
    """

    def to_message(self) -> Any:
        """
        Build the transform message publishing all of them at this time.
        """
        return MESSAGE_DEFINITIONS.types[RosbagMessageType.TRANSFORMS](
            transforms=[
                transform.to_message(self.time) for transform in self.transforms
            ]
        )


@dataclass(frozen=True)
class JointPositionsAt(PublishedMessage):
    """
    The joint positions one message publishes at one time.
    """

    positions: Dict[str, float] = field(default_factory=dict)
    """
    The position of each joint, by the joint's name.
    """

    def to_message(self) -> Any:
        """
        Build the joint state message publishing all of them at this time.
        """
        return MESSAGE_DEFINITIONS.types[RosbagMessageType.JOINT_STATES](
            header=header_of(self.time, UNSTAMPED_FRAME),
            name=list(self.positions),
            position=np.array(list(self.positions.values()), dtype=float),
            velocity=np.array([], dtype=float),
            effort=np.array([], dtype=float),
        )


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
        """
        Write the static transforms as one message, stamped at the episode's start.

        :param writer: The writer of the bag being built.
        """
        if not self.static_transforms:
            return
        published = TransformsAt(self._first_time(), self.static_transforms)
        self._write(writer, RosbagTopic.STATIC_TRANSFORMS, [published])

    def _write_transforms(self, writer: Writer) -> None:
        """
        Write one transform message per time the episode publishes transforms at.

        :param writer: The writer of the bag being built.
        """
        self._write(writer, RosbagTopic.TRANSFORMS, self.transforms)

    def _write_joint_positions(self, writer: Writer) -> None:
        """
        Write one joint state message per time the episode publishes positions at.

        :param writer: The writer of the bag being built.
        """
        self._write(writer, RosbagTopic.JOINT_STATES, self.joint_positions)

    @staticmethod
    def _write(
        writer: Writer, topic: RosbagTopic, published: List[PublishedMessage]
    ) -> None:
        """
        Write every message of one topic, opening a connection only if there are any.

        :param writer: The writer of the bag being built.
        :param topic: The topic to publish them on.
        :param published: What is published, each carrying the time it is published at.
        """
        if not published:
            return
        connection = writer.add_connection(
            str(topic),
            str(topic.message_type),
            typestore=MESSAGE_DEFINITIONS,
        )
        for message in published:
            writer.write(
                connection, message.stamped_at, serialized(message.to_message())
            )

    def _first_time(self) -> float:
        """
        The time of the earliest message the episode publishes over time.
        """
        times = [published.time for published in self.transforms] + [
            published.time for published in self.joint_positions
        ]
        return min(times, default=0.0)
