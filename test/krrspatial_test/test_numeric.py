from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrspatial.exceptions import DifferentReferenceFrames
from krrspatial.numeric import (
    FloatPoint2,
    FloatVector2,
    IntegerPoint2,
    IntegerVector2,
)
from krrspatial.spatial_types import Point2, Vector2

from .dataset.frames import NamedFrame

# %% the interfaces


@pytest.mark.parametrize("interface", [Point2, Vector2])
def test_the_point_and_vector_interfaces_cannot_be_instantiated(interface: type):
    with pytest.raises(InterfaceInstantiationError):
        interface()


@pytest.mark.parametrize(
    "spatial_object, interface",
    [
        (FloatPoint2(1.0, 2.0), Point2),
        (IntegerPoint2(1, 2), Point2),
        (FloatVector2(1.0, 2.0), Vector2),
        (IntegerVector2(1, 2), Vector2),
    ],
)
def test_numeric_types_implement_their_interface(
    spatial_object: object, interface: type
):
    assert isinstance(spatial_object, interface)


@pytest.mark.parametrize(
    "spatial_type, coordinate_type",
    [
        (FloatPoint2, float),
        (IntegerPoint2, int),
        (FloatVector2, float),
        (IntegerVector2, int),
    ],
)
def test_binding_the_coordinate_type_narrows_both_coordinates(
    spatial_type: type, coordinate_type: type
):
    x_field, y_field, _ = fields(spatial_type)
    assert (x_field.type, y_field.type) == (coordinate_type, coordinate_type)


# %% points and vectors combined


def test_the_difference_of_two_points_is_a_vector_of_their_coordinate_type(
    table_frame: NamedFrame,
):
    start = IntegerPoint2(1, 2, table_frame)
    end = IntegerPoint2(4, 6, table_frame)
    assert end - start == IntegerVector2(3, 4, table_frame)


def test_a_point_moved_by_a_vector_is_a_point_of_the_same_type(
    table_frame: NamedFrame,
):
    point = FloatPoint2(1.0, 2.0, table_frame)
    offset = FloatVector2(0.5, -1.0, table_frame)
    assert point + offset == FloatPoint2(1.5, 1.0, table_frame)


def test_a_point_moved_back_by_a_vector_is_a_point_of_the_same_type(
    table_frame: NamedFrame,
):
    point = FloatPoint2(1.0, 2.0, table_frame)
    offset = FloatVector2(0.5, -1.0, table_frame)
    assert point - offset == FloatPoint2(0.5, 3.0, table_frame)


def test_vectors_add_subtract_and_negate_per_axis(table_frame: NamedFrame):
    first = IntegerVector2(1, 2, table_frame)
    second = IntegerVector2(3, 5, table_frame)
    assert (first + second, second - first, -first) == (
        IntegerVector2(4, 7, table_frame),
        IntegerVector2(2, 3, table_frame),
        IntegerVector2(-1, -2, table_frame),
    )


def test_the_norm_of_a_float_vector_is_its_euclidean_length():
    assert FloatVector2(3.0, 4.0).norm() == 5.0


@pytest.mark.parametrize(
    "first, second",
    [
        (FloatPoint2(0.0, 0.0), FloatVector2(1.0, 1.0)),
        (FloatPoint2(0.0, 0.0), FloatPoint2(1.0, 1.0)),
        (FloatVector2(0.0, 0.0), FloatVector2(1.0, 1.0)),
    ],
)
def test_objects_in_different_frames_are_not_combined(
    first: FloatPoint2 | FloatVector2,
    second: FloatPoint2 | FloatVector2,
    table_frame: NamedFrame,
    camera_frame: NamedFrame,
):
    first.reference_frame = table_frame
    second.reference_frame = camera_frame
    with pytest.raises(DifferentReferenceFrames):
        first - second


# %% whole-number positions


def test_the_nearest_integer_point_rounds_each_coordinate_and_keeps_the_frame(
    table_frame: NamedFrame,
):
    point = FloatPoint2(2.6, 3.2, table_frame)
    assert IntegerPoint2.nearest(point) == IntegerPoint2(3, 3, table_frame)
