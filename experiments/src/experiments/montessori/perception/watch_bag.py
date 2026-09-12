"""
Run the perception pipeline over a recorded rosbag and watch what it finds.

Run it as::

    python -m experiments.montessori.perception.watch_bag rosbags/<bag>

This is :mod:`~experiments.montessori.perception.node` with the recording in place of
the camera and the robot: the same pipeline, the same windows, playing frames that were
already published once. It is what a change to the detectors is watched on when the
robot is not there.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import List, Optional

from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import perception_pipeline
from experiments.montessori.perception.recordings import (
    REFERENCE_FRAME,
    RecordedCamera,
)
from experiments.montessori.perception.scene_windows import SceneWindows
from experiments.montessori.perception.viewer import CameraFrameViewer

logger = logging.getLogger(__name__)


@dataclass
class BagReplay:
    """
    Plays a recording's frames through the pipeline, drawing every look it takes.
    """

    camera: RecordedCamera
    """
    The recording being played, and where its camera stood.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    Turns each frame into detections.
    """

    viewer: Optional[CameraFrameViewer] = None
    """
    Where the looks are drawn, or None to run without opening a window.
    """

    every_nth_frame: int = 1
    """
    How many of the recording's frames to run: one in this many.
    """

    scenes: List[MontessoriScene] = field(default_factory=list, init=False)
    """
    What each look found, in the order the looks were taken.
    """

    def play(self, limit: Optional[int] = None) -> None:
        """
        Read the recording through, detecting on every :attr:`every_nth_frame` frame.

        :param limit: Stop after this many looks, or None to play to the end.
        """
        windows = (
            None
            if self.viewer is None
            else SceneWindows(pipeline=self.pipeline, viewer=self.viewer)
        )
        intrinsics = self.camera.intrinsics
        reference_frame_T_camera = self.camera.reference_frame_T_camera
        for index, look in enumerate(self.camera.looks()):
            if index % self.every_nth_frame:
                continue
            frame = look.to_frame(intrinsics, reference_frame_T_camera)
            scene = self.pipeline.detect(frame)
            self.scenes.append(scene)
            logger.info(
                "frame %d: %d pieces, %d holes",
                index,
                len(scene.shapes),
                len(scene.holes),
            )
            if windows is not None:
                windows.show(frame, scene)
                self.viewer.refresh()
            if limit is not None and len(self.scenes) >= limit:
                return


def main() -> None:
    """
    Replay the recording named on the command line.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path, help="directory of the recording to replay")
    parser.add_argument(
        "--camera-from",
        type=Path,
        default=None,
        help=(
            "recording to read the camera's pose from, for a recording that carries "
            "no transform tree of its own"
        ),
    )
    parser.add_argument(
        "--every-nth-frame",
        type=int,
        default=1,
        help="run the pipeline on one frame in this many",
    )
    parser.add_argument(
        "--without-windows",
        action="store_true",
        help="detect without drawing anything, for a run with no screen",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    viewer = None if arguments.without_windows else CameraFrameViewer()
    replay = BagReplay(
        camera=RecordedCamera(
            bag=arguments.bag,
            reference_frame=REFERENCE_FRAME,
            camera_bag=arguments.camera_from,
        ),
        pipeline=perception_pipeline(),
        viewer=viewer,
        every_nth_frame=arguments.every_nth_frame,
    )
    try:
        replay.play()
    finally:
        if viewer is not None:
            viewer.close()


if __name__ == "__main__":
    main()
