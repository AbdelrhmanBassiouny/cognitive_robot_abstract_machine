"""
Tests for :mod:`experiments.montessori.perception.scene_publishing`: the board a look
found is stood in the world the robot publishes, once, where the look found it, the
pieces a look found are stood there as the pieces they were seen as, and a scene
perceived again stands them afresh.
"""

from __future__ import annotations

import math

import pytest

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.recorded_setup import (
    TABLE_HEIGHT,
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import (
    PUBLISHED_PREFIX,
    BoardPublisher,
    PerceivedScene,
    PiecePublisher,
    look_for_board,
)
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import MontessoriShape, ShapeSortingBoard
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


# %% the pieces

MEASURED_CAPTURE = "scaled_pieces_in_a_row"
"""
A capture of the smaller set standing in a row on the bare table, with the board.
"""


@pytest.fixture
def look() -> RecordedFrame:
    """
    The capture, looked at afresh for every request, placed in the recorded setup's
    world.
    """
    return RecordedFrame(
        pipeline=perception_pipeline(world=recorded_world(), pieces=SMALLER_PIECES),
        frame=SceneCapture.load(MEASURED_CAPTURE).to_frame(),
    )


def test_the_pieces_a_look_put_on_the_table_are_stood_where_they_were_seen(
    look: RecordedFrame,
) -> None:
    scene = look.scene()
    on_the_table = [
        shape
        for shape in scene.shapes
        if shape.supporting_surface == look.pipeline.table.name
    ]
    live = look.pipeline.world
    publisher = PiecePublisher(world=live)

    stood = publisher.publish(scene, resting_on=look.pipeline.table.name)

    assert live.get_semantic_annotations_by_type(MontessoriShape) == stood
    assert [piece.shape_category for piece in stood] == [
        shape.category for shape in on_the_table
    ]
    for piece, shape in zip(stood, on_the_table):
        assert piece.name.prefix == PUBLISHED_PREFIX
        known = shape.hypothesis.piece_of(shape.category)
        stands_at = piece.root.global_transform.to_position().to_np()[:3]
        assert stands_at[:2] == pytest.approx(shape.pose.to_position().to_np()[:2])
        assert stands_at[2] == pytest.approx(shape.surface_height + known.height / 2)
        assert float(
            piece.root.global_transform.to_rotation_matrix().to_rpy()[2]
        ) == pytest.approx(shape.yaw)
        bounds = piece.root.collision.combined_mesh.bounds
        assert float(bounds[1][2] - bounds[0][2]) == pytest.approx(known.height)
        assert piece.root.collision[0].color == known.color


def test_a_piece_on_another_surface_is_not_stood(look: RecordedFrame) -> None:
    scene = look.scene()
    live = look.pipeline.world

    stood = PiecePublisher(world=live).publish(scene, resting_on=look.pipeline.lid.name)

    assert stood == []
    assert live.get_semantic_annotations_by_type(MontessoriShape) == []


def test_two_looks_stand_pieces_under_different_names(look: RecordedFrame) -> None:
    scene = look.scene()
    publisher = PiecePublisher(world=look.pipeline.world)

    first = publisher.publish(scene, resting_on=look.pipeline.table.name)
    second = publisher.publish(scene, resting_on=look.pipeline.table.name)

    assert len({piece.name for piece in first + second}) == len(first) + len(second)
    assert publisher.published == first + second


def test_taking_the_pieces_down_leaves_none_of_them_in_the_world(
    look: RecordedFrame,
) -> None:
    scene = look.scene()
    live = look.pipeline.world
    publisher = PiecePublisher(world=live)
    stood = publisher.publish(scene, resting_on=look.pipeline.table.name)
    assert stood

    publisher.take_down()

    assert publisher.published == []
    assert live.get_semantic_annotations_by_type(MontessoriShape) == []
    assert not {piece.root for piece in stood} & set(live.bodies)


def test_pieces_stood_after_a_take_down_keep_their_own_names(
    look: RecordedFrame,
) -> None:
    """
    A name is never given twice, so nothing that kept a piece of the first look can
    mistake one of the second for it.
    """
    scene = look.scene()
    publisher = PiecePublisher(world=look.pipeline.world)
    first = publisher.publish(scene, resting_on=look.pipeline.table.name)

    publisher.take_down()
    second = publisher.publish(scene, resting_on=look.pipeline.table.name)

    assert not {piece.name for piece in first} & {piece.name for piece in second}


# %% the scene a look stands


def test_a_perceived_scene_holds_the_board_and_the_pieces_the_look_found(
    look: RecordedFrame,
) -> None:
    live = look.pipeline.world
    scene = PerceivedScene(world=live, look=look, described_board=lab_board())

    scene.perceive()

    assert ShapeSortingBoard.held_by(live) is scene.board
    assert live.get_semantic_annotations_by_type(MontessoriShape) == scene.pieces
    assert sorted(piece.shape_category for piece in scene.pieces) == sorted(
        shape.category
        for shape in look.scene().shapes
        if shape.supporting_surface == look.pipeline.table.name
    )
    assert scene.piece_set is SMALLER_PIECES
    assert scene.table_height == pytest.approx(TABLE_HEIGHT)


def test_a_scene_perceived_again_stands_the_pieces_afresh_and_keeps_the_board(
    look: RecordedFrame,
) -> None:
    """
    The pieces of the first look are gone from the world, the second look's stand in
    their place, and the board found once is the board the world holds.
    """
    live = look.pipeline.world
    scene = PerceivedScene(world=live, look=look, described_board=lab_board())
    scene.perceive()
    board, first = scene.board, list(scene.pieces)

    scene.perceive()

    assert scene.board is board
    assert ShapeSortingBoard.held_by(live) is board
    assert live.get_semantic_annotations_by_type(MontessoriShape) == scene.pieces
    assert len(scene.pieces) == len(first)
    assert not {piece.root for piece in first} & set(live.bodies)


# %% looking for the board


def test_one_look_finds_the_described_board_standing_at_the_lids_height(
    look: RecordedFrame,
) -> None:
    described = DescribedBoard.of_layout(
        BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
    )

    found = look_for_board(look, described)

    assert found is not None
    assert float(BoardPublisher.lid_pose_of(found).z) == pytest.approx(
        TABLE_HEIGHT + float(BOARD_SCALE.z)
    )
