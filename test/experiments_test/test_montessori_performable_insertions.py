"""
Tests for reading the insertions a built Montessori scene makes possible, and for how
each of them reaches the viewer's perform button.
"""

from __future__ import annotations

import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from cramera.loose_objects import LooseObjects
from experiments.montessori.performable_insertions import (
    InsertableShapeMissing,
    PerformableInsertion,
)

from .dataset.montessori_board import (
    SHAPE_KEY,
    SHAPE_OBJECT_NAME,
    board_with_one_hole,
    cube_at,
    sphere_at,
)

HOLE_POSITION = Point3(0.2, -0.1, 0.05)
"""
Where the scene below places its one hole, in the world root frame.
"""


@pytest.fixture()
def scene():
    """
    A board with one hole, a cube that fits it, and a sphere that fits nothing.
    """
    world = World()
    with world.modify_world():
        world.add_body(Body(name=PrefixedName("root")))
        board, hole = board_with_one_hole(world, HOLE_POSITION)
        cube_at(world, Point3(0.0, 0.0, 0.08))
        sphere_at(world, Point3(0.3, 0.3, 0.08))
    return world, hole


class TestReadingTheInsertionsOffTheWorld:
    def test_a_shape_with_a_matching_hole_can_be_inserted(self, scene):
        world, hole = scene

        [insertion] = PerformableInsertion.of_world(world)

        assert insertion.shape == SHAPE_OBJECT_NAME
        assert insertion.shape_key == SHAPE_KEY
        assert insertion.hole == LooseObjects.key_of(hole.root)

    def test_a_shape_no_hole_fits_cannot_be_inserted(self, scene):
        """
        The sphere passes through nothing on this board, so nothing offers to insert it.
        """
        world, _ = scene

        named = [insertion.shape for insertion in PerformableInsertion.of_world(world)]

        assert named == [SHAPE_OBJECT_NAME]

    def test_an_empty_world_offers_no_insertion(self):
        assert PerformableInsertion.of_world(World()) == []


class TestWhatThePerformButtonReads:
    def test_the_insertion_is_named_after_the_shape_it_picks_up(self, scene):
        world, _ = scene

        [insertion] = PerformableInsertion.of_world(world)

        assert insertion.name == "insert %s" % SHAPE_OBJECT_NAME
        assert insertion.performable_action().name == insertion.name

    def test_the_button_says_which_shape_goes_through_which_hole(self, scene):
        world, hole = scene

        [insertion] = PerformableInsertion.of_world(world)

        assert insertion.performable_action().description == (
            "insert the %s through the %s"
            % (SHAPE_OBJECT_NAME, LooseObjects.key_of(hole.root).replace("_", " "))
        )


class TestFindingThePieceToPickUp:
    def test_the_insertion_finds_the_shape_it_was_read_from(self, scene):
        world, _ = scene

        [insertion] = PerformableInsertion.of_world(world)

        assert insertion.shape_in(world).shape_key == SHAPE_KEY

    def test_a_world_without_that_shape_is_reported_rather_than_searched_past(
        self, scene
    ):
        world, _ = scene

        [insertion] = PerformableInsertion.of_world(world)

        with pytest.raises(InsertableShapeMissing):
            insertion.shape_in(World())
