"""
Tests for looking up the one simulator property of a type an entity carries.
"""

from __future__ import annotations

import pytest

from semantic_digital_twin.adapters.multi_sim import MujocoBody, MujocoGeom
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.exceptions import DuplicateSimulatorPropertyError
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.world_entity import Body


@pytest.fixture
def body() -> Body:
    return Body(name=PrefixedName("body"))


def test_no_property_of_a_type_is_none(body):
    assert body.simulator_property(MujocoBody) is None


def test_the_attached_property_is_found(body):
    attached = MujocoBody(motion_capture=True)
    body.simulator_additional_properties.append(attached)

    assert body.simulator_property(MujocoBody) is attached


def test_a_property_of_another_type_is_ignored(body):
    body.simulator_additional_properties.append(MujocoGeom())

    assert body.simulator_property(MujocoBody) is None


def test_two_properties_of_one_type_raise(body):
    body.simulator_additional_properties.append(MujocoBody())
    body.simulator_additional_properties.append(MujocoBody())

    with pytest.raises(DuplicateSimulatorPropertyError) as raised:
        body.simulator_property(MujocoBody)
    assert raised.value.property_type is MujocoBody
    assert raised.value.count == 2


def test_default_is_attached_once_and_then_reused():
    shape = Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1))

    created = shape.simulator_property_or_default(MujocoGeom)
    reused = shape.simulator_property_or_default(MujocoGeom)

    assert reused is created
    assert shape.simulator_additional_properties == [created]
