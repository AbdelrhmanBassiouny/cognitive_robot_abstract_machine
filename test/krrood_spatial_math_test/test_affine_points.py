from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.affine_point import AffinePoint2D, CoordinateT
from krrood_spatial_math.coordinate_system import (
    AffineFrame,
    AffineFrameT,
    CoordinateRepresentation,
)

from .dataset.spaces import ScalablePlaneFrame, StoredScalablePlanePoint

# %% points given in an affine frame


def test_an_affine_point_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        AffinePoint2D()


def test_an_affine_point_is_a_coordinate_representation():
    assert issubclass(AffinePoint2D, CoordinateRepresentation)


def test_an_affine_point_is_given_in_an_affine_frame():
    assert AffineFrameT.__bound__ is AffineFrame


def test_a_point_reports_the_kind_of_frame_it_is_given_in():
    assert (
        StoredScalablePlanePoint.get_type_of_generic_parameter(AffineFrameT)
        is ScalablePlaneFrame
    )


def test_a_point_reports_what_its_coordinates_are_stored_as():
    assert StoredScalablePlanePoint.get_type_of_generic_parameter(CoordinateT) is float


def test_a_points_fields_are_narrowed_to_the_bound_types():
    point_types = {
        point_field.name: point_field.type
        for point_field in fields(StoredScalablePlanePoint)
    }

    assert point_types == {
        "x": float,
        "y": float,
        "coordinate_system": ScalablePlaneFrame | None,
    }
