"""
Render a Montessori scene of known geometry into a camera image, so perception can be
tested against ground truth it was never told.

The camera looks at the table from off to one side, the way the real one does, so a
piece standing on the table shows its sides as well as its top and its silhouette comes
out stretched -- the very effect
:meth:`~experiments.montessori.perception.pipeline.LoosePieceDetector.detect` has to
cancel.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from typing_extensions import List, Sequence, Tuple

from experiments.montessori.hole_geometry import HoleFootprint, detect_hole_footprints
from experiments.montessori.perception.camera import CameraIntrinsics, RgbdFrame
from experiments.montessori.semantics import MontessoriShapeCategory
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)

# %% how the scene looks

TABLE_COLOR = (30, 13, 156)
"""
Hue, saturation and value of the bare metal table, measured off the real one.
"""

LID_COLOR = (19, 53, 204)
"""
Hue, saturation and value of the board's wooden lid, measured off the real one.
"""

HOLE_COLOR = (17, 149, 79)
"""
Hue, saturation and value seen through a hole in the lid, measured off the real board.
"""

PIECE_COLOR = (22, 115, 220)
"""
Hue, saturation and value of a loose piece, measured off the real ones.
"""


# %% what is in the scene


@dataclass(frozen=True)
class PlacedPiece:
    """
    One loose piece standing on the table, at a position the test chose.
    """

    category: MontessoriShapeCategory
    """
    Which shape it is.
    """

    x: float
    """
    Where its centre stands along the world frame's x-axis, in metres.
    """

    y: float
    """
    Where its centre stands along the world frame's y-axis, in metres.
    """

    height: float = 0.03
    """
    How tall it stands, in metres.
    """


@dataclass
class MontessoriSceneRenderer:
    """
    Draws a Montessori scene of known geometry as the camera would see it.
    """

    table_height: float = 0.88
    """
    Height of the table's top surface above the world frame's origin, in metres.
    """

    board_height: float = 0.08
    """
    How far the board's lid stands above the table, in metres.
    """

    board_x: float = 0.83
    """
    Where the board's centre stands along the world frame's x-axis, in metres.
    """

    board_y: float = 0.12
    """
    Where the board's centre stands along the world frame's y-axis, in metres.
    """

    image_width: int = 1920
    """
    Width of the rendered image, matching the real camera.
    """

    image_height: int = 1080
    """
    Height of the rendered image, matching the real camera.
    """

    intrinsics: CameraIntrinsics = field(
        default_factory=lambda: CameraIntrinsics(
            focal_length_x=1117.02,
            focal_length_y=1116.93,
            principal_point_x=950.57,
            principal_point_y=527.61,
        )
    )
    """
    The real camera's own intrinsics.
    """

    camera_pose: Tuple[float, ...] = (
        0.4089,
        -0.0473,
        1.8153,
        -0.7024,
        0.7053,
        -0.0710,
        0.0644,
    )
    """
    Where the real camera stands, as a position and a quaternion in the world frame.
    """

    @property
    def lid_height(self) -> float:
        """
        Height of the board's lid above the world frame's origin, in metres.
        """
        return self.table_height + self.board_height

    @property
    def world_T_camera(self) -> np.ndarray:
        """
        The camera's pose as a 4x4 homogeneous transformation.
        """
        return HomogeneousTransformationMatrix.from_xyz_quaternion(
            *self.camera_pose
        ).to_np()

    def hole_footprints(self) -> List[HoleFootprint]:
        """
        The holes cut into the board this renderer draws, read from the board's own
        mesh.
        """
        return detect_hole_footprints()

    def hole_center(self, footprint: HoleFootprint) -> Tuple[float, float]:
        """
        Where a hole's centre lies in the world frame.

        :param footprint: The hole, positioned relative to the board's own centre.
        """
        return (self.board_x + footprint.center[0], self.board_y + footprint.center[1])

    def render(self, pieces: Sequence[PlacedPiece]) -> RgbdFrame:
        """
        Draw the scene as the camera sees it.

        :param pieces: The loose pieces to place on the table.
        :return: The frame, with a depth image left empty since the real table is too
            reflective to return one.
        """
        canvas = np.zeros((self.image_height, self.image_width, 3), dtype=np.uint8)
        canvas[:, :] = TABLE_COLOR
        self._draw_board(canvas)
        for piece in pieces:
            self._draw_piece(canvas, piece)
        return RgbdFrame(
            color=cv2.cvtColor(canvas, cv2.COLOR_HSV2BGR),
            depth=np.zeros((self.image_height, self.image_width), dtype=np.float32),
            intrinsics=self.intrinsics,
            reference_frame_T_camera=self.world_T_camera,
        )

    def _draw_board(self, canvas: np.ndarray) -> None:
        """
        Draw the board's lid and the holes cut through it.

        :param canvas: The hue-saturation-value image to draw into.
        """
        footprints = self.hole_footprints()
        half_width = max(abs(point[0]) for point in self._lid_corners(footprints))
        half_length = max(abs(point[1]) for point in self._lid_corners(footprints))
        lid = [
            (self.board_x + sign_x * half_width, self.board_y + sign_y * half_length)
            for sign_x, sign_y in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
        self._fill(canvas, lid, self.lid_height, LID_COLOR)
        for footprint in footprints:
            center = self.hole_center(footprint)
            self._fill(
                canvas,
                [(center[0] + x, center[1] + y) for x, y in footprint.boundary],
                self.lid_height,
                HOLE_COLOR,
            )

    @staticmethod
    def _lid_corners(
        footprints: Sequence[HoleFootprint],
    ) -> List[Tuple[float, float]]:
        """
        Corners of a lid drawn just large enough to hold every hole with a margin.

        :param footprints: The holes the lid must hold.
        """
        margin = 0.02
        return [
            (
                footprint.center[0] + sign_x * (footprint.size[0] / 2 + margin),
                footprint.center[1] + sign_y * (footprint.size[1] / 2 + margin),
            )
            for footprint in footprints
            for sign_x, sign_y in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]

    def _draw_piece(self, canvas: np.ndarray, piece: PlacedPiece) -> None:
        """
        Draw one loose piece as the camera sees it: its base, its top, and the sides
        joining the two.

        :param canvas: The hue-saturation-value image to draw into.
        :param piece: The piece to draw.
        """
        boundary = self._piece_boundary(piece)
        base = self._project(boundary, self.table_height)
        top = self._project(boundary, self.table_height + piece.height)
        silhouette = cv2.convexHull(np.vstack([base, top]).astype(np.int32))
        cv2.fillPoly(canvas, [silhouette], PIECE_COLOR)

    def _piece_boundary(self, piece: PlacedPiece) -> List[Tuple[float, float]]:
        """
        A piece's own outline in the world frame, taken from the board hole it is made
        to fit through.

        :param piece: The piece to outline.
        """
        footprint = next(
            candidate
            for candidate in self.hole_footprints()
            if candidate.category is piece.category
        )
        return [(piece.x + x, piece.y + y) for x, y in footprint.boundary]

    def _fill(
        self,
        canvas: np.ndarray,
        boundary: Sequence[Tuple[float, float]],
        height: float,
        color: Tuple[int, int, int],
    ) -> None:
        """
        Fill a flat polygon lying at a given height.

        :param canvas: The hue-saturation-value image to draw into.
        :param boundary: The polygon's world-frame ``(x, y)`` corners.
        :param height: Height of the plane it lies on, in metres.
        :param color: Hue, saturation and value to fill it with.
        """
        cv2.fillPoly(canvas, [self._project(boundary, height).astype(np.int32)], color)

    def _project(
        self, boundary: Sequence[Tuple[float, float]], height: float
    ) -> np.ndarray:
        """
        Project world-frame points on a horizontal plane into the camera image.

        :param boundary: The points' world-frame ``(x, y)``.
        :param height: Height of the plane they lie on, in metres.
        :return: The pixels they land on, shape ``(n, 2)``.
        """
        camera_T_world = np.linalg.inv(self.world_T_camera)
        world_points = np.array([[x, y, height, 1.0] for x, y in boundary], dtype=float)
        camera_points = (camera_T_world @ world_points.T)[:3]
        pixels = self.intrinsics.to_matrix() @ camera_points
        return (pixels[:2] / pixels[2]).T
