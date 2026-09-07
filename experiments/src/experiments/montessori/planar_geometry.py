"""
Points and extents on a horizontal plane.

The board's holes, the pieces resting on a surface and the places a piece is believed to
be are all measured on some horizontal plane, so where something is on one is said once
here rather than as a pair of numbers whose order every reader has to remember. Which
plane a measurement is on is said by whatever holds it.
"""

from __future__ import annotations

from dataclasses import dataclass


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
