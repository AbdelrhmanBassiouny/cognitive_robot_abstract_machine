"""
Tests for making an event happen: a motion event reproduced in a world puts the object
it is about where the event says it ended up, whichever connection the object hangs
from.
"""

from __future__ import annotations

import numpy as np
import pytest

from segmind.datastructures.events import (
    ReproducibleEvent,
    RotationEvent,
    StopTranslationEvent,
    SupportEvent,
    TranslationEvent,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.connections import (
    Connection6DoF,
    FixedConnection,
)
from semantic_digital_twin.world_description.world_entity import Body

# %% the world the events are reproduced in

SETUP = "event_reproduction_test"
"""
The prefix every entity of these tests is named under.
"""


@pytest.fixture
def world() -> World:
    """
    A root with a piece welded to it and a piece free to move on it.
    """
    world = World()
    root = Body(name=PrefixedName("root", SETUP))
    welded = Body(name=PrefixedName("welded_piece", SETUP))
    loose = Body(name=PrefixedName("loose_piece", SETUP))
    with world.modify_world():
        for body in (root, welded, loose):
            world.add_kinematic_structure_entity(body)
        world.add_connection(FixedConnection(parent=root, child=welded))
        world.add_connection(
            Connection6DoF.create_with_dofs(parent=root, child=loose, world=world)
        )
    return world


def _piece(world: World, name: str) -> Body:
    """
    :return: One of the fixture's pieces, by the name it was given.
    """
    return world.get_body_by_name(PrefixedName(name, SETUP))


def _ended_up_at(world: World, x: float, y: float) -> Pose:
    """
    :return: A pose on the table in the world frame, for an event to end at.
    """
    return Pose.from_xyz_rpy(x, y, 0.0, reference_frame=world.root)


# %% which events can be made to happen


@pytest.mark.parametrize(
    "event_type", [TranslationEvent, RotationEvent, StopTranslationEvent]
)
def test_a_motion_event_can_be_reproduced(event_type, world):
    event = event_type(tracked_object=_piece(world, "loose_piece"))

    assert isinstance(event, ReproducibleEvent)


def test_an_event_that_only_says_what_holds_cannot_be_reproduced(world):
    event = SupportEvent(
        tracked_object=_piece(world, "loose_piece"), with_object=world.root
    )

    assert not isinstance(event, ReproducibleEvent)


# %% what reproducing a motion does


@pytest.mark.parametrize("piece_name", ["loose_piece", "welded_piece"])
def test_a_reproduced_translation_puts_the_object_where_the_event_ended(
    piece_name, world
):
    piece = _piece(world, piece_name)
    ended_at = _ended_up_at(world, 0.3, -0.2)
    event = TranslationEvent(
        tracked_object=piece, start_pose=piece.global_pose, current_pose=ended_at
    )

    event.reproduce(world)

    assert np.allclose(
        piece.global_transform.to_np(), ended_at.to_homogeneous_matrix().to_np()
    )


def test_reproducing_a_translation_leaves_every_other_object_where_it_was(world):
    loose, welded = _piece(world, "loose_piece"), _piece(world, "welded_piece")
    welded_stood_at = welded.global_transform.to_np()
    event = TranslationEvent(
        tracked_object=loose,
        start_pose=loose.global_pose,
        current_pose=_ended_up_at(world, 0.3, -0.2),
    )

    event.reproduce(world)

    assert np.allclose(welded.global_transform.to_np(), welded_stood_at)
