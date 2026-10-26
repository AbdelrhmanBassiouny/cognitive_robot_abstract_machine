"""
Color and depth conventions for aligned ray-traced camera images.
"""

from __future__ import annotations

# %% Imports
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import numpy as np
import trimesh
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy.typing as npt

    from semantic_digital_twin.datastructures.camera_model import PinholeCameraModel
    from semantic_digital_twin.world_description.world_entity import Body


# %% Rendering conventions
class ColorRenderingMode(StrEnum):
    """
    Select how the ray tracer produces the color image.
    """

    BODY_COLOR = "body_color"
    """
    Color each visible body uniformly with its first collision geometry color.
    """

    TEXTURED = "textured"
    """
    Render surface textures and materials.
    """


# %% Depth conventions
@dataclass(frozen=True)
class DepthMode(ABC):
    """
    Compute one meter depth per surface hit, using negative values for invalid depths.
    """

    @abstractmethod
    def hit_depth(
        self,
        hit_points: npt.NDArray[np.float64],
        ray_origins: npt.NDArray[np.float64],
        ray_directions: npt.NDArray[np.float64],
        world_T_camera: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """
        Return depths aligned with the input hits.

        :param hit_points: World-space surface points, one row per hit.
        :param ray_origins: World-space ray origins aligned with the hits.
        :param ray_directions: World-space unit ray directions aligned with the hits.
        :param world_T_camera: Pose of the rendering camera, looking along its negative z axis.
        :return: Meter depths, with negative values for invalid depths.
        """
        ...


@dataclass(frozen=True)
class OpticalAxisDepthMode(DepthMode):
    """
    Measure depth along the rendering camera's negative z axis.
    """

    def hit_depth(
        self,
        hit_points: npt.NDArray[np.float64],
        ray_origins: npt.NDArray[np.float64],
        ray_directions: npt.NDArray[np.float64],
        world_T_camera: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        camera_T_world = np.linalg.inv(world_T_camera)
        world_P_hits = np.concatenate(
            [hit_points, np.ones((len(hit_points), 1))], axis=1
        )
        camera_P_hits = (camera_T_world @ world_P_hits.T).T
        depths = -camera_P_hits[:, 2]
        return np.where(depths > 0.0, depths, -1.0)


@dataclass(frozen=True)
class RayDistanceDepthMode(DepthMode):
    """
    Measure depth from each ray origin along its viewing direction.
    """

    def hit_depth(
        self,
        hit_points: npt.NDArray[np.float64],
        ray_origins: npt.NDArray[np.float64],
        ray_directions: npt.NDArray[np.float64],
        world_T_camera: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        return trimesh.util.diagonal_dot(hit_points - ray_origins, ray_directions)


# %% Aligned depth and segmentation
@dataclass
class SegmentationDepthFrame:
    """
    Segmentation and meter depths produced by one camera intersection query.
    """

    segmentation: np.ndarray
    """
    World-body indices with negative values for pixels without a hit.
    """
    depth: np.ndarray
    """
    Depths in meters with negative values for pixels without a valid depth.
    """


# %% Aligned RGB-D products
@dataclass
class RenderedRGBDFrame:
    """
    Contain aligned width-first images with their origin at the top-left pixel.
    """

    color_bgr: np.ndarray
    """
    Color image encoded in BGR channel order.
    """

    depth_in_millimeters: np.ndarray
    """
    Depth in the selected convention, encoded in unsigned millimeters.
    """

    segmentation: np.ndarray
    """
    Body-index segmentation image aligned with the color and depth images.
    """

    object_color_map: dict[str, list[str]]
    """
    Visible body names grouped by comma-separated RGB color keys.
    """

    camera_model: PinholeCameraModel
    """
    Effective projection model used to render the frame.
    """


# %% Camera rays
@dataclass
class CameraRays:
    """
    World-space viewing rays and the image pixels they represent.
    """

    origin_points: np.ndarray
    """
    World-space starting point for each viewing ray.
    """
    direction_vectors: np.ndarray
    """
    World-space viewing direction of each ray.
    """
    pixel_coordinates: np.ndarray
    """
    Width-first image coordinates with their origin at the top-left pixel.
    """


@dataclass
class RayIntersections:
    """
    Surface intersections and their source rays and world bodies.
    """

    hit_points: np.ndarray
    """
    World-space points where rays intersect world geometry.
    """
    ray_indices: np.ndarray
    """
    Source ray index for each intersection.
    """
    bodies: list[Body]
    """
    World body intersected at each hit point.
    """


# %% Color image products
@dataclass
class RenderedColorFrame:
    """
    BGR image values and the associated body names grouped by color.
    """

    color_image: np.ndarray
    """
    Width-first color image in BGR channel order.
    """
    object_color_map: dict[str, list[str]]
    """
    Visible body names grouped by comma-separated RGB color keys.
    """
