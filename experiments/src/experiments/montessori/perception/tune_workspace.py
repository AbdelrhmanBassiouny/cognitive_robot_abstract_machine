"""
Cut the workspace down to the table by eye, with a slider for each of its edges.

Run it as::

    python -m experiments.montessori.perception.tune_workspace

The windows show exactly what a run shows -- the camera image clipped to the workspace,
its depth, and the table rectified -- while four sliders move the workspace's edges. Drag
them until only the table is left, then press ``q`` or escape: the region you settled on
is printed and written to a file, to be put back into the setup it was tuned for.

The sliders can only cut the declared region down, never grow it past what the setup
already searches, so a workspace tuned here is always one the camera saw.
"""

from __future__ import annotations

import argparse
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path

import cv2
from typing_extensions import Dict

from experiments.montessori.perception.camera import MILLIMETRES_PER_METRE, RgbdFrame
from experiments.montessori.perception.captures import CAPTURE_DIRECTORY, SceneCapture
from experiments.montessori.perception.orthophoto import WorkspaceRegion
from experiments.montessori.perception.overlay import RectifiedView, ViewFromAbove
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import perception_pipeline
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
    One OpenCV slider per edge, each measured in millimetres from the declared region's
    own corner, so an edge can be brought in but never pushed out.
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

    def _metres_from_corner(self, edge: WorkspaceEdge) -> float:
        """
        How far one edge's slider stands from the declared region's corner, in metres.

        :param edge: The edge to read.
        """
        return cv2.getTrackbarPos(edge.value, self.window_name) / MILLIMETRES_PER_METRE

    def read(self) -> WorkspaceRegion:
        return replace(
            self.bounds,
            minimum_x=self.bounds.minimum_x
            + self._metres_from_corner(WorkspaceEdge.MINIMUM_X),
            maximum_x=self.bounds.minimum_x
            + self._metres_from_corner(WorkspaceEdge.MAXIMUM_X),
            minimum_y=self.bounds.minimum_y
            + self._metres_from_corner(WorkspaceEdge.MINIMUM_Y),
            maximum_y=self.bounds.minimum_y
            + self._metres_from_corner(WorkspaceEdge.MAXIMUM_Y),
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
                    self.frame, searching.rectify(self.frame, searching.table.height)
                )
            ).to_image()
        )

    def tune(self) -> WorkspaceRegion:
        """
        Draw the workspace until the windows are quit, reporting each edge that moves.

        The edges are reported as they are moved because a slider says where it stands
        far less precisely than a number does, and the number is what the setup is
        written back with.

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
        default=Path("tuned_workspace.json"),
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
        controls=TrackbarControls(bounds=pipeline.table.region),
        viewer=viewer,
    )
    try:
        region = tuner.tune()
    finally:
        viewer.close()
    arguments.save_to.write_text(json.dumps(asdict(region), indent=2) + "\n")
    logger.info("tuned on %s to %s, written to %s", name, region, arguments.save_to)


if __name__ == "__main__":
    main()
