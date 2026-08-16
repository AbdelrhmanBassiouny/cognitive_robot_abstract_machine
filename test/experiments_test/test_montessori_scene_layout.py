"""
Tests for reading the scene's fixed layout — board, holes, insertion goals — out of a
built world, and for naming the world entities the viewer should show for it.
"""

from __future__ import annotations

import pytest
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Point3
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from cramera.body_geometry import NumericPose
from experiments.montessori.scene_layout import SceneLayout, scene_entities_of
from experiments.montessori.semantics import MontessoriShapeCategory

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
        cube = cube_at(world, Point3(0.0, 0.0, 0.08))
        sphere_at(world, Point3(0.3, 0.3, 0.08))
    return world, board, hole, cube


# %% what the layout reads out of the world
class TestSceneLayoutOfWorld:
    def test_each_hole_is_recorded_with_its_category_and_position(self, scene):
        world, board, hole, cube = scene

        layout = SceneLayout.of_world(world)

        [record] = layout.holes
        assert record.name == SHAPE_KEY
        assert record.shape_category == str(MontessoriShapeCategory.CUBE)
        assert record.pose.position == (
            HOLE_POSITION.x,
            HOLE_POSITION.y,
            HOLE_POSITION.z,
        )

    def test_the_board_is_recorded_under_its_published_key(self, scene):
        world, board, hole, cube = scene

        layout = SceneLayout.of_world(world)

        [record] = layout.boards
        assert record.name == "board"

    def test_a_shape_with_a_matching_hole_gets_a_goal_at_its_insertion_target(
        self, scene
    ):
        world, board, hole, cube = scene

        layout = SceneLayout.of_world(world)

        [goal] = layout.goals
        assert goal.shape == SHAPE_OBJECT_NAME
        assert goal.hole == SHAPE_KEY
        assert goal.pose == NumericPose.of_pose(board.insertion_target_for(cube, world))

    def test_a_shape_with_no_matching_hole_gets_no_goal(self, scene):
        """
        The sphere has no hole shaped to accept it, so the goals name every other shape
        but never it.
        """
        world, board, hole, cube = scene

        layout = SceneLayout.of_world(world)

        assert [goal.shape for goal in layout.goals] == [SHAPE_OBJECT_NAME]

    def test_a_goal_answer_row_lights_up_the_goals_hole(self, scene):
        world, board, hole, cube = scene

        [goal] = SceneLayout.of_world(world).goals

        assert goal.related_highlight_ids() == [SHAPE_KEY]


# %% what the viewer is asked to show
class TestSceneEntitiesOfWorld:
    def test_the_board_and_its_holes_are_the_published_scene_entities(self, scene):
        world, board, hole, cube = scene

        assert scene_entities_of(world) == [board.root, hole.root]
