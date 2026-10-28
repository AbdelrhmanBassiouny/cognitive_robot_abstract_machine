from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrspatial.coordinate_system import CoordinateRepresentation, CoordinateSystemT
from krrspatial.planar_point import CoordinateT, PlanarPoint

from .dataset.spaces import ScalablePlaneCoordinateSystem, StoredScalablePlanePoint

# %% points given in a coordinate system


def test_a_planar_point_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        PlanarPoint()


def test_a_planar_point_is_a_coordinate_representation():
    assert issubclass(PlanarPoint, CoordinateRepresentation)


def test_a_point_reports_the_kind_of_coordinate_system_it_is_given_in():
    assert (
        StoredScalablePlanePoint.get_type_of_generic_parameter(CoordinateSystemT)
        is ScalablePlaneCoordinateSystem
    )


def test_a_point_reports_what_its_coordinates_are_stored_as():
    assert StoredScalablePlanePoint.get_type_of_generic_parameter(CoordinateT) is float


def test_a_points_coordinate_fields_are_narrowed_to_the_bound_type():
    coordinate_types = {
        point_field.name: point_field.type
        for point_field in fields(StoredScalablePlanePoint)
        if point_field.name in ("x", "y")
    }

    assert coordinate_types == {"x": float, "y": float}
