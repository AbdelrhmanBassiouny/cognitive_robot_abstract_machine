from __future__ import annotations

from dataclasses import dataclass

from krrood.exceptions import DataclassException
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
from semantic_digital_twin.world_description.world_entity import Body

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


# %% placing into the basin


@dataclass
class NoStandingPoseInFrontOfTheBasin(DataclassException):
    """
    Raised when the robot comes closer to the kitchen than collision avoidance keeps it
    wherever it stands in front of a basin.
    """

    basin_center: Point3
    """
    The centre of the basin floor the robot faces.
    """

    maximum_distance: float
    """
    How far in front of the basin the robot stood at most.
    """

    def error_message(self) -> str:
        return (
            f"The robot comes too close to the kitchen everywhere up to "
            f"{self.maximum_distance} m in front of the basin at {self.basin_center}."
        )

    def suggest_correction(self) -> str:
        return "Allow the robot to stand further away from the basin."


@dataclass
class NoPathIntoTheBasin(DataclassException):
    """
    Raised when no path leads through the free space around a sink into its basin.
    """

    entry: Point3
    """
    Where the path into the basin was to start.
    """

    release: Point3
    """
    Where the path was to end, above where the object is let go of in the basin.
    """

    def error_message(self) -> str:
        return f"No path leads through free space from {self.entry} to {self.release}."

    def suggest_correction(self) -> str:
        return (
            "Keep the path less far off the kitchen, or search a larger space for it."
        )


@dataclass
class NoFreeSpotInTheBasin(DataclassException):
    """
    Raised when an object fits nowhere on the floor of a basin without touching
    something already there.
    """

    held_object: Body
    """
    The object to be placed into the basin.
    """

    basin_center: Point3
    """
    The centre of the basin floor.
    """

    def error_message(self) -> str:
        return (
            f"{self.held_object.name} fits nowhere on the floor of the basin at "
            f"{self.basin_center} without touching something already there."
        )

    def suggest_correction(self) -> str:
        return "Clear the basin, or let go of the object higher above its floor."
