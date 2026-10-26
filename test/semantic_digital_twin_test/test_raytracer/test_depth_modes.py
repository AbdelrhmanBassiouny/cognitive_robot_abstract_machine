"""
Depth conventions and extension through custom depth calculations.
"""

from __future__ import annotations

# %% Imports
from dataclasses import dataclass

import numpy as np
import pytest
from typing_extensions import TYPE_CHECKING

from semantic_digital_twin.datastructures.camera_rendering import (
    DepthMode,
    OpticalAxisDepthMode,
    RayDistanceDepthMode,
)
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix
from semantic_digital_twin.testing import ray_test_world

from .test_camera_rendering import camera_intersections

if TYPE_CHECKING:
    import numpy.typing as npt

    from .test_camera_rendering import CameraIntersections


# %% Physical depth conventions
@pytest.mark.parametrize(
    ("depth_mode", "expected_depths"),
    [
        (OpticalAxisDepthMode(), [2.0, 2.0]),
        (RayDistanceDepthMode(), [2.0, np.sqrt(13.0)]),
    ],
)
def test_depth_mode_with_translated_and_rotated_camera(
    depth_mode: DepthMode, expected_depths: list[float]
) -> None:
    """
    Depth conventions account for the world-space camera pose and ray origins.
    """
    hit_points = np.array([[8.0, 2.0, 3.0], [8.0, 5.0, 3.0]])
    ray_origins = np.array([[10.0, 2.0, 3.0], [10.0, 2.0, 3.0]])
    ray_directions = hit_points - ray_origins
    ray_directions /= np.linalg.norm(ray_directions, axis=1, keepdims=True)
    world_T_camera = np.array(
        [
            [0.0, 0.0, 1.0, 10.0],
            [0.0, 1.0, 0.0, 2.0],
            [-1.0, 0.0, 0.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )

    depths = depth_mode.hit_depth(
        hit_points, ray_origins, ray_directions, world_T_camera
    )

    np.testing.assert_allclose(depths, expected_depths)


def test_optical_axis_depth_rejects_hits_outside_forward_half_space() -> None:
    """
    Points on or behind the camera plane have invalid optical depth.
    """
    hit_points = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    depths = OpticalAxisDepthMode().hit_depth(
        hit_points=hit_points,
        ray_origins=np.zeros((2, 3)),
        ray_directions=np.array([[0.0, 0.0, -1.0], [0.0, 0.0, 1.0]]),
        world_T_camera=np.eye(4),
    )

    np.testing.assert_array_equal(depths, np.full(2, -1.0))


# %% Custom depth convention
@dataclass(frozen=True)
class WorldPlaneDepthMode(DepthMode):
    """
    Measure signed distance from a plane perpendicular to the world's x axis.
    """

    plane_x: float = -2.0
    """
    World x coordinate of the reference plane.
    """

    def hit_depth(
        self,
        hit_points: npt.NDArray[np.float64],
        ray_origins: npt.NDArray[np.float64],
        ray_directions: npt.NDArray[np.float64],
        world_T_camera: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        return hit_points[:, 0] - self.plane_x


# %% Depth mode dispatch
def test_custom_depth_mode_controls_hit_depths(
    camera_intersections: CameraIntersections,
) -> None:
    """
    A new depth convention computes depths without changes to the raytracer.
    """
    fixture = camera_intersections
    frame = fixture.ray_tracer.create_segmentation_and_depth(
        HomogeneousTransformationMatrix(),
        resolution=fixture.resolution,
        depth_mode=WorldPlaneDepthMode(),
    )
    expected = np.full(
        (fixture.resolution.width, fixture.resolution.height), -1.0, dtype=np.float32
    )
    expected[0, 0] = 2.0
    expected[1, 0] = 3.5
    np.testing.assert_array_equal(frame.depth, expected)
