"""
Tests for a bag written by a process of its own: the recording happens outside the
run's interpreter, its bag holds what was published while it ran, and a recorder that
cannot start is reported to the run that asked for it.
"""

from __future__ import annotations

import os
import threading
import time

import pytest
import rclpy
import rosbag2_py
from rclpy.node import Node
from std_msgs.msg import String
from typing_extensions import Iterator

from experiments.tracy_experiments.rosbag_recording import (
    RosbagRecorder,
    RosbagRecordingFailed,
    RosbagRecordingProcess,
)

A_TOPIC = "/rosbag_recording_process_test/words"
"""
The topic the test publishes on and records.
"""

A_TOPIC_NOBODY_PUBLISHES = "/rosbag_recording_process_test/silence"
"""
A topic no node publishes, so a recorder asked for it alone cannot start.
"""

PUBLISHING_PERIOD_SECONDS = 0.02
"""
How often a word is published while the bag records.
"""

RECORDING_SECONDS = 1.0
"""
How long the test keeps the bag open.
"""


@pytest.fixture(scope="module")
def ros() -> Iterator[None]:
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def publishing(ros: None) -> Iterator[Node]:
    """
    A node publishing a word on :data:`A_TOPIC` for as long as the test runs.
    """
    node = rclpy.create_node("rosbag_recording_process_test")
    publisher = node.create_publisher(String, A_TOPIC, 10)
    stop = threading.Event()

    def publish() -> None:
        while not stop.is_set():
            publisher.publish(String(data="word"))
            time.sleep(PUBLISHING_PERIOD_SECONDS)

    thread = threading.Thread(target=publish, daemon=True)
    thread.start()
    yield node
    stop.set()
    thread.join()
    node.destroy_node()


def messages_recorded(bag_directory: str) -> dict[str, int]:
    """
    How many messages a bag holds per topic.

    :param bag_directory: The bag to read.
    """
    metadata = rosbag2_py.Info().read_metadata(bag_directory, "mcap")
    return {
        entry.topic_metadata.name: entry.message_count
        for entry in metadata.topics_with_message_count
    }


# %% recording apart from the run


def test_the_bag_is_written_by_another_process(tmp_path, publishing: Node):
    bag = str(tmp_path / "bag")

    with RosbagRecordingProcess(
        RosbagRecorder(output_directory=bag, topics=[A_TOPIC])
    ) as recording:
        assert recording.process_id != os.getpid()
        time.sleep(RECORDING_SECONDS)

    assert messages_recorded(bag)[A_TOPIC] > 0


def test_the_recording_process_names_the_bag_it_writes(tmp_path, publishing: Node):
    bag = str(tmp_path / "bag")

    with RosbagRecordingProcess(
        RosbagRecorder(output_directory=bag, topics=[A_TOPIC])
    ) as recording:
        assert recording.output_directory == bag


def test_a_recorder_that_cannot_start_fails_the_run_that_asked_for_it(
    tmp_path, ros: None
):
    recorder = RosbagRecorder(
        output_directory=str(tmp_path / "bag"),
        topics=[A_TOPIC_NOBODY_PUBLISHES],
        startup_timeout=0.5,
    )

    with pytest.raises(RosbagRecordingFailed):
        with RosbagRecordingProcess(recorder):
            pass
