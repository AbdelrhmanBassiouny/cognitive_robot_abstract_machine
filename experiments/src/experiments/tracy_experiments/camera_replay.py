"""
Replay the camera streams out of a bag recorded by
:mod:`experiments.tracy_experiments.rosbag_recording`.

Only the camera topics are played. The bag also holds joint states and transforms, and
republishing those onto a live system would fight the real robot's own publishers and
corrupt the TF tree every other node reads -- so replaying them is not something this
offers by accident.

:mod:`~experiments.tracy_experiments.rosbag_recording` records colour compressed, so the
colour stream is decompressed back onto the raw topic during playback by default and the
bag replays as though the raw stream had been recorded.

Run with::

    python -m experiments.tracy_experiments.camera_replay <bag directory>
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field

import rosbag2_py
from typing_extensions import List, Optional

from experiments.tracy_experiments.rosbag_recording import CAMERA_TOPICS

logging.basicConfig(level=logging.INFO, format="%(message)s")

logger = logging.getLogger(__name__)

# %% transports

COMPRESSED_COLOUR_TOPIC = "/camera/color/image_raw/compressed"
"""
Colour topic as recorded. See
:data:`~experiments.tracy_experiments.rosbag_recording.CAMERA_TOPICS`.
"""

RAW_COLOUR_TOPIC = "/camera/color/image_raw"
"""
Colour topic the compressed stream is decompressed onto during playback, so tools that
only read raw images see the replay.
"""


# %% failures


class CameraReplayFailed(RuntimeError):
    """
    Raised when a bag cannot be replayed: it is missing, holds none of the camera
    topics, or ``ros2`` is not available.
    """


# %% bag inspection


def camera_topics_in(bag_directory: str) -> List[str]:
    """
    The camera topics a bag actually holds.

    Read from the bag's own metadata rather than assumed, so a bag recorded with a
    trimmed topic list replays the streams it has instead of silently playing nothing.

    :param bag_directory: The bag to inspect.
    :raises CameraReplayFailed: If the bag cannot be read, or holds no camera topic.
    """
    if not os.path.isdir(bag_directory):
        raise CameraReplayFailed(f"No bag directory at {bag_directory}.")

    metadata = rosbag2_py.Info().read_metadata(bag_directory, "")
    recorded = {
        topic.topic_metadata.name for topic in metadata.topics_with_message_count
    }
    present = [topic for topic in CAMERA_TOPICS if topic in recorded]
    if not present:
        raise CameraReplayFailed(
            f"{bag_directory} holds none of the camera topics {CAMERA_TOPICS}. "
            f"It has: {sorted(recorded)}"
        )
    return present


# %% replay


@dataclass
class CameraReplay:
    """
    Plays a bag's camera topics, optionally decompressing the colour stream back onto
    :data:`RAW_COLOUR_TOPIC` for the duration.
    """

    bag_directory: str
    """
    The bag to replay.
    """

    rate: float = 1.0
    """
    Playback speed multiplier.
    """

    loop: bool = False
    """
    Whether to restart the bag when it reaches the end.
    """

    start_offset: float = 0.0
    """
    Seconds into the bag to start at.
    """

    decompress_colour: bool = True
    """
    Whether to run an ``image_transport`` republisher alongside playback, so the
    compressed colour stream also appears on :data:`RAW_COLOUR_TOPIC`.
    """

    _processes: List[subprocess.Popen] = field(
        init=False, default_factory=list, repr=False
    )
    """
    The republisher and the player, in start order.
    """

    def play(self) -> None:
        """
        Replay the bag, returning when playback finishes or is interrupted.

        :raises CameraReplayFailed: If ``ros2`` is unavailable or the bag holds no
            camera topics.
        """
        if shutil.which("ros2") is None:
            raise CameraReplayFailed(
                "'ros2' is not on the PATH; source the ROS setup before replaying."
            )
        topics = camera_topics_in(self.bag_directory)
        logger.info(
            "Replaying %d camera topics from %s.", len(topics), self.bag_directory
        )
        for topic in topics:
            logger.info("  %s", topic)

        try:
            if self.decompress_colour and COMPRESSED_COLOUR_TOPIC in topics:
                self._start_colour_republisher()
            self._play_bag(topics)
        finally:
            self._stop_all()

    def _start_colour_republisher(self) -> None:
        """
        Start the ``image_transport`` node that decompresses colour onto
        :data:`RAW_COLOUR_TOPIC`.

        ``in_transport``/``out_transport`` are parameters rather than positional
        arguments; passed positionally the node silently keeps its ``raw`` default and
        republishes nothing useful.
        """
        logger.info("Decompressing colour onto %s.", RAW_COLOUR_TOPIC)
        self._processes.append(
            subprocess.Popen(
                [
                    "ros2",
                    "run",
                    "image_transport",
                    "republish",
                    "--ros-args",
                    "-p",
                    "in_transport:=compressed",
                    "-p",
                    "out_transport:=raw",
                    "-r",
                    f"in/compressed:={COMPRESSED_COLOUR_TOPIC}",
                    "-r",
                    f"out:={RAW_COLOUR_TOPIC}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        )
        # The republisher has to be subscribed before playback starts, or the opening
        # frames arrive with nothing listening and never reach the raw topic.
        time.sleep(1.0)

    def _play_bag(self, topics: List[str]) -> None:
        """
        Run ``ros2 bag play`` over ``topics`` and wait for it.

        :param topics: The topics to play.
        """
        command = [
            "ros2",
            "bag",
            "play",
            self.bag_directory,
            "--rate",
            str(self.rate),
            "--topics",
            *topics,
        ]
        if self.loop:
            command.append("--loop")
        if self.start_offset:
            command += ["--start-offset", str(self.start_offset)]

        player = subprocess.Popen(command, start_new_session=True)
        self._processes.append(player)
        try:
            player.wait()
        except KeyboardInterrupt:
            logger.info("Replay interrupted.")

    def _stop_all(self) -> None:
        """
        Stop every child process this replay started, youngest first.
        """
        for process in reversed(self._processes):
            if process.poll() is not None:
                continue
            os.killpg(os.getpgid(process.pid), signal.SIGINT)
            try:
                process.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
        self._processes.clear()


# %% entry point


def _parse_arguments() -> argparse.Namespace:
    """
    :return: The script's own command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Replay the camera streams from a Tracy demo bag."
    )
    parser.add_argument("bag_directory", help="The bag directory to replay.")
    parser.add_argument(
        "--rate", type=float, default=1.0, help="Playback speed multiplier."
    )
    parser.add_argument(
        "--loop", action="store_true", help="Restart the bag when it ends."
    )
    parser.add_argument(
        "--start-offset",
        type=float,
        default=0.0,
        help="Seconds into the bag to start at.",
    )
    parser.add_argument(
        "--no-decompress",
        dest="decompress_colour",
        action="store_false",
        help=(
            f"Leave the colour stream compressed instead of also publishing it on "
            f"{RAW_COLOUR_TOPIC}."
        ),
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()
    CameraReplay(
        bag_directory=arguments.bag_directory,
        rate=arguments.rate,
        loop=arguments.loop,
        start_offset=arguments.start_offset,
        decompress_colour=arguments.decompress_colour,
    ).play()


if __name__ == "__main__":
    main()
