from __future__ import annotations

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrood_spatial_math.cartesian_frame_3d import (
    CartesianFrame3D,
    CartesianFrame3DReference,
)
from krrood_spatial_math.coordinate_system import CartesianFrame, SpaceT
from krrood_spatial_math.exceptions import MissingCartesianFrame3DResolver
from krrood_spatial_math.space import EuclideanSpace

from .dataset.frames import KnownFrames

# %% the frame interface


def test_a_three_dimensional_cartesian_frame_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        CartesianFrame3D()


def test_a_three_dimensional_cartesian_frame_is_a_cartesian_frame():
    assert issubclass(CartesianFrame3D, CartesianFrame)


def test_a_three_dimensional_cartesian_frame_charts_euclidean_space():
    assert CartesianFrame3D.get_type_of_generic_parameter(SpaceT) is EuclideanSpace


def test_a_three_dimensional_cartesian_frame_declares_expressing_values_in_it():
    assert CartesianFrame3D.__abstractmethods__ == {CartesianFrame3D.express.__name__}


# %% referring to a frame in a serialized value


def test_a_reference_resolves_to_the_readers_frame(table_frame):
    reference = CartesianFrame3DReference("reference_frame")
    data = {}
    reference.write(data, table_frame)
    known_frames = KnownFrames()
    known_frames.add(table_frame.id, table_frame)

    assert reference.resolve(data, **known_frames.create_kwargs()) is table_frame


def test_a_reference_cannot_be_resolved_without_a_resolver(table_frame):
    reference = CartesianFrame3DReference("reference_frame")
    data = {}
    reference.write(data, table_frame)

    with pytest.raises(MissingCartesianFrame3DResolver):
        reference.resolve(data)
