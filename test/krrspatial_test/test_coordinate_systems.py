from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrspatial.coordinate_system import (
    CoordinateChange,
    CoordinateSystem,
    CoordinateSystemT,
    ImageCoordinateSystem,
    SpaceT,
)
from krrspatial.reference_frame import ReferenceFrame
from krrspatial.space import EuclideanSpace, ImagePlane, Space

from .dataset.frames import NamedFrame
from .dataset.spaces import NamedImageCoordinateSystem, StoredImageCoordinateChange

# %% spaces


@pytest.mark.parametrize("space_kind", [Space, EuclideanSpace, ImagePlane])
def test_a_space_cannot_be_instantiated(space_kind):
    with pytest.raises(InterfaceInstantiationError):
        space_kind()


@pytest.mark.parametrize("space_kind", [EuclideanSpace, ImagePlane])
def test_physical_space_and_image_planes_are_spaces(space_kind):
    assert issubclass(space_kind, Space)


def test_an_image_plane_is_not_physical_space():
    assert not issubclass(ImagePlane, EuclideanSpace)


# %% coordinate systems on spaces


@pytest.mark.parametrize(
    "coordinate_system_kind", [CoordinateSystem, ImageCoordinateSystem]
)
def test_a_coordinate_system_interface_cannot_be_instantiated(coordinate_system_kind):
    with pytest.raises(InterfaceInstantiationError):
        coordinate_system_kind()


@pytest.mark.parametrize(
    "coordinate_system_kind, space_kind",
    [(ReferenceFrame, EuclideanSpace), (ImageCoordinateSystem, ImagePlane)],
)
def test_a_coordinate_system_reports_the_kind_of_space_it_charts(
    coordinate_system_kind, space_kind
):
    assert coordinate_system_kind.get_type_of_generic_parameter(SpaceT) is space_kind


def test_an_image_coordinate_system_is_not_a_reference_frame():
    assert not isinstance(NamedImageCoordinateSystem("camera image"), ReferenceFrame)


def test_a_reference_frame_is_not_an_image_coordinate_system(table_frame: NamedFrame):
    assert not isinstance(table_frame, ImageCoordinateSystem)


# %% changing coordinates within one space


def test_a_coordinate_change_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        CoordinateChange()


def test_a_coordinate_change_reports_the_kind_of_coordinate_system_it_changes():
    assert (
        StoredImageCoordinateChange.get_type_of_generic_parameter(CoordinateSystemT)
        is ImageCoordinateSystem
    )


def test_a_coordinate_changes_coordinate_systems_are_narrowed_to_the_bound_kind():
    coordinate_system_types = {
        change_field.name: change_field.type
        for change_field in fields(StoredImageCoordinateChange)
    }

    assert coordinate_system_types == {
        "source_coordinate_system": ImageCoordinateSystem | None,
        "target_coordinate_system": ImageCoordinateSystem | None,
    }
