from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrspatial.planar_point import CoordinateT, PlanarPoint, SpaceT
from krrspatial.reference_frame import ReferenceFrame
from krrspatial.space import ImageSpace, Space

from .dataset.frames import NamedFrame
from .dataset.spaces import NamedImage, StoredImagePoint

# %% the spaces points are given in


def test_a_space_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        Space()


@pytest.mark.parametrize("space_kind", [ReferenceFrame, ImageSpace])
def test_frames_and_images_are_spaces(space_kind):
    assert issubclass(space_kind, Space)


def test_an_image_is_not_a_reference_frame():
    assert not isinstance(NamedImage("camera image"), ReferenceFrame)


def test_a_reference_frame_is_not_an_image(table_frame: NamedFrame):
    assert not isinstance(table_frame, ImageSpace)


# %% points given in a space


def test_a_planar_point_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        PlanarPoint()


def test_a_point_reports_the_kind_of_space_it_is_given_in():
    assert StoredImagePoint.get_type_of_generic_parameter(SpaceT) is ImageSpace


def test_a_point_reports_what_its_coordinates_are_stored_as():
    assert StoredImagePoint.get_type_of_generic_parameter(CoordinateT) is float


def test_a_points_coordinate_fields_are_narrowed_to_the_bound_type():
    coordinate_types = {
        point_field.name: point_field.type
        for point_field in fields(StoredImagePoint)
        if point_field.name in ("x", "y")
    }

    assert coordinate_types == {"x": float, "y": float}
