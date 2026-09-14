"""
The framework figure's two pictures of Tracy, cut out of a bag its framework demo
recorded on the robot.

The figure shows the robot twice: before it acts, and inserting the cube. Both are taken
through the robot's own camera, which is the only camera a run records. The first is the
first colour frame of the recording, before the arm has moved; the second is the frame
nearest the moment the fingers let go of the piece they carried, read off the knuckle
joint's own positions in the same recording.

Run with::

    python -m experiments.tracy_experiments.bag_frames <bag directory> \
        [--output-directory experiments/doc/figures/framework]
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import cv2
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import JointState
from typing_extensions import List, Optional, Sequence

import experiments
from coraplex.datastructures.enums import Arms
from experiments.montessori.perception.camera import decode_compressed_color_image
from experiments.montessori.perception.recordings import (
    RecordedCamera,
    RecordedImages,
    open_bag,
)
from experiments.tracy_experiments.montessori.gripper_feedback import (
    FULLY_CLOSED_KNUCKLE_POSITION,
    OPEN_KNUCKLE_POSITION,
    gripper_joint_state_topic,
    knuckle_joint_name,
)
from krrood.exceptions import DataclassException

logger = logging.getLogger(__name__)

HOLDING_KNUCKLE_POSITION = (OPEN_KNUCKLE_POSITION + FULLY_CLOSED_KNUCKLE_POSITION) / 2
"""
Knuckle position, in radians, past which the fingers count as closed on something, which
is halfway between fully open and fully closed.
"""

FIRST_FRAME = 0.0
"""
How far into the recording the picture of the robot before it acts is taken: at its very
start.
"""

FRAMEWORK_FIGURE_DIRECTORY = (
    Path(experiments.__file__).parents[2] / "doc" / "figures" / "framework"
)
"""
The directory the framework figure reads its pictures of Tracy from.
"""


class FigureFrame(StrEnum):
    """
    The framework figure's two pictures of Tracy, by the file the figure reads each
    from.
    """

    BEFORE_IT_ACTS = "tracy_idle.png"
    INSERTING = "tracy_inserting.png"


# %% when the fingers let go


@dataclass(frozen=True)
class KnuckleReading:
    """
    One position the knuckle joint was recorded at.
    """

    stamp: int
    """
    When it was recorded, in nanoseconds since the epoch on the recording machine's wall
    clock.
    """

    position: float
    """
    The knuckle's position, in radians.
    """


@dataclass
class NoReleaseRecordedError(DataclassException):
    """
    Raised when a recording holds no moment the fingers let go of something they held.
    """

    readings: int
    """
    How many knuckle readings the recording held.
    """

    def error_message(self) -> str:
        return (
            f"None of the {self.readings} knuckle readings shows the fingers opening "
            f"after they had closed on something."
        )

    def suggest_correction(self) -> str:
        return (
            "Record the bag for the whole run, so it spans the insertion's release, and "
            "read the arm that carried the piece."
        )


def last_release(readings: Sequence[KnuckleReading]) -> int:
    """
    The last moment the fingers stood open again after holding something.

    :param readings: The knuckle's positions, in the order they were recorded.
    :return: The stamp of the first reading open again after the last one closed.
    :raises NoReleaseRecordedError: If the fingers never closed, or never opened again
        after they last did.
    """
    release: Optional[int] = None
    holding = False
    for reading in readings:
        closed = reading.position >= HOLDING_KNUCKLE_POSITION
        if holding and not closed:
            release = reading.stamp
        holding = closed
    if release is None or holding:
        raise NoReleaseRecordedError(readings=len(readings))
    return release


def knuckle_readings(bag: Path, arm: Arms) -> List[KnuckleReading]:
    """
    :param bag: Directory of the recording.
    :param arm: The arm whose gripper is read.
    :return: Every position the arm's knuckle joint was recorded at, in order.
    """
    joint = knuckle_joint_name(arm)
    reader = open_bag(bag, [gripper_joint_state_topic(arm)])
    readings = []
    while reader.has_next():
        _, payload, stamp = reader.read_next()
        message = deserialize_message(payload, JointState)
        if joint in message.name:
            readings.append(
                KnuckleReading(
                    stamp=stamp, position=message.position[message.name.index(joint)]
                )
            )
    return readings


# %% the pictures


@dataclass
class FigureFramesFromBag:
    """
    The framework figure's two pictures of Tracy, as one recording shows them.
    """

    bag: Path
    """
    Directory of the recording.
    """

    arm: Arms = Arms.LEFT
    """
    The arm that carried the piece, whose fingers letting go marks the insertion.
    """

    @property
    def camera(self) -> RecordedCamera:
        """
        The robot's camera, as the recording holds it.
        """
        return RecordedCamera(bag=self.bag)

    def before_it_acts(self) -> RecordedImages:
        """
        What the camera showed before the robot moved.
        """
        return self.camera.image_at(FIRST_FRAME)

    def inserting(self) -> RecordedImages:
        """
        What the camera showed as the fingers let go of the piece over its hole.

        :raises NoReleaseRecordedError: If the recording holds no release.
        """
        return self.camera.image_nearest(
            last_release(knuckle_readings(self.bag, self.arm))
        )

    def write(self, directory: Path) -> List[Path]:
        """
        Write both pictures where the figure reads them from.

        :param directory: The directory the figure reads its pictures from.
        :return: The files written.
        """
        written = []
        for frame, images in (
            (FigureFrame.BEFORE_IT_ACTS, self.before_it_acts()),
            (FigureFrame.INSERTING, self.inserting()),
        ):
            path = directory / frame
            cv2.imwrite(
                str(path),
                decode_compressed_color_image(
                    images.color_payload, images.color_format
                ),
            )
            written.append(path)
        return written


def main(argument_list: Optional[Sequence[str]] = None) -> None:
    """
    Cut the figure's two pictures of Tracy out of a recording.

    :param argument_list: Arguments to read; the process's own when omitted.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path, help="directory of the recording")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=FRAMEWORK_FIGURE_DIRECTORY,
        help="where the figure reads its pictures of Tracy from",
    )
    arguments = parser.parse_args(argument_list)
    for path in FigureFramesFromBag(bag=arguments.bag).write(
        arguments.output_directory
    ):
        logger.info("Wrote %s.", path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", force=True)
    main()
