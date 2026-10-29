from __future__ import annotations

from dataclasses import fields

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.cartesian_frame_3d import CartesianFrame3D
from krrood_spatial_math.coordinate_system import (
    AffineCoordinateChange,
    AffineFrame,
    AffineFrameT,
    CartesianFrame,
    CartesianFrameT,
    CoordinateChange,
    CoordinateRepresentation,
    CoordinateSystem,
    RigidCoordinateChange,
    SpaceT,
)
from krrood_spatial_math.space import EuclideanSpace, EuclideanSpace3D, Space

from .dataset.spaces import (
    ScalablePlane,
    ScalablePlaneFrame,
    StoredFrameChange,
    StoredScalingChange,
)

# %% spaces


@pytest.mark.parametrize("space_kind", [Space, EuclideanSpace, EuclideanSpace3D])
def test_a_space_cannot_be_instantiated(space_kind):
    with pytest.raises(InterfaceInstantiationError):
        space_kind()


def test_euclidean_space_is_a_space():
    assert issubclass(EuclideanSpace, Space)


def test_three_dimensional_euclidean_space_is_a_euclidean_space():
    assert issubclass(EuclideanSpace3D, EuclideanSpace)


# %% coordinate systems on spaces


@pytest.mark.parametrize(
    "coordinate_system_kind", [CoordinateSystem, AffineFrame, CartesianFrame]
)
def test_a_coordinate_system_interface_cannot_be_instantiated(coordinate_system_kind):
    with pytest.raises(InterfaceInstantiationError):
        coordinate_system_kind()


def test_an_affine_frame_is_a_coordinate_system():
    assert issubclass(AffineFrame, CoordinateSystem)


def test_a_cartesian_frame_is_an_affine_frame():
    assert issubclass(CartesianFrame, AffineFrame)


def test_an_affine_frame_need_not_be_cartesian():
    assert issubclass(ScalablePlaneFrame, AffineFrame)
    assert not issubclass(ScalablePlaneFrame, CartesianFrame)


def test_an_affine_frame_reports_the_space_it_charts():
    assert ScalablePlaneFrame.get_type_of_generic_parameter(SpaceT) is ScalablePlane


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


def test_an_affine_change_changes_between_affine_frames():
    assert AffineFrameT.__bound__ is AffineFrame


def test_a_rigid_change_changes_between_cartesian_frames():
    assert CartesianFrameT.__bound__ is CartesianFrame


def test_a_rigid_change_reports_the_kind_of_frame_it_changes():
    assert (
        StoredFrameChange.get_type_of_generic_parameter(CartesianFrameT)
        is CartesianFrame3D
    )


def test_an_affine_change_reports_the_kind_of_frame_it_changes():
    assert (
        StoredScalingChange.get_type_of_generic_parameter(AffineFrameT)
        is ScalablePlaneFrame
    )


def test_a_coordinate_changes_frames_are_narrowed_to_the_bound_kind():
    frame_types = {
        change_field.name: change_field.type
        for change_field in fields(StoredScalingChange)
    }

    assert frame_types == {
        "source_coordinate_system": ScalablePlaneFrame | None,
        "target_coordinate_system": ScalablePlaneFrame | None,
    }
