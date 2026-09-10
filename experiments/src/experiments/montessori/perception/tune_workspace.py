"""
Cut the workspace down to the table by eye, with a slider for each of its edges.

Run it as::

    python -m experiments.montessori.perception.tune_workspace

The windows show exactly what a run shows -- the camera image clipped to the workspace,
its depth, and the table rectified -- while four sliders move the workspace's edges. Drag
them until only the table is left, then press ``q`` or escape: the region you settled on
is printed and written down as the workspace the setup searches, so the next run over
these captures looks at exactly what was left on screen.

The sliders can only cut the whole workspace down, never grow it past what the camera
looks over, so a workspace tuned here is always one the camera saw. They open from that
whole workspace rather than from a previous tuning, so an edge brought in too far can be
pushed back out.
"""

from __future__ import annotations

import argparse
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

import cv2
from typing_extensions import Dict

from experiments.montessori.perception.camera import MILLIMETRES_PER_METRE, RgbdFrame
from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.overlay import RectifiedView, ViewFromAbove
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    TUNED_WORKSPACE_FILE,
    WIDEST_WORKSPACE,
    perception_pipeline,
)
from experiments.montessori.perception.viewer import CameraFrameViewer, QuitKey

logger = logging.getLogger(__name__)

# %% moving the workspace's edges


class WorkspaceEdge(StrEnum):
    """
    The four edges of the workspace, labelled as their sliders are.
    """

    MINIMUM_X = "x from (mm)"
    MAXIMUM_X = "x to (mm)"
    MINIMUM_Y = "y from (mm)"
    MAXIMUM_Y = "y to (mm)"


class WorkspaceControls(ABC):
    """
    Somewhere the workspace's edges can be moved.
    """

    @abstractmethod
    def read(self) -> WorkspaceRegion:
        """
        :return: The region the edges stand at now.
        """


@dataclass
class TrackbarControls(WorkspaceControls):
    """
    One OpenCV slider per edge, each measured in millimetres from the corner of the
    whole workspace, so an edge can be brought in but never pushed out.
    """

    bounds: WorkspaceRegion
    """
    The region the sliders move inside, which is the one being cut down.
    """

    window_name: str = "montessori perception: workspace"
    """
    The window the sliders sit on.
    """

    def __post_init__(self) -> None:
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        for edge, span in self._spans().items():
            cv2.createTrackbar(edge.value, self.window_name, 0, span, lambda _: None)
        for edge in (WorkspaceEdge.MAXIMUM_X, WorkspaceEdge.MAXIMUM_Y):
            cv2.setTrackbarPos(edge.value, self.window_name, self._spans()[edge])

    def _spans(self) -> Dict[WorkspaceEdge, int]:
        """
        How far each edge's slider may travel, in millimetres.
        """
        across = round(
            (self.bounds.maximum_x - self.bounds.minimum_x) * MILLIMETRES_PER_METRE
        )
        along = round(
            (self.bounds.maximum_y - self.bounds.minimum_y) * MILLIMETRES_PER_METRE
        )
        return {
            WorkspaceEdge.MINIMUM_X: across,
            WorkspaceEdge.MAXIMUM_X: across,
            WorkspaceEdge.MINIMUM_Y: along,
            WorkspaceEdge.MAXIMUM_Y: along,
        }

    def _position_of(self, edge: WorkspaceEdge, corner: float) -> float:
        """
        Where one edge stands, in metres.

        The whole sum is taken in the millimetres the slider is graduated in, so an edge
        is written down as the round number it was dragged to rather than as that number
        plus the remainder of adding two metric floats.

        :param edge: The edge to read.
        :param corner: The corner of the whole workspace its slider is measured from, in
            metres.
        """
        travelled = cv2.getTrackbarPos(edge.value, self.window_name)
        return (round(corner * MILLIMETRES_PER_METRE) + travelled) / (
            MILLIMETRES_PER_METRE
        )

    def read(self) -> WorkspaceRegion:
        return replace(
            self.bounds,
            minimum_x=self._position_of(WorkspaceEdge.MINIMUM_X, self.bounds.minimum_x),
            maximum_x=self._position_of(WorkspaceEdge.MAXIMUM_X, self.bounds.minimum_x),
            minimum_y=self._position_of(WorkspaceEdge.MINIMUM_Y, self.bounds.minimum_y),
            maximum_y=self._position_of(WorkspaceEdge.MAXIMUM_Y, self.bounds.minimum_y),
        )


# %% watching the workspace while it is cut down


@dataclass
class WorkspaceTuner:
    """
    Draws the workspace one frame is searched through, as its edges are moved.

    Nothing is detected while tuning: the question being answered is which stretch of
    table is worth looking at, which the clipped image and the rectified table answer on
    their own.
    """

    frame: RgbdFrame
    """
    The look at the scene the workspace is judged against.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    The pipeline whose workspace is being cut down, and which says how the clipping and
    the rectification are done.
    """

    controls: WorkspaceControls
    """
    Where the edges are moved.
    """

    viewer: CameraFrameViewer
    """
    Where the workspace is drawn.
    """

    def show(self, region: WorkspaceRegion) -> None:
        """
        Draw what one region cuts out of the frame.

        A region with no area is passed over rather than drawn, which is what an edge
        dragged past its opposite makes.

        :param region: The region to draw.
        """
        if region.width_in_pixels < 1 or region.height_in_pixels < 1:
            return
        searching = replace(
            self.pipeline, table=replace(self.pipeline.table, region=region)
        )
        workspace = searching.workspace
        self.viewer.show_color(workspace.clip(self.frame.color, self.frame))
        self.viewer.show_depth(workspace.clip(self.frame.depth, self.frame))
        self.viewer.show_rectified(
            ViewFromAbove(
                RectifiedView(
                    self.frame, searching.rectify(self.frame, searching.table)
                )
            ).to_image()
        )

    def tune(self) -> WorkspaceRegion:
        """
        Draw the workspace until the windows are quit, reporting each edge that moves.

        The edges are reported as they are moved because a slider says where it stands
        far less precisely than a number does, and the number is what is written back.

        :return: The region the edges were left at.
        """
        reported = None
        while True:
            region = self.controls.read()
            if region != reported:
                logger.info("%s", region)
                reported = region
            self.show(region)
            pressed = self.viewer.refresh()
            if pressed is not None and pressed in QuitKey:
                return region


# %% running it


def main() -> None:
    """
    Tune the workspace against one capture and write down where it was left.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capture",
        nargs="?",
        default=None,
        help="the capture to tune against, or none for the first one",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=CAPTURE_DIRECTORY,
        help="where the captures lie",
    )
    parser.add_argument(
        "--save-to",
        type=Path,
        default=TUNED_WORKSPACE_FILE,
        help="where to write the region the edges were left at",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    name = arguments.capture or SceneCapture.names_in(arguments.directory)[0]
    pipeline = perception_pipeline()
    viewer = CameraFrameViewer()
    tuner = WorkspaceTuner(
        frame=SceneCapture.load(name, arguments.directory).to_frame(),
        pipeline=pipeline,
        controls=TrackbarControls(bounds=WIDEST_WORKSPACE),
        viewer=viewer,
    )
    try:
        region = tuner.tune()
    finally:
        viewer.close()
    region.save(arguments.save_to)
    logger.info("tuned on %s to %s, written to %s", name, region, arguments.save_to)


if __name__ == "__main__":
    main()
