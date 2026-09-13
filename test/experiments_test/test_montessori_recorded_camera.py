"""
Reading the camera back out of a recording by the moment a frame was taken.

A recording stamps every message with the wall clock it was written at, and a trial's
rows and artifacts count their seconds from the instant the trial began on that same
clock, so a frame is asked for by that stamp rather than by how far through the
recording it falls -- which only agrees with the trial where the recording began with
it and ended with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytest
import rosbag2_py
from rclpy.serialization import serialize_message
from sensor_msgs.msg import CompressedImage, Image
from typing_extensions import List, Sequence

from experiments.montessori.perception.camera import (
    CameraTopic,
    decode_compressed_color_image,
)
from experiments.montessori.perception.exceptions import NothingRecordedOnTopic
from experiments.montessori.perception.recordings import (
    RAW_DEPTH_TOPIC,
    REFERENCE_FRAME,
    STORAGE_IDENTIFIER,
    RecordedCamera,
)

# %% a recording of a few frames at known moments

FRAME_SIDE = 8
"""
Pixel width and height of the frames written here, which only have to tell each other
apart.
"""

A_SECOND = 1_000_000_000
"""
One second, in the nanoseconds a recording stamps its messages in.
"""

RECORDING_BEGAN_AT = 1_800_000_000 * A_SECOND
"""
The stamp of the first message of the recording, a moment of the wall clock in
nanoseconds since the epoch.
"""

DEPTH_BEFORE_COLOUR = A_SECOND // 100
"""
How long before each colour image its depth image was written, which is the pairing a
recording is read by.
"""


@dataclass(frozen=True)
class FrameTaken:
    """
    One colour frame of the recording, as one flat shade taken at one moment.
    """

    shade: int
    """
    The value every pixel of the frame carries, which is what tells it apart.
    """

    stamp: int
    """
    When it was written, in nanoseconds since the epoch.
    """


FRAMES_TAKEN = [
    FrameTaken(shade=10, stamp=RECORDING_BEGAN_AT),
    FrameTaken(shade=20, stamp=RECORDING_BEGAN_AT + 2 * A_SECOND),
    FrameTaken(shade=30, stamp=RECORDING_BEGAN_AT + 5 * A_SECOND),
]
"""
The frames the recording holds, unevenly spaced so that a place in the recording and a
moment of the wall clock do not coincide.
"""


def shade_of(image: np.ndarray) -> int:
    """
    The one shade a flat frame carries.

    :param image: The frame, every pixel of which carries the same value.
    """
    return int(image[0, 0, 0])


def compressed_colour(shade: int) -> CompressedImage:
    """
    A flat colour frame, encoded the way the camera publishes colour.

    :param shade: The value every pixel carries.
    """
    flat = np.full((FRAME_SIDE, FRAME_SIDE, 3), shade, dtype=np.uint8)
    encoded, payload = cv2.imencode(".png", flat)
    assert encoded
    message = CompressedImage()
    message.format = "png"
    message.data = payload.tobytes()
    return message


def raw_depth() -> Image:
    """
    A depth frame of one metre everywhere, in the raw encoding older recordings carry.
    """
    message = Image()
    message.height = FRAME_SIDE
    message.width = FRAME_SIDE
    message.encoding = "16UC1"
    message.step = FRAME_SIDE * 2
    message.data = np.full((FRAME_SIDE, FRAME_SIDE), 1000, dtype=np.uint16).tobytes()
    return message


def open_recording(directory: Path) -> rosbag2_py.SequentialWriter:
    """
    Open a recording to write the camera's colour and raw depth topics into.

    :param directory: Where the recording is written.
    """
    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(uri=str(directory), storage_id=STORAGE_IDENTIFIER),
        rosbag2_py.ConverterOptions("", ""),
    )
    for topic, message_type in (
        (str(CameraTopic.COLOR), CompressedImage),
        (RAW_DEPTH_TOPIC, Image),
    ):
        writer.create_topic(
            rosbag2_py.TopicMetadata(
                id=0,
                name=topic,
                type="sensor_msgs/msg/%s" % message_type.__name__,
                serialization_format="cdr",
            )
        )
    return writer


def write_colour(writer: rosbag2_py.SequentialWriter, frame: FrameTaken) -> None:
    """
    Write one colour frame under its stamp.
    """
    writer.write(
        str(CameraTopic.COLOR),
        serialize_message(compressed_colour(frame.shade)),
        frame.stamp,
    )


def write_depth_before(writer: rosbag2_py.SequentialWriter, frame: FrameTaken) -> None:
    """
    Write the depth image a colour frame is paired with, just before it.
    """
    writer.write(
        RAW_DEPTH_TOPIC,
        serialize_message(raw_depth()),
        frame.stamp - DEPTH_BEFORE_COLOUR,
    )


def write_recording(directory: Path, frames: Sequence[FrameTaken]) -> Path:
    """
    Leave a recording holding the given colour frames, each with a depth image written
    just before it.

    :param directory: Where the recording is written.
    :param frames: The frames, in the order they are written.
    :return: The recording's directory.
    """
    writer = open_recording(directory)
    for frame in frames:
        write_depth_before(writer, frame)
        write_colour(writer, frame)
    del writer
    return directory


@pytest.fixture
def camera(tmp_path: Path) -> RecordedCamera:
    """
    The camera of a recording holding :data:`FRAMES_TAKEN`.
    """
    return RecordedCamera(
        bag=write_recording(tmp_path / "recording", FRAMES_TAKEN),
        reference_frame=REFERENCE_FRAME,
    )


def shades_of(camera: RecordedCamera) -> List[int]:
    """
    The shade of every colour frame the camera yields, in order.
    """
    return [
        shade_of(
            decode_compressed_color_image(images.color_payload, images.color_format)
        )
        for images in camera.images()
    ]


# %% the stamps a recording places its frames at


def test_every_colour_frame_is_placed_at_the_stamp_it_was_written_under(
    camera: RecordedCamera,
) -> None:
    assert camera.colour_stamps() == [frame.stamp for frame in FRAMES_TAKEN]


def test_a_colour_frame_no_depth_was_written_before_is_not_placed_either(
    tmp_path: Path,
) -> None:
    """
    A colour frame published before any depth is skipped when the frames are read, so it
    is skipped when they are placed too, or the stamps and the frames would count
    differently.
    """
    unpaired_then_paired = tmp_path / "recording"
    unpaired, paired = FRAMES_TAKEN[0], FRAMES_TAKEN[1]
    writer = open_recording(unpaired_then_paired)
    write_colour(writer, unpaired)
    write_depth_before(writer, paired)
    write_colour(writer, paired)
    del writer
    camera = RecordedCamera(bag=unpaired_then_paired, reference_frame=REFERENCE_FRAME)

    assert camera.colour_stamps() == [paired.stamp]
    assert shades_of(camera) == [paired.shade]


# %% the frame nearest a moment


def frame_nearest(camera: RecordedCamera, stamp: int) -> int:
    """
    The shade of the frame the camera recorded nearest the given stamp.
    """
    images = camera.image_nearest(stamp)
    return shade_of(
        decode_compressed_color_image(images.color_payload, images.color_format)
    )


def test_the_frame_at_a_stamp_is_the_one_written_under_it(
    camera: RecordedCamera,
) -> None:
    for frame in FRAMES_TAKEN:
        assert frame_nearest(camera, frame.stamp) == frame.shade


def test_the_frame_between_two_stamps_is_the_nearer_one(camera: RecordedCamera) -> None:
    first, second, third = FRAMES_TAKEN
    assert frame_nearest(camera, first.stamp + A_SECOND // 2) == first.shade
    assert frame_nearest(camera, second.stamp - A_SECOND // 2) == second.shade
    assert frame_nearest(camera, third.stamp - A_SECOND) == third.shade


def test_a_moment_before_the_recording_began_shows_its_first_frame(
    camera: RecordedCamera,
) -> None:
    """
    A recording opened a little after the trial began has no frame for the trial's first
    moments, which are shown from where the recording starts rather than refused.
    """
    assert frame_nearest(camera, RECORDING_BEGAN_AT - A_SECOND) == FRAMES_TAKEN[0].shade


def test_a_moment_after_the_recording_ended_shows_its_last_frame(
    camera: RecordedCamera,
) -> None:
    assert (
        frame_nearest(camera, FRAMES_TAKEN[-1].stamp + A_SECOND)
        == FRAMES_TAKEN[-1].shade
    )


def test_a_recording_with_no_frame_to_show_says_so(tmp_path: Path) -> None:
    camera = RecordedCamera(
        bag=write_recording(tmp_path / "recording", []), reference_frame=REFERENCE_FRAME
    )

    with pytest.raises(NothingRecordedOnTopic) as raised:
        camera.image_nearest(RECORDING_BEGAN_AT)
    assert raised.value.topic == str(CameraTopic.COLOR)
