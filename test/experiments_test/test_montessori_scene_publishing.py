"""
Tests for :mod:`experiments.montessori.perception.scene_publishing`: the board a look
found is stood in the world the robot publishes where the look found it, the pieces a
look found are stood there as the pieces they were seen as, and a scene perceived again
holds the same board and the same pieces where the camera finds them now.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import pytest
from typing_extensions import List

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
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.pieces import SMALLER_PIECES
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
    ShapeSortingHole,
)
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.adapters.ros.messages import WorldModelSnapshot
from semantic_digital_twin.adapters.world_entity_kwargs_tracker import (
    WorldEntityWithIDKwargsTracker,
)
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
    Vector3,
)
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

from .dataset.montessori_capture_truths import CAPTURE_TRUTHS
from .test_montessori_occupancy import piece_at

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


# %% the board an earlier run left in the published world


def _as_the_robot_publishes_it(world: World) -> World:
    """
    :param world: A world some process holds.
    :return: That world as another process fetches it from the robot: rebuilt from the
        JSON of its modification history, the way the world service serves it.
    """
    snapshot = WorldModelSnapshot(
        modifications=list(world.get_world_model_manager().model_modification_blocks),
        ids=list(world.state.keys()),
        states=list(world.state.positions),
    )
    fetched = World()
    WorldModelSnapshot.apply_to_json_snapshot_to_world(
        fetched,
        json.loads(json.dumps(snapshot.to_json())),
        **WorldEntityWithIDKwargsTracker.from_world(fetched).create_kwargs(),
    )
    return fetched


def test_the_holes_of_a_board_fetched_from_the_robot_keep_their_shape_categories():
    """
    A run reuses the board an earlier run stood in the world the robot publishes, which
    reaches it through the JSON of that world; each hole's category must come back as
    the category itself, since equality to its name is not enough for what records it.
    """
    described = DescribedBoard.of_layout(
        BoardHoleLayout.of_board_mesh(), height=float(BOARD_SCALE.z)
    )
    live = _world_with_root("live")
    stood = BoardPublisher(world=live).publish(described, _found_board(described))

    fetched = _as_the_robot_publishes_it(live)

    held = ShapeSortingBoard.held_by(fetched)
    assert held is not None
    assert [hole.name for hole in held.apertures] == [
        hole.name for hole in stood.apertures
    ]
    for hole, stood_hole in zip(held.apertures, stood.apertures):
        assert isinstance(hole, ShapeSortingHole)
        assert hole.shape_category is stood_hole.shape_category
        assert isinstance(hole.shape_category, MontessoriShapeCategory)


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

    stood = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))

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


CAPTURE_WITH_A_PIECE_ON_THE_LID = "displaced_cube_from_hole"
"""
A capture of the full-size set with pieces on the bare table and the cube on the lid,
the way the sorting demo starts them.
"""


@pytest.fixture
def look_at_the_lid() -> RecordedFrame:
    """
    A capture holding a piece on the lid as well as pieces on the table, looked at
    afresh for every request.
    """
    return RecordedFrame(
        pipeline=perception_pipeline(world=recorded_world()),
        frame=SceneCapture.load(CAPTURE_WITH_A_PIECE_ON_THE_LID).to_frame(),
    )


def test_a_piece_on_the_lid_is_stood_along_with_the_ones_on_the_table(
    look_at_the_lid: RecordedFrame,
) -> None:
    """
    The sorting demo starts a piece on the lid, so a look asked for both surfaces holds
    every piece there is to sort rather than only the ones on the bare table.
    """
    look = look_at_the_lid
    live = look.pipeline.world
    scene = look.scene()
    on_the_table = [
        shape.category
        for shape in scene.shapes
        if shape.supporting_surface == look.pipeline.table.name
    ]

    stood = PiecePublisher(world=live).publish(
        scene,
        resting_on=frozenset({look.pipeline.table.name, look.pipeline.lid.name}),
    )

    assert sorted(piece.shape_category for piece in stood) == sorted(
        on_the_table
        + list(CAPTURE_TRUTHS[CAPTURE_WITH_A_PIECE_ON_THE_LID].pieces_on_lid)
    )


def test_the_better_explained_of_two_sightings_of_one_shape_is_the_one_stood(
    look: RecordedFrame,
) -> None:
    """
    The set holds exactly one piece of every shape it contains, so a look that reports
    two sightings of the same shape has mistaken one place for the other; the one kept
    is the one whose own account better explains the picture.
    """
    resting_on = look.pipeline.table.name
    live = look.pipeline.world
    weaker = piece_at(0.70, 0.05, TABLE_HEIGHT, explains=0.4, reference_frame=live.root)
    stronger = piece_at(
        0.79, 0.10, TABLE_HEIGHT, explains=0.9, reference_frame=live.root
    )
    weaker.supporting_surface = resting_on
    stronger.supporting_surface = resting_on
    scene = MontessoriScene(shapes=[weaker, stronger])

    stood = PiecePublisher(world=live).publish(
        scene, resting_on=frozenset({resting_on})
    )

    assert len(stood) == 1
    assert live.get_semantic_annotations_by_type(MontessoriShape) == stood
    stands_at = stood[0].root.global_transform.to_position().to_np()[:2]
    assert stands_at == pytest.approx([0.79, 0.10])


def test_a_piece_on_another_surface_is_not_stood(look: RecordedFrame) -> None:
    scene = look.scene()
    live = look.pipeline.world

    stood = PiecePublisher(world=live).publish(
        scene, resting_on=frozenset({look.pipeline.lid.name})
    )

    assert stood == []
    assert live.get_semantic_annotations_by_type(MontessoriShape) == []


def test_the_piece_a_finding_names_is_the_one_the_published_world_holds(
    look: RecordedFrame,
) -> None:
    """
    A plan reaches for the piece a look answers with, so that piece has to be the one
    the world the robot plans in holds rather than a second body standing for the same
    sighting in a world of the look's own.
    """
    scene = look.scene()
    live = look.pipeline.world
    findings = list(scene.shapes)
    bodies_the_look_stood = [shape.role_taker for shape in findings]

    stood = PiecePublisher(world=live).publish(
        scene, resting_on=frozenset({look.pipeline.table.name})
    )

    left_in_the_looks_own_world = scene.imagined.world.get_semantic_annotations_by_type(
        MontessoriShape
    )
    for piece in stood:
        [(finding, its_own_body)] = [
            (shape, body)
            for shape, body in zip(findings, bodies_the_look_stood)
            if shape.role_taker is piece
        ]
        assert finding.category is piece.shape_category
        assert finding.root is piece.root
        assert not any(held is its_own_body for held in left_in_the_looks_own_world)


def test_two_looks_stand_pieces_under_different_names(look: RecordedFrame) -> None:
    scene = look.scene()
    publisher = PiecePublisher(world=look.pipeline.world)

    first = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))
    second = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))

    assert len({piece.name for piece in first + second}) == len(first) + len(second)
    assert publisher.published == first + second


def test_taking_the_pieces_down_leaves_none_of_them_in_the_world(
    look: RecordedFrame,
) -> None:
    scene = look.scene()
    live = look.pipeline.world
    publisher = PiecePublisher(world=live)
    stood = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))
    assert stood

    publisher.take_down()

    assert publisher.published == []
    assert live.get_semantic_annotations_by_type(MontessoriShape) == []
    assert not {piece.root for piece in stood} & set(live.bodies)


def test_a_piece_found_again_after_a_take_down_is_stood_as_the_same_piece(
    look: RecordedFrame,
) -> None:
    """
    Whatever kept a piece of the first look -- a monitor watching it, a question about
    it -- keeps the piece the second look finds, so a piece is stood again as the body
    it already was.
    """
    scene = look.scene()
    live = look.pipeline.world
    publisher = PiecePublisher(world=live)
    first = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))

    publisher.take_down()
    second = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))

    assert second == first
    assert all(piece.root in live.bodies for piece in second)
    assert live.get_semantic_annotations_by_type(MontessoriShape) == second


def test_the_pieces_an_earlier_run_stood_are_taken_down_before_a_look_stands_its_own(
    look: RecordedFrame,
) -> None:
    """
    The world fetched from the robot still holds the pieces every earlier run stood in
    it; a publisher that knew only what it had stood itself left them standing beside
    its own, one more set per run.
    """
    scene = look.scene()
    live = look.pipeline.world
    an_earlier_run = PiecePublisher(world=live)
    an_earlier_run.publish(scene, resting_on=frozenset({look.pipeline.table.name}))
    this_run = PiecePublisher(world=live)

    this_run.take_down()
    stood = this_run.publish(scene, resting_on=frozenset({look.pipeline.table.name}))

    assert live.get_semantic_annotations_by_type(MontessoriShape) == stood
    assert len(stood) == len(
        [
            shape
            for shape in scene.shapes
            if shape.supporting_surface == look.pipeline.table.name
        ]
    )


def test_a_piece_the_next_look_no_longer_finds_stays_taken_down(
    look: RecordedFrame,
) -> None:
    scene = look.scene()
    live = look.pipeline.world
    publisher = PiecePublisher(world=live)
    first = publisher.publish(scene, resting_on=frozenset({look.pipeline.table.name}))
    gone, *still_there = scene.shapes

    publisher.take_down()
    second = publisher.publish(
        MontessoriScene(shapes=still_there, board=scene.board, imagined=scene.imagined),
        resting_on=frozenset({look.pipeline.table.name}),
    )

    assert [piece.shape_category for piece in second] == [
        shape.category for shape in still_there
    ]
    assert set(second) < set(first)
    assert live.get_semantic_annotations_by_type(MontessoriShape) == second


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


A_SHOVE = Vector3(0.05, -0.02, 0.0)
"""
How far the look below finds the cube from where it stood, as a person's shove would
leave it.
"""

A_SLIDE = Vector3(0.0, 0.04, 0.0)
"""
How far the look below finds the board from where it stood.
"""


@dataclass
class RecordedFrameWhoseSceneCanBeMoved(RecordedFrame):
    """
    A look at one frame that reports, once told the scene has moved, the cube shoved and
    the board slid by stated displacements -- what a camera reports once the person at
    the table has moved them.
    """

    cube_shoved_by: Vector3 = field(kw_only=True)
    """
    How far the cube is found from where it stood, once the scene has moved.
    """

    board_slid_by: Vector3 = field(kw_only=True)
    """
    How far the board is found from where it stood, once the scene has moved.
    """

    moved: bool = False
    """
    Whether the person has moved the cube and the board yet.
    """

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        seen = super().scene(request)
        if not self.moved:
            return seen
        for shape in seen.shapes:
            if shape.category is MontessoriShapeCategory.CUBE:
                shape.pose = _moved(shape.pose, self.cube_shoved_by)
        if seen.stood_board is not None:
            imagined = seen.imagined.world
            imagined.move_branch_to(
                seen.stood_board.root,
                _moved(
                    seen.stood_board.root.global_pose, self.board_slid_by
                ).to_homogeneous_matrix(),
            )
        return seen


def _moved(pose: Pose, by: Vector3) -> Pose:
    """
    :return: The pose moved by a displacement in the frame it is stated in.
    """
    return (
        HomogeneousTransformationMatrix.from_xyz_rpy(
            x=float(by.x),
            y=float(by.y),
            z=float(by.z),
            reference_frame=pose.reference_frame,
        )
        @ pose.to_homogeneous_matrix()
    ).to_pose()


@pytest.fixture
def moving_look() -> RecordedFrameWhoseSceneCanBeMoved:
    """
    The capture, which can be told the cube was shoved and the board slid.
    """
    return RecordedFrameWhoseSceneCanBeMoved(
        pipeline=perception_pipeline(world=recorded_world(), pieces=SMALLER_PIECES),
        frame=SceneCapture.load(MEASURED_CAPTURE).to_frame(),
        cube_shoved_by=A_SHOVE,
        board_slid_by=A_SLIDE,
    )


def _position_of(body: Body) -> List[float]:
    """
    :return: Where a body stands, as ``[x, y]`` in the world root frame.
    """
    return body.global_transform.to_position().to_np()[:2].flatten().tolist()


def test_a_scene_perceived_again_holds_the_same_pieces_where_the_look_finds_them_now(
    moving_look: RecordedFrameWhoseSceneCanBeMoved,
) -> None:
    live = moving_look.pipeline.world
    scene = PerceivedScene(world=live, look=moving_look, described_board=lab_board())
    scene.perceive()
    first = list(scene.pieces)
    stood_at = {piece: _position_of(piece.root) for piece in first}
    [cube] = [
        piece for piece in first if piece.shape_category is MontessoriShapeCategory.CUBE
    ]
    moving_look.moved = True

    scene.perceive()

    assert scene.pieces == first
    assert live.get_semantic_annotations_by_type(MontessoriShape) == first
    assert all(piece.root in live.bodies for piece in first)
    assert _position_of(cube.root) == pytest.approx(
        [stood_at[cube][0] + float(A_SHOVE.x), stood_at[cube][1] + float(A_SHOVE.y)]
    )
    for piece in first:
        if piece is not cube:
            assert _position_of(piece.root) == pytest.approx(stood_at[piece])


def test_a_scene_perceived_again_holds_the_same_board_where_the_look_finds_it_now(
    moving_look: RecordedFrameWhoseSceneCanBeMoved,
) -> None:
    live = moving_look.pipeline.world
    scene = PerceivedScene(world=live, look=moving_look, described_board=lab_board())
    scene.perceive()
    board = scene.board
    stood_at = _position_of(board.root)
    holes_stood_at = [_position_of(hole.root) for hole in board.apertures]
    moving_look.moved = True

    scene.perceive()

    assert scene.board is board
    assert ShapeSortingBoard.held_by(live) is board
    assert _position_of(board.root) == pytest.approx(
        [stood_at[0] + float(A_SLIDE.x), stood_at[1] + float(A_SLIDE.y)]
    )
    for hole, hole_stood_at in zip(board.apertures, holes_stood_at):
        assert _position_of(hole.root) == pytest.approx(
            [hole_stood_at[0] + float(A_SLIDE.x), hole_stood_at[1] + float(A_SLIDE.y)]
        )
    assert moving_look.pipeline.lid == WorkspaceSurface.of(
        board, moving_look.pipeline.reference_frame
    )


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
