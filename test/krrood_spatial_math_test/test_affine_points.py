from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.affine_point import (
    AffinePoint,
    AffinePoint2D,
    AffinePoint3D,
    CartesianPoint,
    CoordinateT,
)
from krrood_spatial_math.coordinate_system import (
    AffineFrame,
    AffineFrameT,
    CartesianFrame,
    CartesianFrameT,
    CoordinateRepresentation,
)

from .dataset.spaces import (
    ScalablePlaneFrame,
    ScalableSpaceFrame,
    StoredScalablePlanePoint,
    StoredScalableSpacePoint,
)

# %% points given in an affine frame


affine_points = [AffinePoint, AffinePoint2D, AffinePoint3D, CartesianPoint]


@pytest.mark.parametrize("affine_point", affine_points)
def test_an_affine_point_cannot_be_instantiated(affine_point):
    with pytest.raises(InterfaceInstantiationError):
        affine_point()


@pytest.mark.parametrize("affine_point", affine_points)
def test_an_affine_point_is_a_coordinate_representation(affine_point):
    assert issubclass(affine_point, CoordinateRepresentation)


@pytest.mark.parametrize("affine_point", [AffinePoint2D, AffinePoint3D, CartesianPoint])
def test_a_point_of_any_dimension_is_an_affine_point(affine_point):
    assert issubclass(affine_point, AffinePoint)


def test_a_cartesian_point_is_given_in_a_cartesian_frame():
    assert CartesianPoint.__parameters__ == (CartesianFrameT, CoordinateT)
    assert CartesianFrameT.__bound__ is CartesianFrame


def test_a_three_dimensional_affine_point_is_not_a_two_dimensional_one():
    assert not issubclass(AffinePoint3D, AffinePoint2D)


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


def test_a_three_dimensional_points_fields_are_narrowed_to_the_bound_types():
    point_types = {
        point_field.name: point_field.type
        for point_field in fields(StoredScalableSpacePoint)
    }

    assert point_types == {
        "x": float,
        "y": float,
        "z": float,
        "coordinate_system": ScalableSpaceFrame | None,
    }
