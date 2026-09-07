"""
Rectify the colour image onto a horizontal plane, giving a metric top-down view of that
plane.

Everything the board and the shapes need to be told apart is a flat footprint lying on a
known horizontal surface -- the table for the loose shapes, the board's lid for its
holes. Warping the camera view onto that surface removes the perspective the camera
adds, so a contour's area, side lengths, and orientation are read straight off in metres
and in the world frame, and the thresholds that classify it are real dimensions rather
than numbers tied to where the camera happened to stand.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path

import cv2
import numpy as np
from typing_extensions import Any, Dict, Self, Tuple

from experiments.montessori.perception.camera import RgbdFrame
from experiments.montessori.perception.exceptions import (
    RegionsDoNotMeet,
    WorkspaceOutOfView,
)
from experiments.montessori.planar_geometry import PlanarPoint
from krrood.adapters.json_serializer import SubclassJSONSerializer
from semantic_digital_twin.spatial_types.math import inverse_frame
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox

# %% the region being looked at

SAMPLE_ROUNDING_TOLERANCE = 1e-6
"""
How far, as a fraction of one sample, a grid position may sit from a whole number of
samples and still be read as that number.

Dividing metre-scale coordinates by a millimetre leaves the count a few parts in ten to
the thirteenth off, so a bound that lies exactly on a sample would otherwise be pushed
out to the next one.
"""

DEFAULT_RESOLUTION = 0.001
"""
Edge length of one rectified pixel, in metres, where nothing says otherwise.

One millimetre resolves the smallest hole on the board (a five millimetre wide slot)
across several pixels while keeping the rectified image small enough to process at
camera rate.
"""


class RegionField(StrEnum):
    """
    The keys a region is written under when it is kept as a file.
    """

    MINIMUM_X = "minimum_x"
    MAXIMUM_X = "maximum_x"
    MINIMUM_Y = "minimum_y"
    MAXIMUM_Y = "maximum_y"
    RESOLUTION = "resolution"


@dataclass(frozen=True)
class WorkspaceRegion(SubclassJSONSerializer):
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

    resolution: float = DEFAULT_RESOLUTION
    """
    Edge length of one rectified pixel, in metres.
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

    def to_pixels(self, positions: np.ndarray) -> np.ndarray:
        """
        The rectified pixels world-frame positions on this plane fall on.

        :param positions: The positions, as ``(n, 2)`` world-frame ``(x, y)`` points in
            metres.
        :return: The pixels, as ``(n, 2)`` fractional ``(column, row)`` points.
        """
        return (
            np.asarray(positions, dtype=float)
            - np.array([self.minimum_x, self.minimum_y])
        ) / self.resolution

    def meets(self, other: WorkspaceRegion) -> bool:
        """
        Whether this patch and another share any ground at all.

        Asked before :meth:`intersection`, which has nothing to answer for two that do
        not: a look narrowed past the surface it searches leaves that surface out
        rather than failing.

        :param other: The patch to compare against.
        """
        return (
            self.minimum_x <= other.maximum_x
            and other.minimum_x <= self.maximum_x
            and self.minimum_y <= other.maximum_y
            and other.minimum_y <= self.maximum_y
        )

    def intersection(self, other: WorkspaceRegion) -> WorkspaceRegion:
        """
        The ground this patch and another share, sampled on this patch's own grid.

        Two narrowings compose rather than the second replacing the first, which is what
        lets a look be cut down by a surface and by a stated region at once.

        **The grid is this patch's, and that is what makes the result less of the same
        picture rather than a different one.** A rectified pixel samples the world point
        its patch's own lower corner puts it over, so a narrowed patch whose corner fell
        between this one's samples would rectify every point half a pixel away from
        where this one had it -- measured on the shipped captures, enough to change
        which piece a fit settles on. So the shared ground is taken out to the nearest
        sample of this patch's grid, never in.

        :param other: The patch to narrow this one by.
        :raises RegionsDoNotMeet: If the two share no ground.
        """
        if not self.meets(other):
            raise RegionsDoNotMeet(
                bounds=(self.minimum_x, self.maximum_x, self.minimum_y, self.maximum_y),
                other_bounds=(
                    other.minimum_x,
                    other.maximum_x,
                    other.minimum_y,
                    other.maximum_y,
                ),
            )
        minimum_x = self._sample_at_or_below(self.minimum_x, other.minimum_x)
        minimum_y = self._sample_at_or_below(self.minimum_y, other.minimum_y)
        return WorkspaceRegion(
            minimum_x=minimum_x,
            maximum_x=min(
                self._sample_at_or_above(
                    minimum_x, min(self.maximum_x, other.maximum_x)
                ),
                self.maximum_x,
            ),
            minimum_y=minimum_y,
            maximum_y=min(
                self._sample_at_or_above(
                    minimum_y, min(self.maximum_y, other.maximum_y)
                ),
                self.maximum_y,
            ),
            resolution=self.resolution,
        )

    def _sample_at_or_below(self, origin: float, bound: float) -> float:
        """
        The last sample of this patch's grid that does not reach past a bound.

        :param origin: Where this patch's grid starts along the axis, in metres.
        :param bound: The bound to stay at or below, in metres.
        """
        if bound <= origin:
            return origin
        samples = (bound - origin) / self.resolution
        return (
            origin + math.floor(samples + SAMPLE_ROUNDING_TOLERANCE) * self.resolution
        )

    def _sample_at_or_above(self, origin: float, bound: float) -> float:
        """
        The first sample of this patch's grid that reaches a bound.

        :param origin: Where this patch's grid starts along the axis, in metres.
        :param bound: The bound to reach, in metres.
        """
        samples = (bound - origin) / self.resolution
        return origin + math.ceil(samples - SAMPLE_ROUNDING_TOLERANCE) * self.resolution

    def grown_by(self, margin: float) -> WorkspaceRegion:
        """
        This patch reaching the given distance further on every side.

        A thing is searched for by its centre but recognised by its whole outline, so a
        patch cut to where a centre may lie has to reach past that for the outline
        around it to still be in the picture.

        :param margin: How much further to reach, in metres.
        """
        return WorkspaceRegion(
            minimum_x=self.minimum_x - margin,
            maximum_x=self.maximum_x + margin,
            minimum_y=self.minimum_y - margin,
            maximum_y=self.maximum_y + margin,
            resolution=self.resolution,
        )

    @classmethod
    def of_box(
        cls, box: VolumetricBoundingBox, resolution: float = DEFAULT_RESOLUTION
    ) -> WorkspaceRegion:
        """
        The patch of plane a box stands over.

        :param box: The box, already expressed in the frame the patch is wanted in.
        :param resolution: Edge length of one rectified pixel, in metres.
        """
        return cls(
            minimum_x=float(box.min_x),
            maximum_x=float(box.max_x),
            minimum_y=float(box.min_y),
            maximum_y=float(box.max_y),
            resolution=resolution,
        )

    @classmethod
    def of_outline(
        cls, outline: np.ndarray, resolution: float = DEFAULT_RESOLUTION
    ) -> WorkspaceRegion:
        """
        The patch of plane an outline spans.

        This is how a surface that was *seen* rather than modelled says where it
        reaches, which is what a surface whose pose the world no longer agrees with has
        to be read from.

        :param outline: The outline, as ``(n, 2)`` world-frame ``(x, y)`` points in
            metres.
        :param resolution: Edge length of one rectified pixel, in metres.
        """
        points = np.asarray(outline, dtype=float).reshape(-1, 2)
        return cls(
            minimum_x=float(points[:, 0].min()),
            maximum_x=float(points[:, 0].max()),
            minimum_y=float(points[:, 1].min()),
            maximum_y=float(points[:, 1].max()),
            resolution=resolution,
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

    def to_json(self) -> Dict[str, Any]:
        return {
            **super().to_json(),
            RegionField.MINIMUM_X.value: self.minimum_x,
            RegionField.MAXIMUM_X.value: self.maximum_x,
            RegionField.MINIMUM_Y.value: self.minimum_y,
            RegionField.MAXIMUM_Y.value: self.maximum_y,
            RegionField.RESOLUTION.value: self.resolution,
        }

    @classmethod
    def _from_json(cls, data: Dict[str, Any]) -> Self:
        return cls(
            minimum_x=data[RegionField.MINIMUM_X.value],
            maximum_x=data[RegionField.MAXIMUM_X.value],
            minimum_y=data[RegionField.MINIMUM_Y.value],
            maximum_y=data[RegionField.MAXIMUM_Y.value],
            resolution=data[RegionField.RESOLUTION.value],
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """
        Read a region back from the file it was written to.

        :param path: The file to read.
        """
        return cls.from_json(json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        """
        Write this region down, so a later run searches what this one settled on.

        :param path: The file to write.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=2) + "\n")


# %% the space being looked at


@dataclass(frozen=True)
class WorkspaceBox:
    """
    The stretch of table perception looks at, together with the room above it that
    anything worth seeing stands in.

    Everything outside it is somebody else's: the far half of the table, the floor
    beyond its edge, whatever is stacked against the wall behind. Cutting the camera
    image down to this box is what makes a window onto the scene show the scene.
    """

    region: WorkspaceRegion
    """
    The patch of the table the box stands on.
    """

    minimum_height: float
    """
    Height of the box's floor above the world frame's origin, in metres.
    """

    maximum_height: float
    """
    Height of the box's ceiling above the world frame's origin, in metres.
    """

    @property
    def corners(self) -> np.ndarray:
        """
        The box's eight corners, as ``(8, 3)`` world-frame points in metres.
        """
        return np.array(
            [
                [x, y, height]
                for x in (self.region.minimum_x, self.region.maximum_x)
                for y in (self.region.minimum_y, self.region.maximum_y)
                for height in (self.minimum_height, self.maximum_height)
            ]
        )

    def outline_in(self, frame: RgbdFrame) -> np.ndarray:
        """
        The outline this box covers in a camera image.

        :param frame: The camera data, carrying the camera's own pose.
        :return: The outline as an OpenCV contour, in image pixels.
        """
        return cv2.convexHull(frame.project(self.corners).astype(np.float32))

    def clip(self, image: np.ndarray, frame: RgbdFrame) -> np.ndarray:
        """
        Cut a camera image down to the part of it this box covers.

        :param image: An image taken through ``frame``'s camera, of any number of
            channels.
        :param frame: The camera data the image was taken with.
        :return: The image cropped to the box, blacked out where the box does not reach.
        """
        covered = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(
            covered, np.round(self.outline_in(frame)).astype(np.int32), 255
        )
        left, top, width, height = cv2.boundingRect(covered)
        if width == 0 or height == 0:
            raise WorkspaceOutOfView(image.shape[:2])
        kept = np.zeros_like(image)
        inside = covered > 0
        kept[inside] = image[inside]
        return kept[top : top + height, left : left + width]


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

    @cached_property
    def hue_saturation_value(self) -> np.ndarray:
        """
        The rectified image as hue, saturation and value, which is what every colour a
        surface or a piece is measured in.

        Kept once per view rather than converted at each reading: the same plane is read
        for several colours in turn, and the conversion costs more than any one of those
        readings.
        """
        return cv2.cvtColor(self.image, cv2.COLOR_BGR2HSV)

    @cached_property
    def observed(self) -> np.ndarray:
        """
        Mask of the pixels the camera actually saw, as opposed to the black border left
        where the plane runs outside its view.
        """
        return self.image.any(axis=2)

    def contour_center(self, contour: np.ndarray) -> PlanarPoint:
        """
        Where on this image's own plane a contour's centre of area lies.

        :param contour: An OpenCV contour in this image's pixels.
        """
        moments = cv2.moments(contour)
        if moments["m00"] == 0.0:
            pixel_x, pixel_y = contour.reshape(-1, 2).mean(axis=0)
            return PlanarPoint(
                *self.region.to_world_position(float(pixel_x), float(pixel_y))
            )
        return PlanarPoint(
            *self.region.to_world_position(
                moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
            )
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
