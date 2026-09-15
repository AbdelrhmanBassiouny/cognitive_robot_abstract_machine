"""
Tests for declaring contact parameters on shapes.
"""

from __future__ import annotations

from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)
from semantic_digital_twin.world_description.contact import (
    ContactFriction,
    ContactImpedance,
    ContactParameters,
    ContactStiffness,
)
from semantic_digital_twin.world_description.geometry import Box, Scale
from semantic_digital_twin.world_description.shape_collection import ShapeCollection
from semantic_digital_twin.world_description.world_entity import Body

# %% list forms


def test_contact_parameters_round_trip_through_their_list_forms():
    friction = ContactFriction(sliding=0.4, torsional=0.05, rolling=0.001)
    stiffness = ContactStiffness(time_constant=0.008, damping_ratio=0.9)
    impedance = ContactImpedance(
        minimum=0.96, maximum=0.99, width=0.002, midpoint=0.4, power=3.0
    )

    assert ContactFriction(*friction.to_list()) == friction
    assert ContactStiffness(*stiffness.to_list()) == stiffness
    assert ContactImpedance(*impedance.to_list()) == impedance
    assert friction.to_list() == [0.4, 0.05, 0.001]
    assert stiffness.to_list() == [0.008, 0.9]
    assert impedance.to_list() == [0.96, 0.99, 0.002, 0.4, 3.0]


# %% applying to bodies


def test_contact_parameters_reach_every_collision_geometry():
    body = Body(name=PrefixedName("box"))
    body.collision = ShapeCollection(
        [
            Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1)),
            Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1)),
        ],
        reference_frame=body,
    )
    contact = ContactParameters.create_for_grasped_object(sliding_friction=0.4)

    contact.apply_to([body])

    for shape in body.collision:
        assert shape.friction == ContactFriction(
            sliding=0.4, torsional=0.05, rolling=0.001
        )
        assert shape.contact_stiffness == contact.stiffness
        assert shape.contact_impedance == contact.impedance


def test_a_surface_leaves_the_geometrys_own_stiffness_and_impedance():
    body = Body(name=PrefixedName("table"))
    shape = Box(origin=HomogeneousTransformationMatrix(), scale=Scale(1, 1, 1))
    body.collision = ShapeCollection([shape], reference_frame=body)
    own_stiffness = ContactStiffness(time_constant=0.05)
    shape.contact_stiffness = own_stiffness

    ContactParameters.create_for_surface(sliding_friction=0.2).apply_to([body])

    assert shape.friction == ContactFriction(sliding=0.2)
    assert shape.contact_stiffness == own_stiffness
    assert shape.contact_impedance is None
