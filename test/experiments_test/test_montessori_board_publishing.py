"""
Tests for :mod:`experiments.montessori.perception.board_publishing`: the board a look
found is stood in the world the robot publishes, once, where the look found it.
"""

from __future__ import annotations

import math

import pytest

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.board_publishing import BoardPublisher
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import ShapeSortingBoard
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

LID_HEIGHT = 0.96
"""
An arbitrary height the found board's lid stands at.
"""


def _world_with_root(name: str) -> World:
    """
    :param name: What the world's root body is called.
    :return: A world holding only its root body.
    """
    world = World()
    with world.modify_world():
        world.add_kinematic_structure_entity(Body(name=PrefixedName(name, "test")))
    return world


def _found_board(described: DescribedBoard) -> ShapeSortingBoard:
    """
    :param described: The board a look was asked for.
    :return: That board, standing in a world of the look's own where it was found.
    """
    return described.stand_in(
        _world_with_root("looked_in"),
        Pose.from_xyz_rpy(0.8, 0.1, LID_HEIGHT, yaw=math.radians(30.0)),
        prefix="looked",
    )


def test_the_found_board_is_stood_in_the_published_world_once_where_it_was_found():
    described = DescribedBoard.of_layout(
        BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
    )
    found = _found_board(described)
    live = _world_with_root("live")
    publisher = BoardPublisher(world=live)

    first = publisher.publish(described, found)
    second = publisher.publish(described, found)

    assert live.get_semantic_annotations_by_type(ShapeSortingBoard) == [first]
    assert second is first
    stands_at = first.root.global_transform.to_position().to_np()
    found_at = found.root.global_transform.to_position().to_np()
    assert (float(stands_at[0]), float(stands_at[1])) == pytest.approx(
        (float(found_at[0]), float(found_at[1]))
    )
    assert WorkspaceSurface.of(first, live.root).height == pytest.approx(LID_HEIGHT)
