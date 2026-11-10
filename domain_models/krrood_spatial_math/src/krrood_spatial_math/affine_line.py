"""
Straight lines of an affine space.
"""

from __future__ import annotations

from typing_extensions import Generic

from krrood.patterns.interface import Interface
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood_spatial_math.affine_point import AffinePointT
from krrood_spatial_math.affine_vector import AffineVectorT

# %% straight lines given by a point and a direction


class AffineLine(Generic[AffinePointT, AffineVectorT], SubClassSafeGeneric, Interface):
    """
    The straight line through a point that runs along a vector: every point the
    direction, scaled by some number, moves :attr:`point` to.
    """

    point: AffinePointT
    """
    A point the line passes through.
    """

    direction: AffineVectorT
    """
    The vector the line runs along, given in the frame of :attr:`point`.
    """
