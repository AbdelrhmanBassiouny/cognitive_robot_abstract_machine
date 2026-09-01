"""
Points, extents and known outlines on a horizontal plane.

The board's holes, the pieces resting on a surface and the places a piece is believed to
be are all measured on some horizontal plane, so where something is on one is said once
here rather than as a pair of numbers whose order every reader has to remember. Which
plane a measurement is on is said by whatever holds it.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

# %% where something is


@dataclass(frozen=True)
class PlanarPoint:
    """
    A point on a horizontal plane.
    """

    x: float
    """
    Position along the plane's x-axis, in metres.
    """

    y: float
    """
    Position along the plane's y-axis, in metres.
    """


@dataclass(frozen=True)
class PlanarSize:
    """
    How far something reaches along a horizontal plane's two axes.
    """

    x: float
    """
    Reach along the plane's x-axis, in metres.
    """

    y: float
    """
    Reach along the plane's y-axis, in metres.
    """


# %% outlines that are known before they are looked for


def turned(points: np.ndarray, angle: float) -> np.ndarray:
    """
    Turn points about the plane's origin.

    :param points: ``(n, 2)`` ``(x, y)`` points in metres.
    :param angle: How far to turn them, in radians about the world frame's z-axis.
    :return: The turned points, in the same shape.
    """
    cosine, sine = math.cos(angle), math.sin(angle)
    return points @ np.array([[cosine, sine], [-sine, cosine]])


def points_along(outline: np.ndarray, spacing: float) -> np.ndarray:
    """
    Spread points evenly along a closed outline, corners included.

    :param outline: The outline's corners, as ``(n, 2)`` ``(x, y)`` points in metres.
    :param spacing: How far apart, in metres, to place the points.
    :return: The points, as ``(m, 2)`` ``(x, y)`` points in metres.
    """
    corners = np.vstack([outline, outline[:1]])
    walked = []
    for start, end in zip(corners[:-1], corners[1:]):
        steps = max(1, int(round(float(np.linalg.norm(end - start)) / spacing)))
        walked.append(start + np.outer(np.arange(steps) / steps, end - start))
    return np.vstack(walked)


class KnownOutline(ABC):
    """
    Something whose outline this scene knows exactly before it is looked for, and which
    can be laid over a picture at any placement.

    Recognising one is therefore not *what shape is this* but *where is it and how is it
    turned*, which is a question a sweep over placements answers and whose answer carries
    how well it fitted.
    """

    @abstractmethod
    def outline_points(self, angle: float, spacing: float) -> np.ndarray:
        """
        The points its outline covers, turned about its own origin.

        :param angle: How far to turn it, in radians about the world frame's z-axis.
        :param spacing: How far apart, in metres, the points stand.
        :return: The points, as ``(n, 2)`` ``(x, y)`` points in metres about its origin.
        """

    @abstractmethod
    def smallest_equivalent_turn(self, angle: float) -> float:
        """
        The smallest turn that leaves it looking the way the given one does.

        :param angle: A turn about the world frame's z-axis, in radians.
        """
