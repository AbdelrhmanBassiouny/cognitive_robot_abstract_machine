"""
Take one look at the scene off the live camera and write it as a capture.

Run it against the live robot with (the camera and the robot drivers must already be up
via ``ros2 launch iai_tracy_bringup tracy_ros2.launch.py``)::

    python -m experiments.montessori.perception.capture_from_camera <name>

The capture is the same three files
:mod:`~experiments.montessori.perception.capture_from_bag` cuts out of a recording, so a
scene set up on the table can be added to the shipped captures without recording and
keeping a rosbag of it.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node

from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.exceptions import NoSceneAvailable
from experiments.montessori.perception.live_camera import LiveCamera
from experiments.montessori.perception.measured_plane import CameraPoseError
from experiments.montessori.perception.recorded_setup import table_surface
from experiments.montessori.perception.recordings import REFERENCE_FRAME

NODE_NAME = "montessori_capture"
"""
Name the node taking the capture registers under.
"""

SPIN_SECONDS = 0.05
"""
How long each turn of the loop waits for a message.
"""

TAKE_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
"""
How the moment a capture was taken is written into what it records itself as taken from,
the way the recordings' own directories are named.
"""

LIVE_CAMERA_TAKE = "live_camera"
"""
What a capture taken off the live camera, rather than cut out of a recording, records
itself as taken from, ahead of the moment it was taken at.
"""


def take_name(taken_at: datetime) -> str:
    """
    :param taken_at: When the look was taken.
    :return: What a capture taken off the live camera at that moment records itself as
        taken from.
    """
    return f"{LIVE_CAMERA_TAKE}_{taken_at.strftime(TAKE_TIMESTAMP_FORMAT)}"


def write_capture(
    node: Node,
    name: str,
    reference_frame: str = REFERENCE_FRAME,
    timeout_seconds: float = 20.0,
    directory: Path = CAPTURE_DIRECTORY,
) -> SceneCapture:
    """
    Wait for the camera's streams and the transform tree, then write one look as a
    capture.

    :param node: The node to subscribe on.
    :param name: What to call this look at the scene.
    :param reference_frame: Frame to express the camera's pose in.
    :param timeout_seconds: How long to wait for everything to arrive.
    :param directory: Where to write the capture's three files.
    :return: The capture that was written.
    :raises NoSceneAvailable: If a stream or the camera's pose never arrived.
    """
    camera = LiveCamera(node=node)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=SPIN_SECONDS)
        if camera.missing_inputs():
            continue
        reference_frame_T_camera = camera.pose_in(reference_frame)
        if reference_frame_T_camera is None:
            continue
        capture = SceneCapture(
            name=name,
            recorded_from=take_name(datetime.now()),
            color_format=camera.color.format,
            intrinsics=camera.intrinsics,
            reference_frame=reference_frame,
            reference_frame_T_camera=reference_frame_T_camera,
            directory=directory,
        )
        capture.save(bytes(camera.color.data), camera.depth_image)
        return capture
    raise NoSceneAvailable(timeout_seconds, camera.missing_inputs())


def main() -> None:
    """
    Write one capture off the live camera under the name given on the command line.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="what to call the capture")
    parser.add_argument(
        "--reference-frame",
        default=REFERENCE_FRAME,
        help="frame to express the camera's pose, and so the detections, in",
    )
    parser.add_argument(
        "--into",
        type=Path,
        default=CAPTURE_DIRECTORY,
        help="directory to write the capture's three files into",
    )
    arguments = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node(NODE_NAME)
    capture = write_capture(
        node=node,
        name=arguments.name,
        reference_frame=arguments.reference_frame,
        directory=arguments.into,
    )
    print(f"wrote {capture.name} to {capture.directory}")
    print(
        f"published camera pose: {CameraPoseError.of(capture.to_frame(), table_surface())}"
    )


if __name__ == "__main__":
    main()
