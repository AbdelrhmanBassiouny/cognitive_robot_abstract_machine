from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.affine_line import AffineLine
from krrood_spatial_math.affine_point import AffinePoint, AffinePointT, CartesianPoint
from krrood_spatial_math.affine_vector import (
    AffineVector,
    AffineVectorT,
    CartesianVector,
    CartesianVectorT,
)
from krrood_spatial_math.coordinate_system import (
    AffineFrame,
    AffineFrameT,
    CartesianFrame,
    CartesianFrameT,
    CoordinateRepresentation,
    CoordinateT,
)

from .dataset.spaces import (
    ScalablePlaneFrame,
    StoredScalablePlaneLine,
    StoredScalablePlanePoint,
    StoredScalablePlaneVector,
)

# %% points and vectors given in an affine frame


affine_values = [AffinePoint, CartesianPoint, AffineVector, CartesianVector]


@pytest.mark.parametrize("affine_value", affine_values)
def test_an_affine_point_or_vector_cannot_be_instantiated(affine_value):
    with pytest.raises(InterfaceInstantiationError):
        affine_value()


@pytest.mark.parametrize("affine_value", affine_values)
def test_an_affine_point_or_vector_is_a_coordinate_representation(affine_value):
    assert issubclass(affine_value, CoordinateRepresentation)


def test_a_cartesian_point_is_an_affine_point():
    assert issubclass(CartesianPoint, AffinePoint)


def test_a_cartesian_vector_is_an_affine_vector():
    assert issubclass(CartesianVector, AffineVector)


def test_a_point_is_not_a_vector():
    assert not issubclass(AffinePoint, AffineVector)


def test_an_affine_point_is_moved_by_an_affine_vector():
    assert AffinePoint.__parameters__ == (AffineFrameT, CoordinateT, AffineVectorT)
    assert AffineVectorT.__bound__ is AffineVector


def test_a_cartesian_point_is_moved_by_a_cartesian_vector_of_a_cartesian_frame():
    assert CartesianPoint.__parameters__ == (
        CartesianFrameT,
        CoordinateT,
        CartesianVectorT,
    )
    assert CartesianFrameT.__bound__ is CartesianFrame
    assert CartesianVectorT.__bound__ is CartesianVector


def test_an_affine_point_is_given_in_an_affine_frame():
    assert AffineFrameT.__bound__ is AffineFrame


def test_a_point_reports_the_kind_of_frame_it_is_given_in():
    assert (
        StoredScalablePlanePoint.get_type_of_generic_parameter(AffineFrameT)
        is ScalablePlaneFrame
    )


def test_a_point_reports_what_its_coordinates_are_stored_as():
    assert StoredScalablePlanePoint.get_type_of_generic_parameter(CoordinateT) is float


def test_a_point_reports_the_kind_of_vector_it_is_moved_by():
    assert (
        StoredScalablePlanePoint.get_type_of_generic_parameter(AffineVectorT)
        is StoredScalablePlaneVector
    )


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


# %% how points and vectors combine


def test_the_difference_of_two_points_is_the_vector_between_them():
    start = StoredScalablePlanePoint(1.0, 2.0, None)
    end = StoredScalablePlanePoint(4.0, 6.0, None)

    assert end - start == StoredScalablePlaneVector(3.0, 4.0, None)


def test_a_point_moved_by_the_difference_to_another_point_reaches_it():
    start = StoredScalablePlanePoint(1.0, 2.0, None)
    end = StoredScalablePlanePoint(4.0, 6.0, None)

    assert start + (end - start) == end


# %% straight lines given by a point and a direction


def test_an_affine_line_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        AffineLine()


def test_an_affine_line_runs_through_a_point_along_a_vector():
    assert AffineLine.__parameters__ == (AffinePointT, AffineVectorT)
    assert AffinePointT.__bound__ is AffinePoint


def test_a_lines_fields_are_narrowed_to_the_bound_types():
    line_types = {
        line_field.name: line_field.type
        for line_field in fields(StoredScalablePlaneLine)
    }

    assert line_types == {
        "point": StoredScalablePlanePoint,
        "direction": StoredScalablePlaneVector,
    }
