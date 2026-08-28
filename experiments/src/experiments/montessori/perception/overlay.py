"""
Draw what perception found onto the camera image it was found in, so a detection can be
checked against the pixels it came from without leaving the camera window.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.colors import (
    BOARD_COLOR,
    HOLE_COLOR,
    LABEL_COLOR,
    PIECE_COLOR,
    DetectionColor,
)
from experiments.montessori.perception.detections import (
    MontessoriDetection,
    MontessoriScene,
)
from experiments.montessori.perception.orthophoto import OrthophotoProjector

# %% where a detection falls in the image


def project_to_pixels(
    frame: RgbdFrame, points: np.ndarray, height: float
) -> np.ndarray:
    """
    Where points on a horizontal plane fall in the image that saw them.

    :param frame: The camera data, carrying the camera's own pose and intrinsics.
    :param points: The points as ``(n, 2)`` world-frame ``(x, y)`` pairs.
    :param height: Height of the plane they lie on, in metres.
    :return: The pixels they fall on, as ``(n, 2)`` ``(x, y)`` pairs.
    """
    on_plane = np.column_stack(
        [np.asarray(points, dtype=float).reshape(-1, 2), np.ones(len(points))]
    )
    projected = on_plane @ OrthophotoProjector.pixel_T_region(frame, height).T
    return projected[:, :2] / projected[:, 2:3]


# %% drawing them


@dataclass
class DetectionOverlay:
    """
    Draws each detection's outline box, its centre and its name onto a frame.

    The box is the smallest upright rectangle holding the detection's own measured
    outline, projected back into the image, so a detection that is the wrong shape or in
    the wrong place is visibly so against the thing it claims to be.
    """

    line_width: int = 2
    """
    Thickness of a drawn box, in pixels.
    """

    center_radius: int = 4
    """
    Radius of the dot marking a detection's centre, in pixels.
    """

    label_height: float = 0.6
    """
    Size the name is written at, as OpenCV's own multiple of its base font.
    """

    label_offset: int = 6
    """
    How far above its box a name is written, in pixels.
    """

    def draw(self, frame: RgbdFrame, scene: MontessoriScene) -> np.ndarray:
        """
        Draw everything one look at the scene found.

        :param frame: The frame the detections were found in.
        :param scene: The detections to draw.
        :return: A copy of the frame's colour image with the detections on it.
        """
        image = frame.color.copy()
        for piece in scene.shapes:
            self._draw_detection(image, frame, piece, PIECE_COLOR)
        for hole in scene.holes:
            self._draw_detection(image, frame, hole, HOLE_COLOR)
        if scene.board is not None:
            self._draw_detection(image, frame, scene.board, BOARD_COLOR)
        return image

    def _draw_detection(
        self,
        image: np.ndarray,
        frame: RgbdFrame,
        detection: MontessoriDetection,
        color: DetectionColor,
    ) -> None:
        """
        Draw one detection's box, centre and name.

        :param image: The image to draw on, changed in place.
        :param frame: The frame the detection was found in.
        :param detection: The detection to draw.
        :param color: The colour to draw it in.
        """
        outline = project_to_pixels(frame, detection.outline, detection.surface_height)
        left, top, width, height = cv2.boundingRect(
            outline.astype(np.float32).reshape(-1, 1, 2)
        )
        cv2.rectangle(
            image,
            (left, top),
            (left + width, top + height),
            color.to_bgr(),
            self.line_width,
        )
        [center] = project_to_pixels(
            frame,
            detection.pose.to_position().to_np()[:2].reshape(1, 2),
            detection.surface_height,
        )
        cv2.circle(
            image,
            (round(center[0]), round(center[1])),
            self.center_radius,
            color.to_bgr(),
            cv2.FILLED,
        )
        cv2.putText(
            image,
            detection.label,
            (left, top - self.label_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            self.label_height,
            LABEL_COLOR.to_bgr(),
            self.line_width,
            cv2.LINE_AA,
        )
