"""
Run the perception pipeline over the captures kept in the repository and watch what it
finds.

Run it as::

    python -m experiments.montessori.perception.watch_captures

Each capture is detected on and drawn in the same windows a live run uses, and stays on
screen until a key is pressed, so what the detectors make of the real table can be
looked at one scene at a time. Press ``q`` or escape to stop.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from typing_extensions import Dict, List, Optional

from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import perception_pipeline
from experiments.montessori.perception.scene_windows import SceneWindows
from experiments.montessori.perception.viewer import CameraFrameViewer, QuitKey

logger = logging.getLogger(__name__)


def pieces_found(scene: MontessoriScene) -> str:
    """
    What a look at the scene made of the loose pieces, surface by surface.

    Which surface a piece was put on is worth reading beside the piece itself: the same
    piece reported on two surfaces at once is one thing seen twice.

    :param scene: The result of one look.
    :return: The pieces found on each surface, in words.
    """
    by_surface: Dict[str, List[str]] = defaultdict(list)
    for shape in scene.shapes:
        by_surface[shape.supporting_surface.name].append(shape.label)
    if not by_surface:
        return "no pieces"
    return "; ".join(
        f"{surface}: {', '.join(labels)}" for surface, labels in by_surface.items()
    )


@dataclass
class CaptureReview:
    """
    Detects on one capture after another, drawing every look it takes.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    Turns each capture into detections.
    """

    viewer: Optional[CameraFrameViewer] = None
    """
    Where the looks are drawn, or None to run without opening a window.
    """

    directory: Path = CAPTURE_DIRECTORY
    """
    Where the captures to review lie.
    """

    seconds_per_capture: Optional[float] = None
    """
    How long each capture stays on screen before the next one is drawn, or None to hold
    it until a key is pressed.
    """

    scenes: Dict[str, MontessoriScene] = field(default_factory=dict, init=False)
    """
    What was found in each capture, by the capture's own name.
    """

    def review(self, names: Optional[List[str]] = None) -> None:
        """
        Detect on each capture in turn and show what came out.

        :param names: The captures to review, or None for every one in
            :attr:`directory`.
        :raises CaptureIncomplete: If a named capture is missing one of its files.
        """
        windows = (
            None
            if self.viewer is None
            else SceneWindows(pipeline=self.pipeline, viewer=self.viewer)
        )
        for name in (
            names if names is not None else SceneCapture.names_in(self.directory)
        ):
            capture = SceneCapture.load(name, self.directory)
            frame = capture.to_frame()
            scene = self.pipeline.detect(frame)
            self.scenes[name] = scene
            logger.info(
                "%s: %s; %d holes; board %s",
                name,
                pieces_found(scene),
                len(scene.holes),
                "found" if scene.board is not None else "not found",
            )
            if windows is None:
                continue
            windows.show(frame, scene)
            pressed = self.viewer.hold(self.seconds_per_capture)
            if pressed is not None and pressed in QuitKey:
                return


def main() -> None:
    """
    Review the captures named on the command line, or all of them.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "captures",
        nargs="*",
        help="names of the captures to review, or none for every one of them",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=CAPTURE_DIRECTORY,
        help="where the captures lie",
    )
    parser.add_argument(
        "--seconds-per-capture",
        type=float,
        default=None,
        help=(
            "move on to the next capture after this long, instead of waiting for a key"
        ),
    )
    parser.add_argument(
        "--without-windows",
        action="store_true",
        help="detect without drawing anything, for a run with no screen",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    viewer = None if arguments.without_windows else CameraFrameViewer()
    review = CaptureReview(
        pipeline=perception_pipeline(),
        viewer=viewer,
        directory=arguments.directory,
        seconds_per_capture=arguments.seconds_per_capture,
    )
    try:
        review.review(arguments.captures or None)
    finally:
        if viewer is not None:
            viewer.close()


if __name__ == "__main__":
    main()
