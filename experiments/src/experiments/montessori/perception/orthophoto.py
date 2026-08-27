"""
Rectify the colour image onto a horizontal plane, giving a metric top-down view of that
plane.

Everything the board and the shapes need to be told apart is a flat footprint lying on a
known horizontal surface -- the table for the loose shapes, the board's lid for its
holes. Warping the camera view onto that surface removes the perspective the camera adds,
so a contour's area, side lengths, and orientation are read straight off in metres and in
the world frame, and the thresholds that classify it are real dimensions rather than
numbers tied to where the camera happened to stand.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from typing_extensions import Tuple

from experiments.montessori.perception.camera import RgbdFrame
from semantic_digital_twin.spatial_types.math import inverse_frame

# %% the region being looked at


@dataclass(frozen=True)
class WorkspaceRegion:
    """
    The axis-aligned patch of a horizontal plane that perception looks at, and how
    finely it is sampled.
    """

    minimum_x: float
    """
    Lower bound of the patch along the world frame's x-axis, in metres.
    """

    maximum_x: float
    """
    Upper bound of the patch along the world frame's x-axis, in metres.
    """

    minimum_y: float
    """
    Lower bound of the patch along the world frame's y-axis, in metres.
    """

    maximum_y: float
    """
    Upper bound of the patch along the world frame's y-axis, in metres.
    """

    resolution: float = 0.001
    """
    Edge length of one rectified pixel, in metres.

    One millimetre resolves the smallest hole on the board (a five millimetre wide slot)
    across several pixels while keeping the rectified image small enough to process at
    camera rate.
    """

    @property
    def width_in_pixels(self) -> int:
        """
        Width of the rectified image.
        """
        return int(round((self.maximum_x - self.minimum_x) / self.resolution))

    @property
    def height_in_pixels(self) -> int:
        """
        Height of the rectified image.
        """
        return int(round((self.maximum_y - self.minimum_y) / self.resolution))

    @property
    def region_T_pixel(self) -> np.ndarray:
        """
        The 3x3 mapping from a rectified pixel to the plane coordinates ``(x, y, 1)`` it
        samples.
        """
        return np.array(
            [
                [self.resolution, 0.0, self.minimum_x],
                [0.0, self.resolution, self.minimum_y],
                [0.0, 0.0, 1.0],
            ]
        )

    def to_world_position(self, pixel_x: float, pixel_y: float) -> Tuple[float, float]:
        """
        The world-frame ``(x, y)`` a rectified pixel samples.

        :param pixel_x: Column in the rectified image, which may be fractional.
        :param pixel_y: Row in the rectified image, which may be fractional.
        """
        return (
            self.minimum_x + pixel_x * self.resolution,
            self.minimum_y + pixel_y * self.resolution,
        )

    def contains(self, x: float, y: float) -> bool:
        """
        Whether a world-frame position falls inside this patch.

        :param x: Position along the world frame's x-axis, in metres.
        :param y: Position along the world frame's y-axis, in metres.
        """
        return (
            self.minimum_x <= x <= self.maximum_x
            and self.minimum_y <= y <= self.maximum_y
        )


# %% the rectified view


@dataclass(frozen=True)
class Orthophoto:
    """
    A metric top-down view of one horizontal plane, rectified from a camera image.
    """

    image: np.ndarray
    """
    The rectified colour image, shape ``(height, width, 3)`` of ``uint8``
    blue/green/red; black where the plane falls outside the camera's view.
    """

    region: WorkspaceRegion
    """
    The patch of the plane the image covers.
    """

    plane_height: float
    """
    Height of the rectified plane above the world frame's origin, in metres.
    """

    @property
    def observed(self) -> np.ndarray:
        """
        Mask of the pixels the camera actually saw, as opposed to the black border left
        where the plane runs outside its view.
        """
        return self.image.any(axis=2)

    def contour_center(self, contour: np.ndarray) -> Tuple[float, float]:
        """
        The world-frame ``(x, y)`` of a contour's centre of area.

        :param contour: An OpenCV contour in this image's pixels.
        """
        moments = cv2.moments(contour)
        if moments["m00"] == 0.0:
            pixel_x, pixel_y = contour.reshape(-1, 2).mean(axis=0)
            return self.region.to_world_position(float(pixel_x), float(pixel_y))
        return self.region.to_world_position(
            moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
        )


# %% rectification


@dataclass(frozen=True)
class OrthophotoProjector:
    """
    Builds the top-down view of a horizontal plane for a given camera pose.

    A plane seen by a pinhole camera maps to the image by a homography, so the whole
    rectification is one 3x3 matrix and a single warp, with no dependence on the depth
    image.
    """

    region: WorkspaceRegion
    """
    The patch of the plane to rectify.
    """

    def project(self, frame: RgbdFrame, plane_height: float) -> Orthophoto:
        """
        Rectify a frame's colour image onto a horizontal plane.

        :param frame: The camera data to rectify, carrying the camera's own pose.
        :param plane_height: Height of the plane above the world frame's origin, in
            metres.
        :return: The plane's top-down view.
        """
        image = cv2.warpPerspective(
            frame.color,
            self.pixel_T_region(frame, plane_height) @ self.region.region_T_pixel,
            (self.region.width_in_pixels, self.region.height_in_pixels),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        )
        return Orthophoto(image=image, region=self.region, plane_height=plane_height)

    @staticmethod
    def pixel_T_region(frame: RgbdFrame, plane_height: float) -> np.ndarray:
        """
        The 3x3 homography taking a point ``(x, y, 1)`` on a horizontal plane to the
        camera pixel that sees it.

        A world point on the plane is ``(x, y, plane_height)``, so projecting it drops
        the world frame's z-axis out of the camera matrix and folds it into the
        translation, leaving a homography in ``x`` and ``y`` alone.

        :param frame: The camera data, carrying the camera's own pose and intrinsics.
        :param plane_height: Height of the plane above the world frame's origin, in
            metres.
        """
        camera_T_reference_frame = inverse_frame(frame.reference_frame_T_camera)
        rotation = camera_T_reference_frame[:3, :3]
        translation = camera_T_reference_frame[:3, 3]
        plane_to_camera = np.column_stack(
            [
                rotation[:, 0],
                rotation[:, 1],
                rotation[:, 2] * plane_height + translation,
            ]
        )
        return frame.intrinsics.to_matrix() @ plane_to_camera
