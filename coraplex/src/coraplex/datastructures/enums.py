"""
Module holding all enums of CoraPlex.
"""

from __future__ import annotations

from enum import Enum, auto, StrEnum


class ReachFraction(float, Enum):
    """
    How far the robot stands off what it reaches for, as a fraction of the arm's length.
    """

    GRASPING = 0.6
    """
    Reaching something that stays where it is.
    """

    ACCESSING = 0.66
    """
    Working a container's handle.

    A container is pulled open towards the robot, so it stands further back than it does
    to reach something that stays where it is.
    """


class PerceptionSource(Enum):
    """
    The kinds of source a perception query can be answered by.
    """

    WORLD_MODEL = auto()
    """
    The world model, read the way a perfect sensor would see it, for a simulated robot.
    """

    ROBOKUDO = auto()
    """
    A RoboKudo pipeline, for the real robot.
    """


class VisualizationBackend(StrEnum):
    """The renderer selected for a simulated world."""

    NONE = "none"
    """Run without a renderer."""
    RVIZ = "rviz"
    """Publish native ROS visualization markers."""
    RERUN = "rerun"
    """Use the native Rerun adapter."""
    CRAMERA = "cramera"
    """Use an installed browser visualization provider."""


class ActionTrialVisualization(StrEnum):
    """
    Where the world copy an action trial runs in is published while debugging, apart
    from the world it copies.
    """

    FRAME_PREFIX = "action_trial/"
    """
    Put in front of every tf frame of the copy.
    """

    MARKER_TOPIC = "/semworld/action_trial/viz_marker"
    """
    The topic the markers of the copy are published on.
    """


class VisualizationOption(StrEnum):
    """
    Configuration names for optional visualization providers.
    """

    BACKEND = "CORAPLEX_VISUALIZATION"
    """
    Environment setting selecting the renderer.
    """

    RERUN_MODE = "CORAPLEX_RERUN_MODE"
    """
    Environment setting selecting Rerun's output mode.
    """

    RERUN_TARGET = "CORAPLEX_RERUN_TARGET"
    """
    Environment setting selecting Rerun's file or server.
    """

    PROVIDER_GROUP = "coraplex.visualizations"
    """
    Installed entry points naming a
    :class:`~coraplex.visualization.WorldVisualization` subclass.
    """


class PouringSide(StrEnum):
    """
    The side of a target container, as the robot sees it, that is poured from.
    """

    LEFT = "left"
    RIGHT = "right"


class JointType(Enum):
    """
    Enum for readable joint types.
    """

    REVOLUTE = 0
    PRISMATIC = 1
    SPHERICAL = 2
    PLANAR = 3
    FIXED = 4
    UNKNOWN = 5
    CONTINUOUS = 6
    FLOATING = 7


class AxisIdentifier(Enum):
    """
    Enum for translating the axis name to a vector along that axis.
    """

    X = (1, 0, 0)
    Y = (0, 1, 0)
    Z = (0, 0, 1)
    Undefined = (0, 0, 0)

    @classmethod
    def from_tuple(cls, axis_tuple):
        return next((axis for axis in cls if axis.value == axis_tuple), None)


class DetectionTechnique(int, Enum):
    """
    Enum for techniques for detection tasks.
    """

    ALL = 0
    HUMAN = 1
    TYPES = 2
    REGION = 3
    HUMAN_ATTRIBUTES = 4
    HUMAN_WAVING = 5


class DetectionState(int, Enum):
    """
    Enum for the state of the detection task.
    """

    START = 0
    STOP = 1
    PAUSE = 2


class MovementType(Enum):
    """
    Enum for the different movement types of the robot.
    """

    STRAIGHT_TRANSLATION = auto()
    STRAIGHT_CARTESIAN = auto()
    TRANSLATION = auto()
    CARTESIAN = auto()


class InsertionPosition(Enum):
    """
    When the nodes a sequential insertion inserts run relative to the anchor node.
    """

    BEFORE = auto()
    """
    Right before the anchor node.
    """

    AFTER = auto()
    """
    Right after the anchor node.
    """


class CuttingTechnique(Enum):
    """
    Enum for the techniques of cutting an object.
    """

    SLICE = auto()
    """
    Cut the object into slices of equal thickness.
    """
    SAW = auto()
    """
    Cut with a repeated back-and-forth sawing motion.
    """
    HALVING = auto()
    """
    Cut the object into two halves.
    """


class SlicingPriority(Enum):
    """
    Decides which slicing parameter is kept when the requested slice thickness and
    number of cuts cannot both fit the object.
    """

    THICKNESS = auto()
    """
    Keep the requested slice thickness and reduce the number of cuts to fit.
    """
    CUT_COUNT = auto()
    """
    Keep the requested number of cuts and shrink the slice thickness to fit.
    """


class ToolPathSegmentKind(Enum):
    """
    Enum for the geometric pattern a tool path segment follows.
    """

    APPROACH = auto()
    """
    Vertical approach from above onto the object.
    """
    DESCEND = auto()
    """
    Straight downward cut into the object.
    """
    SAW = auto()
    """
    Oscillatory shear motion with increasing depth.
    """
    RETRACT = auto()
    """
    Vertical retraction away from the object.
    """
    SPIRAL = auto()
    """
    Planar spiral with growing radius.
    """
    STIR = auto()
    """
    Continuous circular stirring loop.
    """
    SHEAR = auto()
    """
    Planar oscillatory shear at constant depth.
    """
    RASTER = auto()
    """
    Planar raster scan covering a rectangle.
    """
    SWEEP = auto()
    """
    Sinusoidal sweep along one axis.
    """


class WipingTechnique(Enum):
    """
    Enum for the techniques of wiping a surface.
    """

    WIPE = auto()
    """
    Wipe along a spiral covering the surface.
    """
    SHEAR = auto()
    """
    Wipe with an oscillatory shear motion.
    """
    SPREAD = auto()
    """
    Spread along straight lanes covering the surface.
    """


class MixingPattern(Enum):
    """
    Enum for the motion patterns of mixing the contents of a container.
    """

    SPIRAL = auto()
    """
    Mix along an outward spiral.
    """
    STIR = auto()
    """
    Mix along circular stirring laps.
    """
