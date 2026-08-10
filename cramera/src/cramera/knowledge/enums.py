"""
Enums shared across the knowledge package.
"""

from __future__ import annotations

from enum import Enum

from typing_extensions import Union


class JointRegion(str, Enum):
    """
    Which region of the robot/scene a joint belongs to, as inferred from its name.

    Arms and grippers use :class:`coraplex.datastructures.enums.Arms` instead, since
    they always name a specific arm; a joint can also belong to the robot's body or to
    the environment, which :class:`~coraplex.datastructures.enums.Arms` has no member
    for.
    """

    LEFT = "left"
    RIGHT = "right"
    BODY = "body"
    ENVIRONMENT = "environment"


class NodeGroup(str, Enum):
    """
    Colour group of a graph-panel node.
    """

    ROBOT = "robot"
    OBJECT = "object"
    EVENT = "event"
    ROOT = "root"
    PACKAGE = "package"
    SUBPACKAGE = "subpackage"
    PLAN = "plan"
    PYTHON_CLASS = "python_class"
    EXTERNAL_CLASS = "external_class"
    OTHER = "other"


class EdgeKind(str, Enum):
    """
    Rendering kind of a graph-panel edge.
    """

    PROPERTY = "property"
    TYPE = "type"


class KinematicChainGroup(str, Enum):
    """
    Colour group of a link in the robot's kinematic tree.

    Separate from :class:`NodeGroup`, whose members name ontological categories of the
    knowledge graph: a right arm is not an "event", it just needs a colour of its own.
    """

    BASE = "base"
    LEFT_ARM = "left_arm"
    RIGHT_ARM = "right_arm"
    GRIPPER = "gripper"
    SENSOR = "sensor"


class PlanNodeGroup(str, Enum):
    """
    Colour group of a node in the executed plan tree.

    Separate from :class:`NodeGroup` for the same reason as
    :class:`KinematicChainGroup`: a motion is not a robot and a condition is not a goal,
    they are kinds of plan node that each need a colour of their own.
    """

    ACTION = "action"
    MOTION = "motion"
    CONDITION = "condition"
    ATTACHMENT = "attachment"
    OTHER = "other_plan_node"


ColourGroup = Union[NodeGroup, KinematicChainGroup, PlanNodeGroup]
"""
Any colour group a graph-panel node can carry: an ontological one from the knowledge
graph, or a kinematic-chain one from the URDF tree.
"""
