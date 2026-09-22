"""
Showing one look at the scene: the camera's own image, its depth, and the top-down view.

Whatever the frames come from -- the live camera or a recording played back -- a look is
drawn the same way, so what is watched during a run and what is watched afterwards are
the same picture.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.overlay import (
    CameraView,
    DetectionOverlay,
    RectifiedView,
    ViewFromAbove,
)
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.viewer import CameraFrameViewer


@dataclass
class SceneWindows:
    """
    The windows one look at the scene is drawn in.

    The camera's own image is cut down to the workspace first, so the window shows the
    stretch of table being worked on rather than the whole room it stands in.
    """

    pipeline: MontessoriPerceptionPipeline
    """
    The pipeline the detections came from, which knows the workspace and the plane the
    outlines were measured in.
    """

    viewer: CameraFrameViewer
    """
    Where the images are shown.
    """

    overlay: DetectionOverlay = field(default_factory=DetectionOverlay)
    """
    Draws the detections onto the images.
    """

    def show(self, frame: RgbdFrame, scene: MontessoriScene) -> None:
        """
        Draw one look at the scene.

        :param frame: The frame the detections were found in.
        :param scene: The detections to draw.
        """
        table = self.pipeline.table_in(frame)
        workspace = self.pipeline.workspace_over(table)
        self.viewer.show_color(
            workspace.clip(self.overlay.draw(CameraView(frame), scene), frame)
        )
        self.viewer.show_depth(workspace.clip(frame.depth, frame))
        self.viewer.show_rectified(
            self.overlay.draw(
                ViewFromAbove(
                    RectifiedView(frame, self.pipeline.rectify(frame, table))
                ),
                scene,
            )
        )
