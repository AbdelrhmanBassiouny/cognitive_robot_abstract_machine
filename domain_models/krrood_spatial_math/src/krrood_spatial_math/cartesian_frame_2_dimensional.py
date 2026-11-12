from __future__ import annotations

from krrood.patterns.identifier_and_name import NameT
from krrood.patterns.interface import Interface
from krrood_spatial_math.coordinate_system import CartesianFrame
from krrood_spatial_math.space import EuclideanSpace2Dimensional

# %% frames that values on a plane are given in


class CartesianFrame2Dimensional(
    CartesianFrame[EuclideanSpace2Dimensional, NameT], Interface
):
    """
    A right-handed Cartesian frame on a two-dimensional Euclidean space, in metres, such
    as the x-y plane of a :class:`~krrood_spatial_math.cartesian_frame_3_dimensional.Car
    tesianFrame3Dimensional`.

    Right-handed means its y-axis is a quarter turn counterclockwise from its x-axis.
    """
