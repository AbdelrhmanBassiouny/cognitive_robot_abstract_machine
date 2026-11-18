"""
Straight lines of an affine space.
"""

from __future__ import annotations

from typing_extensions import Generic, TypeVar

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood_spatial_math.point import PointT
from krrood_spatial_math.vector import VectorT

# %% straight lines given by a point and a direction


class Line(Generic[PointT, VectorT], SubClassSafeGeneric, Interface):
    """
    A straight line of an affine space: the points ``point + direction * t`` for every
    number ``t``.

    A direction alone fixes only which way a line runs, and every parallel line shares
    it; :attr:`point` fixes which of those lines this one is.
    """

    point: PointT
    """
    A point the line passes through, where ``t`` is zero.
    """

    direction: VectorT
    """
    The vector the line runs along, given in the frame of :attr:`point`.
    """


LineT = TypeVar("LineT", bound=Line)
"""
The kind of straight line of an affine space.
"""
