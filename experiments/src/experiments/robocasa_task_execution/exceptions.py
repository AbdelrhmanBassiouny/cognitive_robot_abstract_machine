from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException
from semantic_digital_twin.spatial_types.spatial_types import Pose

# %% where the robot starts


@dataclass
class NoClearStandingPose(DataclassException):
    """
    Raised when the robot collides with the kitchen wherever it stands behind the start
    pose RoboCasa gives.
    """

    start_pose: Pose
    """
    RoboCasa's start pose, which the robot stepped back from.
    """

    maximum_distance: float
    """
    How far behind the start pose the robot stood at most.
    """

    def error_message(self) -> str:
        return (
            f"The robot collides with the kitchen everywhere up to "
            f"{self.maximum_distance} m behind its start pose {self.start_pose}."
        )

    def suggest_correction(self) -> str:
        return "Allow the robot to step back further, or compose another episode."
