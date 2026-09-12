"""
Record a rosbag for the span of a demo's execution, optionally keeping only every Nth
frame of the heavy camera streams.

A demo wraps the part of its run worth capturing in a :class:`RosbagRecorder`, which
subscribes to the topics and writes them itself rather than shelling out to ``ros2 bag
record`` -- that has no way to thin a stream, and the camera's registered depth and point
cloud dominate a bag so completely that recording them whole is often not practical.

Messages are subscribed to and written back *serialized*, so nothing is ever
deserialized: decimating a 23 MB point cloud costs a counter increment, not a parse.

The recorder is a context manager rather than a start/stop pair so an exception mid-plan
still closes the bag: a bag that was never closed has no metadata and does not replay.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

import rclpy
import rosbag2_py
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile
from rosidl_runtime_py.utilities import get_message
from typing_extensions import Dict, List, Optional

logger = logging.getLogger(__name__)

# %% topic selection

CAMERA_TOPICS = [
    "/camera/color/image_raw/compressed",
    "/camera/color/camera_info",
    "/camera/depth/image_raw",
    "/camera/depth/camera_info",
    "/camera/depth_registered/points",
]
"""
Colour, depth and registered point-cloud topics of the Orbbec Femto Mega.

The colour stream is taken compressed: at the camera's configured 1920x1080 the raw
topic dominates the bag, and colour is the one stream that survives lossy compression
without losing what the recording is for. Depth stays raw, where a lossy codec would
corrupt the measurement itself.

``depth_registered`` rather than ``depth`` for the cloud, since ``tracy_ros2.launch.py``
brings the camera up with ``depth_registration`` and ``enable_colored_point_cloud``.
"""

JOINT_STATE_TOPICS = [
    "/left_arm/joint_states",
    "/right_arm/joint_states",
    "/left_gripper/joint_states",
    "/right_gripper/joint_states",
    "/joint_states",
]
"""
Per-arm and per-gripper joint states, plus the merged ``/joint_states`` the demo's own
``joint_state_publisher`` produces.
"""

TRANSFORM_TOPICS = ["/tf", "/tf_static"]
"""
Transforms, without which the recorded images and joint states cannot be placed relative
to each other on replay.
"""

DEFAULT_TOPICS = CAMERA_TOPICS + JOINT_STATE_TOPICS + TRANSFORM_TOPICS
"""
What :class:`RosbagRecorder` records unless given its own list.
"""

DECIMATED_TOPICS = [
    "/camera/color/image_raw/compressed",
    "/camera/depth/image_raw",
    "/camera/depth_registered/points",
]
"""
Topics :attr:`RosbagRecorder.keep_every_nth_frame` thins.

The image and cloud streams only -- they are effectively all of a bag's size. Joint
states, transforms and camera infos are together well under a percent of it, and thinning
them would cost motion fidelity and replayability to save nothing.

``camera_info`` is excluded deliberately: it is tiny and constant, and a consumer that
cannot find one alongside a thinned image stream cannot use the images at all.
"""

SUBSCRIPTION_QUEUE_DEPTH = 100
"""
How many messages a recording subscription buffers.

Deep enough to ride out a write stall without dropping frames, and to receive the whole
latched backlog of a transient-local topic such as ``/tf_static``.
"""

DEFAULT_BAG_DIRECTORY = "~/tracy_bags"
"""
Where :meth:`RosbagRecorder.timestamped` puts bags unless told otherwise.

Deliberately outside any source tree: a run of the demo produces tens of gigabytes, and
writing that next to the code it was launched from puts it in reach of the next
``git add``.
"""


# %% failures


class RosbagRecordingFailed(RuntimeError):
    """
    Raised when recording cannot start: a topic never appeared, or the bag could not be
    opened.
    """


# %% counting frames


@dataclass
class FrameCounter:
    """
    Decides which of a topic's messages are written, keeping one in every
    :attr:`keep_every_nth`.

    The first message a topic delivers is always kept, so a thinned stream starts at the
    beginning of the recording rather than ``keep_every_nth`` frames into it.
    """

    keep_every_nth: int
    """
    Keep one message in this many. ``1`` keeps everything.
    """

    seen: int = 0
    """
    How many messages have been offered so far.
    """

    kept: int = 0
    """
    How many messages have been written so far.
    """

    def wants(self) -> bool:
        """
        :return: Whether the message being offered now should be written.
        """
        keep = self.seen % self.keep_every_nth == 0
        self.seen += 1
        if keep:
            self.kept += 1
        return keep


# %% recorder


@dataclass
class RosbagRecorder:
    """
    Records ``topics`` to a rosbag for as long as its ``with`` block runs.

    ..note:: Recording the depth and point-cloud streams whole is heavy -- around
        230 MB of disk per second of wall clock at the camera's configured 1920x1080.
        See :attr:`keep_every_nth_frame`.
    """

    output_directory: str
    """
    Directory the bag is written to. Must not already exist.
    """

    topics: List[str] = field(default_factory=lambda: list(DEFAULT_TOPICS))
    """
    Topics to record. See :data:`DEFAULT_TOPICS`.
    """

    keep_every_nth_frame: int = 1
    """
    Keep only one in this many messages of each of :data:`DECIMATED_TOPICS`. ``1``, the
    default, records every frame.
    """

    startup_timeout: float = 20.0
    """
    Seconds to wait for the recorded topics to be discovered. A topic nobody publishes
    within this is reported and left out rather than failing the run.
    """

    _node: Optional[Node] = field(init=False, default=None, repr=False)
    """
    The recorder's own node, separate from the demo's so heavy writes never block it.
    """

    _writer: Optional[rosbag2_py.SequentialWriter] = field(
        init=False, default=None, repr=False
    )
    """
    The open bag, or ``None`` outside the ``with`` block.
    """

    _executor: Optional[SingleThreadedExecutor] = field(
        init=False, default=None, repr=False
    )
    """
    Spins :attr:`_node`. Single-threaded, so writes to the bag are serialised without a
    lock.
    """

    _thread: Optional[threading.Thread] = field(init=False, default=None, repr=False)
    """
    Runs :attr:`_executor` for the duration of the block.
    """

    _stopping: threading.Event = field(
        init=False, default_factory=threading.Event, repr=False
    )
    """
    Set to ask :attr:`_thread` to stop spinning.
    """

    counters: Dict[str, FrameCounter] = field(
        init=False, default_factory=dict, repr=False
    )
    """
    The :class:`FrameCounter` of every subscribed topic, by topic name.
    """

    @classmethod
    def timestamped(
        cls, prefix: str, parent_directory: str = DEFAULT_BAG_DIRECTORY, **kwargs
    ) -> "RosbagRecorder":
        """
        A recorder writing to ``<parent_directory>/<prefix>_<timestamp>``, so
        consecutive runs of a demo do not collide.

        :param prefix: Leading part of the bag directory's name.
        :param parent_directory: Where the bag is placed; ``~`` is expanded and the
            directory is created if missing. See :data:`DEFAULT_BAG_DIRECTORY`.
        :param kwargs: Passed on to the constructor.
        """
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parent = os.path.expanduser(parent_directory)
        os.makedirs(parent, exist_ok=True)
        return cls(output_directory=os.path.join(parent, f"{prefix}_{stamp}"), **kwargs)

    def keep_every_nth_frame_of(self, topic: str) -> int:
        """
        How many messages of ``topic`` one is kept out of.

        :param topic: The topic being recorded.
        :return: :attr:`keep_every_nth_frame` for a stream in :data:`DECIMATED_TOPICS`,
            otherwise ``1``.
        """
        if topic in DECIMATED_TOPICS:
            return self.keep_every_nth_frame
        return 1

    def __enter__(self) -> "RosbagRecorder":
        """
        Open the bag and subscribe, returning once every discoverable topic is
        subscribed.

        :raises RosbagRecordingFailed: If the bag cannot be opened, or none of the
            requested topics was ever published.
        """
        if self.keep_every_nth_frame < 1:
            raise RosbagRecordingFailed(
                f"keep_every_nth_frame must be at least 1, got "
                f"{self.keep_every_nth_frame}."
            )

        self._node = rclpy.create_node("tracy_rosbag_recorder")
        self._writer = rosbag2_py.SequentialWriter()
        self._writer.open(
            rosbag2_py.StorageOptions(uri=self.output_directory, storage_id="mcap"),
            rosbag2_py.ConverterOptions("", ""),
        )
        self._subscribe_to_available_topics()

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._thread = threading.Thread(
            target=self._spin_until_stopped, daemon=True, name="rosbag-recorder"
        )
        self._thread.start()
        return self

    def _spin_until_stopped(self) -> None:
        """
        Spin the recorder's node until :attr:`_stopping` is set.

        Polls rather than calling ``spin``, which can only be stopped by shutting the
        executor down underneath it -- that races the spinning thread and tears down the
        guard condition it is waiting on.
        """
        while not self._stopping.is_set():
            self._executor.spin_once(timeout_sec=0.1)

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        """
        Stop recording and close the bag.

        Never suppresses an exception from the block: a bag of a failed run is still
        worth having, and the failure itself is what the caller needs to see.
        """
        self._stop()

    def _subscribe_to_available_topics(self) -> None:
        """
        Subscribe to every requested topic that some node publishes, matching each
        publisher's own quality of service.

        Matching the publisher matters beyond throughput: ``/tf_static`` is published
        transient-local and latched, and a subscription that asked for the default
        volatile profile would record none of it.

        :raises RosbagRecordingFailed: If none of the requested topics was published
            within :attr:`startup_timeout`.
        """
        available = self._wait_for_topic_types()
        missing = [topic for topic in self.topics if topic not in available]
        if missing:
            logger.warning("Not recording (nobody publishes them): %s", missing)
        if not available:
            raise RosbagRecordingFailed(
                f"None of {self.topics} was published within {self.startup_timeout} "
                f"seconds; nothing to record."
            )

        for topic, type_name in available.items():
            self._writer.create_topic(
                rosbag2_py.TopicMetadata(
                    id=0,
                    name=topic,
                    type=type_name,
                    serialization_format="cdr",
                )
            )
            keep_every_nth = self.keep_every_nth_frame_of(topic)
            self.counters[topic] = FrameCounter(keep_every_nth=keep_every_nth)
            self._node.create_subscription(
                get_message(type_name),
                topic,
                self._writer_for(topic),
                self._subscription_qos_for(topic),
                raw=True,
            )
            thinning = "" if keep_every_nth == 1 else f" (every {keep_every_nth}th)"
            logger.info("Recording %s%s.", topic, thinning)

    def _subscription_qos_for(self, topic: str) -> QoSProfile:
        """
        A profile that matches ``topic``'s publisher closely enough to receive it.

        Only the reliability and durability are taken from the publisher, since those
        are what a subscription has to agree on to match at all -- ``/tf_static`` is
        transient-local, and a volatile subscription records none of it. The publisher's
        reported history cannot be reused: a discovered endpoint comes back with
        ``HistoryPolicy.UNKNOWN`` and a depth of ``0``, which is rejected as an invalid
        profile.

        :param topic: The topic being subscribed to.
        """
        publishers = self._node.get_publishers_info_by_topic(topic)
        profile = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=SUBSCRIPTION_QUEUE_DEPTH
        )
        if publishers:
            profile.reliability = publishers[0].qos_profile.reliability
            profile.durability = publishers[0].qos_profile.durability
        return profile

    def _wait_for_topic_types(self) -> Dict[str, str]:
        """
        Wait for the requested topics to be discovered.

        :return: The message type of every requested topic that is published, by topic
            name. Returns as soon as all of them are found, or when
            :attr:`startup_timeout` expires with whichever were.
        """
        deadline = time.monotonic() + self.startup_timeout
        found: Dict[str, str] = {}
        while time.monotonic() < deadline and len(found) < len(self.topics):
            published = dict(self._node.get_topic_names_and_types())
            found = {
                topic: published[topic][0]
                for topic in self.topics
                if topic in published and published[topic]
            }
            if len(found) == len(self.topics):
                break
            time.sleep(0.2)
        return found

    def _writer_for(self, topic: str):
        """
        The subscription callback writing ``topic``'s kept messages to the bag.

        :param topic: The topic the callback is for.
        """
        counter = self.counters[topic]

        def write_if_kept(serialized_message) -> None:
            if not counter.wants():
                return
            self._writer.write(
                topic,
                bytes(serialized_message),
                self._node.get_clock().now().nanoseconds,
            )

        return write_if_kept

    def _stop(self) -> None:
        """
        Stop spinning and close the bag, so its metadata is written and it replays.
        """
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        if self._executor is not None:
            self._executor.shutdown()
        if self._node is not None:
            self._node.destroy_node()
        # Releasing the writer is what finalises the bag; there is no explicit close.
        self._writer = None
        self._executor = None
        self._thread = None
        self._node = None
        self._log_what_was_kept()

    def _log_what_was_kept(self) -> None:
        """
        Report how much of each thinned stream was written.
        """
        logger.info("Recording stopped; bag written to %s.", self.output_directory)
        for topic, counter in self.counters.items():
            if counter.keep_every_nth == 1:
                continue
            logger.info(
                "  %s: kept %d of %d frames.", topic, counter.kept, counter.seen
            )
