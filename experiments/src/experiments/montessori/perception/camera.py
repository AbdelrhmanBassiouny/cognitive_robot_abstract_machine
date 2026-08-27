"""
The camera data a detection runs on: one registered colour/depth pair, its pinhole
intrinsics, and where the camera stood when it was taken.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from typing_extensions import Self

from experiments.montessori.perception.exceptions import (
    DepthAndColourNotRegistered,
    UnsupportedImageEncoding,
)

# %% encodings


class ImageEncoding(StrEnum):
    """
    The ``sensor_msgs/Image`` encodings this package reads.
    """

    RGB8 = "rgb8"
    BGR8 = "bgr8"
    DEPTH_IN_MILLIMETRES = "16UC1"
    DEPTH_IN_METRES = "32FC1"


MILLIMETRES_PER_METRE = 1000.0
"""
Divisor turning a :attr:`ImageEncoding.DEPTH_IN_MILLIMETRES` reading into metres.
"""


# %% intrinsics


@dataclass(frozen=True)
class CameraIntrinsics:
    """
    A pinhole camera's focal lengths and principal point, in pixels.
    """

    focal_length_x: float
    """
    Focal length along the image's x-axis.
    """

    focal_length_y: float
    """
    Focal length along the image's y-axis.
    """

    principal_point_x: float
    """
    X-coordinate of the point where the optical axis meets the image.
    """

    principal_point_y: float
    """
    Y-coordinate of the point where the optical axis meets the image.
    """

    @classmethod
    def from_camera_info_matrix(cls, camera_info_matrix: np.ndarray) -> Self:
        """
        Read the intrinsics out of a ``sensor_msgs/CameraInfo``'s own ``k``.

        :param camera_info_matrix: The 3x3 intrinsic matrix, in any shape that reshapes
            to ``(3, 3)``.
        """
        matrix = np.asarray(camera_info_matrix, dtype=float).reshape(3, 3)
        return cls(
            focal_length_x=float(matrix[0, 0]),
            focal_length_y=float(matrix[1, 1]),
            principal_point_x=float(matrix[0, 2]),
            principal_point_y=float(matrix[1, 2]),
        )

    def to_matrix(self) -> np.ndarray:
        """
        :return: These intrinsics as a 3x3 projection matrix.
        """
        return np.array(
            [
                [self.focal_length_x, 0.0, self.principal_point_x],
                [0.0, self.focal_length_y, self.principal_point_y],
                [0.0, 0.0, 1.0],
            ]
        )

    def deproject(self, pixels: np.ndarray, depths: np.ndarray) -> np.ndarray:
        """
        Turn pixels with known depth into points in the camera's optical frame, where x
        points right, y down, and z along the optical axis.

        :param pixels: Pixel coordinates as ``(n, 2)`` ``(x, y)`` pairs.
        :param depths: Depth of each pixel in metres, shape ``(n,)``.
        :return: The points, shape ``(n, 3)``.
        """
        pixels = np.asarray(pixels, dtype=float).reshape(-1, 2)
        depths = np.asarray(depths, dtype=float).reshape(-1)
        return np.stack(
            [
                (pixels[:, 0] - self.principal_point_x) * depths / self.focal_length_x,
                (pixels[:, 1] - self.principal_point_y) * depths / self.focal_length_y,
                depths,
            ],
            axis=1,
        )


# %% frames


@dataclass(frozen=True)
class RgbdFrame:
    """
    One colour image with the depth image registered onto it, plus the camera's pose in
    the frame detections are reported in.

    Registered means the two images share a resolution and a set of intrinsics, so pixel
    ``(x, y)`` names the same ray in both.
    """

    color: np.ndarray
    """
    The colour image in OpenCV's channel order, shape ``(height, width, 3)`` of
    ``uint8`` blue/green/red.
    """

    depth: np.ndarray
    """
    Depth in metres, shape ``(height, width)``; zero marks a pixel the sensor returned
    no reading for.
    """

    intrinsics: CameraIntrinsics
    """
    The intrinsics both images were taken with.
    """

    reference_frame_T_camera: np.ndarray
    """
    The camera's optical frame expressed in the frame detections are reported in, as a
    4x4 homogeneous transformation.
    """

    def __post_init__(self) -> None:
        if self.color.shape[:2] != self.depth.shape[:2]:
            raise DepthAndColourNotRegistered(
                self.color.shape[:2], self.depth.shape[:2]
            )

    @property
    def height(self) -> int:
        """
        Number of image rows.
        """
        return int(self.color.shape[0])

    @property
    def width(self) -> int:
        """
        Number of image columns.
        """
        return int(self.color.shape[1])

    def depth_at(self, pixels: np.ndarray) -> np.ndarray:
        """
        Read the depth of a set of pixels, dropping the ones the sensor gave no reading
        for.

        :param pixels: Pixel coordinates as ``(n, 2)`` ``(x, y)`` pairs.
        :return: The depths in metres that were actually measured, shape ``(m,)`` with
            ``m <= n``.
        """
        pixels = np.asarray(pixels, dtype=int).reshape(-1, 2)
        inside = (
            (pixels[:, 0] >= 0)
            & (pixels[:, 0] < self.width)
            & (pixels[:, 1] >= 0)
            & (pixels[:, 1] < self.height)
        )
        pixels = pixels[inside]
        depths = self.depth[pixels[:, 1], pixels[:, 0]]
        return depths[depths > 0.0]


def decode_color_image(
    data: bytes, height: int, width: int, step: int, encoding: str
) -> np.ndarray:
    """
    Read a ``sensor_msgs/Image``'s bytes into an OpenCV-ordered colour image.

    :param data: The message's raw bytes.
    :param height: Number of rows.
    :param width: Number of columns.
    :param step: Row stride in bytes, which may exceed ``width * 3``.
    :param encoding: The message's own encoding.
    :return: The image, shape ``(height, width, 3)`` of ``uint8`` blue/green/red.
    :raises UnsupportedImageEncoding: If the encoding is neither ``rgb8`` nor ``bgr8``.
    """
    if encoding not in (ImageEncoding.RGB8, ImageEncoding.BGR8):
        raise UnsupportedImageEncoding(
            encoding, [ImageEncoding.RGB8, ImageEncoding.BGR8]
        )
    rows = np.frombuffer(data, dtype=np.uint8).reshape(height, step)
    image = rows[:, : width * 3].reshape(height, width, 3)
    if encoding == ImageEncoding.RGB8:
        return image[:, :, ::-1].copy()
    return image.copy()


def decode_depth_image(
    data: bytes, height: int, width: int, step: int, encoding: str
) -> np.ndarray:
    """
    Read a ``sensor_msgs/Image``'s bytes into a depth image in metres.

    :param data: The message's raw bytes.
    :param height: Number of rows.
    :param width: Number of columns.
    :param step: Row stride in bytes.
    :param encoding: The message's own encoding.
    :return: Depth in metres, shape ``(height, width)``, zero where unmeasured.
    :raises UnsupportedImageEncoding: If the encoding is neither ``16UC1`` nor ``32FC1``.
    """
    if encoding == ImageEncoding.DEPTH_IN_MILLIMETRES:
        rows = np.frombuffer(data, dtype=np.uint16).reshape(height, step // 2)
        return rows[:, :width].astype(np.float32) / MILLIMETRES_PER_METRE
    if encoding == ImageEncoding.DEPTH_IN_METRES:
        rows = np.frombuffer(data, dtype=np.float32).reshape(height, step // 4)
        return np.nan_to_num(rows[:, :width].astype(np.float32))
    raise UnsupportedImageEncoding(
        encoding,
        [ImageEncoding.DEPTH_IN_MILLIMETRES, ImageEncoding.DEPTH_IN_METRES],
    )
