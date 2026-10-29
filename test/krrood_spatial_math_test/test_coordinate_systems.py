from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.coordinate_system import (
    AffineCoordinateChange,
    CoordinateChange,
    CoordinateRepresentation,
    CoordinateSystem,
    CoordinateSystemT,
    RigidCoordinateChange,
    SpaceT,
)
from krrood_spatial_math.reference_frame import ReferenceFrame
from krrood_spatial_math.space import EuclideanSpace, Space

from .dataset.spaces import (
    ScalablePlaneCoordinateSystem,
    StoredFrameChange,
    StoredScalingChange,
)

# %% spaces


@pytest.mark.parametrize("space_kind", [Space, EuclideanSpace])
def test_a_space_cannot_be_instantiated(space_kind):
    with pytest.raises(InterfaceInstantiationError):
        space_kind()


def test_physical_space_is_a_space():
    assert issubclass(EuclideanSpace, Space)


# %% coordinate systems on spaces


def test_a_coordinate_system_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        CoordinateSystem()


def test_a_reference_frame_charts_physical_space():
    assert ReferenceFrame.get_type_of_generic_parameter(SpaceT) is EuclideanSpace


# %% values given in a coordinate system


def test_a_coordinate_representation_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        CoordinateRepresentation()


# %% changing coordinates within one space


@pytest.mark.parametrize(
    "change_kind",
    [CoordinateChange, AffineCoordinateChange, RigidCoordinateChange],
)
def test_a_coordinate_change_interface_cannot_be_instantiated(change_kind):
    with pytest.raises(InterfaceInstantiationError):
        change_kind()


def test_a_coordinate_change_declares_inverting_and_composing():
    assert CoordinateChange.__abstractmethods__ == {
        CoordinateChange.inverse.__name__,
        CoordinateChange.__matmul__.__name__,
    }


def test_a_rigid_change_is_an_affine_change():
    assert issubclass(RigidCoordinateChange, AffineCoordinateChange)


def test_an_affine_change_is_a_coordinate_change():
    assert issubclass(AffineCoordinateChange, CoordinateChange)


def test_an_affine_change_need_not_be_rigid():
    assert issubclass(StoredScalingChange, AffineCoordinateChange)
    assert not issubclass(StoredScalingChange, RigidCoordinateChange)


def test_a_rigid_change_reports_the_kind_of_coordinate_system_it_changes():
    assert (
        StoredFrameChange.get_type_of_generic_parameter(CoordinateSystemT)
        is ReferenceFrame
    )


def test_a_coordinate_change_reports_the_kind_of_coordinate_system_it_changes():
    assert (
        StoredScalingChange.get_type_of_generic_parameter(CoordinateSystemT)
        is ScalablePlaneCoordinateSystem
    )


def test_a_coordinate_changes_coordinate_systems_are_narrowed_to_the_bound_kind():
    coordinate_system_types = {
        change_field.name: change_field.type
        for change_field in fields(StoredScalingChange)
    }

    assert coordinate_system_types == {
        "source_coordinate_system": ScalablePlaneCoordinateSystem | None,
        "target_coordinate_system": ScalablePlaneCoordinateSystem | None,
    }
