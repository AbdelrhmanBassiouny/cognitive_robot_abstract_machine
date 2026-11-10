from __future__ import annotations

from dataclasses import dataclass

from krrood_spatial_math.spatial_types import Pose3D


@dataclass
class PoseTrajectory:
    """
    Immutable wrapper for a sequence of waypoint poses.
    """

    poses: list[Pose3D]
    """
    Ordered waypoint poses.
    """
