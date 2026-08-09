"""
Enums shared across the knowledge package.
"""

from __future__ import annotations

from enum import Enum


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
    CONCEPT = "concept"
    KLASS = "klass"
    GOAL = "goal"
    PYCLASS = "pyclass"
    UPPER = "upper"
    OTHER = "ind"


class EdgeKind(str, Enum):
    """
    Rendering kind of a graph-panel edge.
    """

    PROP = "prop"
    TYPE = "type"
