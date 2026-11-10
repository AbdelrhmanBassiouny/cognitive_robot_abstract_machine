"""
The laws every space map obeys, run against each implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.space_map import SpaceMap
from krrood_spatial_math.spatial_types import (
    CartesianPoint2D,
    OrthogonalProjection,
)

from .dataset.frames import NamedFrame

# %% the space maps every law runs against


@dataclass
class SpaceMapCase:
    """
    A space map together with an image point it is tested at.
    """

    space_map: SpaceMap
    """
    The space map under test.
    """

    image_point: CartesianPoint2D
    """
    A point of the space map's target space.
    """


@pytest.fixture(
    params=[OrthogonalProjection],
    ids=lambda space_map_type: space_map_type.__name__,
)
def space_map_case(request: pytest.FixtureRequest) -> SpaceMapCase:
    """
    Each space map implementation, onto the plane of one frame.
    """
    frame = NamedFrame("plane")
    return SpaceMapCase(
        space_map=request.param(frame),
        image_point=CartesianPoint2D(1.5, -2.0, reference_frame=frame),
    )


positions_along_line = [-3.0, 0.0, 0.5, 4.0]


# %% inverse laws


@pytest.mark.parametrize("position_along_line", positions_along_line)
def test_project_after_unproject_restores_the_image_point(
    space_map_case: SpaceMapCase, position_along_line: float
):
    """
    Every point unprojected from an image point projects back onto it.
    """
    space_map, image_point = space_map_case.space_map, space_map_case.image_point

    round_trip = space_map.project(
        space_map.unproject(image_point, position_along_line)
    )

    np.testing.assert_allclose(round_trip.to_np(), image_point.to_np())


@pytest.mark.parametrize("position_along_line", positions_along_line)
def test_unproject_lies_at_its_position_on_the_projection_line(
    space_map_case: SpaceMapCase, position_along_line: float
):
    """
    An unprojected point lies on the projection line, as many direction lengths from its
    point as its position along the line.
    """
    space_map, image_point = space_map_case.space_map, space_map_case.image_point
    projection_line = space_map.projection_line(image_point)

    unprojected = space_map.unproject(image_point, position_along_line)

    np.testing.assert_allclose(
        unprojected.to_np(),
        (
            projection_line.point + projection_line.direction * position_along_line
        ).to_np(),
    )


# %% the interface itself


def test_a_space_map_cannot_be_instantiated():
    """
    A space map is an interface, implemented but never instantiated.
    """
    with pytest.raises(InterfaceInstantiationError):
        SpaceMap()
