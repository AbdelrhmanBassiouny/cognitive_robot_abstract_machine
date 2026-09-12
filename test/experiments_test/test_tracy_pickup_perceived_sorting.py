"""
Tests for :mod:`experiments.tracy_experiments.pickup.perceived_sorting`: a run looks for
the board and the pieces, stands both in the world it plans in, and releases each piece
over the hole of the perceived board it fits through -- measured on the capture whose
table was laid out with a tape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest
from typing_extensions import List, Tuple

from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.exceptions import NoBoardInView
from experiments.montessori.perception.recorded_setup import (
    TABLE_HEIGHT,
    lab_board,
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.scene_publishing import (
    PUBLISHED_PREFIX,
    PerceivedScene,
)
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import RecordedFrame, RepeatedLook
from experiments.montessori.perception.surfaces import WorkspaceSurface
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.tracy_experiments.pickup.perceived_sorting import (
    PerceivedSorting,
    ShapeSorter,
)
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
    Pose,
)
from semantic_digital_twin.world import World

from .dataset.montessori_capture_truths import CAPTURE_TRUTHS, CaptureTruth
from .test_montessori_detection_on_captures import TAPE_TOLERANCE

MEASURED_CAPTURE = "scaled_pieces_in_a_row"
"""
The capture whose pieces and board were measured with a tape.
"""


@dataclass
class _SorterKeepingWhatItWasHanded(ShapeSorter):
    """
    Stands in for the arm: keeps every piece and release pose it was handed, in order.
    """

    sorted: List[Tuple[MontessoriShape, Pose]] = field(default_factory=list)

    def sort(self, piece: MontessoriShape, release_pose: Pose) -> None:
        self.sorted.append((piece, release_pose))


@dataclass
class _LookKeepingItsRequests(RecordedFrame):
    """
    The capture looked at afresh, keeping what each look was asked for.
    """

    requests: List[SceneRequest] = field(default_factory=list)

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        self.requests.append(request)
        return super().scene(request)


@pytest.fixture
def truth() -> CaptureTruth:
    """
    What the measured capture really holds.
    """
    return CAPTURE_TRUTHS[MEASURED_CAPTURE]


@pytest.fixture
def world() -> World:
    """
    A world standing in for the one the robot publishes: its surfaces, and no board.
    """
    return recorded_world()


@pytest.fixture
def look(world: World, truth: CaptureTruth) -> _LookKeepingItsRequests:
    """
    The measured capture, looked at afresh for every request, for the set of pieces it
    holds.
    """
    return _LookKeepingItsRequests(
        pipeline=perception_pipeline(world=world, pieces=truth.piece_set),
        frame=SceneCapture.load(MEASURED_CAPTURE).to_frame(),
    )


def _held_board(world: World) -> ShapeSortingBoard:
    """
    :return: The lab board, stood in the world by hand as one a fetch would already hold.
    """
    return lab_board().stand_in(
        world,
        Pose.from_xyz_rpy(1.0, 0.15, TABLE_HEIGHT + lab_board().height),
        prefix="held",
    )


@dataclass
class _LookAtAnEmptyTable(RepeatedLook):
    """
    A source showing a table with nothing on it, keeping what each look was asked for.
    """

    requests: List[SceneRequest] = field(default_factory=list)

    def scene(self, request: SceneRequest = SceneRequest()) -> MontessoriScene:
        self.requests.append(request)
        return MontessoriScene()


@pytest.fixture
def sorting(world: World, look: RecordedFrame) -> PerceivedSorting:
    """
    A run over the measured capture that has already looked.
    """
    run = PerceivedSorting(
        scene=PerceivedScene(world=world, look=look, described_board=lab_board()),
        sorter=_SorterKeepingWhatItWasHanded(),
    )
    run.perceive()
    return run


def _position(piece: MontessoriShape) -> np.ndarray:
    """
    :return: Where a piece's centre stands, in the world root frame.
    """
    return piece.root.global_transform.to_position().to_np()[:3]


# %% the board


def test_the_board_is_stood_in_the_world_where_the_tape_put_it(
    sorting: PerceivedSorting, world: World, truth: CaptureTruth
) -> None:
    """
    The world holds one board, stood by the look with its front-left corner within the
    tape's tolerance of where the tape put it and its lid as high as the description
    says.
    """
    assert ShapeSortingBoard.held_by(world) is sorting.board
    assert sorting.board.name.prefix == PUBLISHED_PREFIX
    centre_T_front_left_corner = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=-sorting.board.lid_size.x / 2, y=sorting.board.lid_size.y / 2
    )
    corner = sorting.board.root.global_transform @ centre_T_front_left_corner
    corner_xy = corner.to_position().to_np()[:2]
    assert (
        float(
            np.hypot(
                corner_xy[0] - truth.board_front_left_corner.x,
                corner_xy[1] - truth.board_front_left_corner.y,
            )
        )
        <= TAPE_TOLERANCE
    ), corner_xy
    assert WorkspaceSurface.of(sorting.board, world.root).height == pytest.approx(
        TABLE_HEIGHT + lab_board().height
    )


def test_the_look_reads_the_lid_of_the_board_it_stood(
    sorting: PerceivedSorting, world: World
) -> None:
    """
    Once the board is stood, the pipeline is handed that board's lid as the second
    surface it reads.
    """
    assert sorting.scene.look.pipeline.lid.entity is sorting.board.root
    assert sorting.scene.look.pipeline.lid.height == pytest.approx(
        WorkspaceSurface.of(sorting.board, world.root).height
    )


def test_a_board_the_world_already_holds_is_moved_to_where_the_look_finds_it(
    look: _LookKeepingItsRequests, world: World, truth: CaptureTruth
) -> None:
    """
    A world holding a board keeps that board, and the look for the board moves it to
    where the camera finds it now: a fetch may hold a board from a table since changed.
    """
    held = _held_board(world)
    stood_by_hand = held.root.global_transform.to_position().to_np()[:2]
    run = PerceivedSorting(
        scene=PerceivedScene(world=world, look=look, described_board=lab_board()),
        sorter=_SorterKeepingWhatItWasHanded(),
    )

    run.perceive()

    assert run.board is held
    assert [request.described_board for request in look.requests] == [
        lab_board(),
        None,
    ]
    centre_T_front_left_corner = HomogeneousTransformationMatrix.from_xyz_rpy(
        x=-held.lid_size.x / 2, y=held.lid_size.y / 2
    )
    corner_xy = (
        (held.root.global_transform @ centre_T_front_left_corner)
        .to_position()
        .to_np()[:2]
    )
    assert (
        float(
            np.hypot(
                corner_xy[0] - truth.board_front_left_corner.x,
                corner_xy[1] - truth.board_front_left_corner.y,
            )
        )
        <= TAPE_TOLERANCE
    ), corner_xy
    assert not np.allclose(held.root.global_transform.to_position().to_np()[:2], stood_by_hand)


def test_a_run_with_no_board_in_view_says_so(
    world: World, look: _LookKeepingItsRequests
) -> None:
    """
    A look showing no board ends the run before any piece is stood, after as many looks
    as it was allowed.
    """
    described = lab_board()
    empty_table = _LookAtAnEmptyTable(pipeline=look.pipeline)
    run = PerceivedSorting(
        scene=PerceivedScene(
            world=world,
            look=empty_table,
            described_board=described,
            looks_for_board=2,
            board_search_period=0.0,
        ),
        sorter=_SorterKeepingWhatItWasHanded(),
    )

    with pytest.raises(NoBoardInView) as raised:
        run.perceive()

    assert raised.value.looks == 2
    assert run.pieces == []
    assert ShapeSortingBoard.held_by(world) is None
    assert [request.described_board for request in empty_table.requests] == [
        described
    ] * 2


# %% the pieces


def test_every_piece_the_tape_measured_is_stood_where_the_tape_put_it(
    sorting: PerceivedSorting, world: World, truth: CaptureTruth
) -> None:
    """
    The world holds one piece per piece on the table, of its own kind, standing within
    the tape's tolerance of where the tape put it and resting on the table.
    """
    assert world.get_semantic_annotations_by_type(MontessoriShape) == sorting.pieces
    assert sorted(piece.shape_category for piece in sorting.pieces) == sorted(
        truth.pieces_on_table
    )
    for measured in truth.tape_measured:
        [piece] = [
            piece
            for piece in sorting.pieces
            if piece.shape_category is measured.category
        ]
        stands_at = _position(piece)
        assert (
            float(
                np.hypot(
                    stands_at[0] - measured.place.x, stands_at[1] - measured.place.y
                )
            )
            <= TAPE_TOLERANCE
        ), (measured, stands_at)
        assert stands_at[2] == pytest.approx(
            TABLE_HEIGHT + PerceivedSorting.half_height_of(piece)
        )


def test_a_piece_stands_as_the_known_piece_it_was_seen_as(
    sorting: PerceivedSorting, truth: CaptureTruth
) -> None:
    """
    A stood piece is the size the set it was looked for in says it is.
    """
    for piece in sorting.pieces:
        known = truth.piece_set.by_category[piece.shape_category]
        assert PerceivedSorting.half_height_of(piece) == pytest.approx(known.height / 2)
        assert piece.name.prefix == PUBLISHED_PREFIX


# %% where each piece is let go


def test_a_piece_is_released_over_the_hole_it_fits_through(
    sorting: PerceivedSorting, world: World
) -> None:
    """
    A piece is let go with its underside the stated hover above the lid, over the
    centre of the hole of the perceived board it fits through.
    """
    lid_height = WorkspaceSurface.of(sorting.board, world.root).height
    for piece in sorting.pieces:
        hole = sorting.board.hole_for(piece)
        hole_at = hole.root.global_transform.to_position().to_np()

        pose = sorting.release_pose_for(piece)

        assert pose.reference_frame is world.root
        released_at = pose.to_position().to_np()
        assert released_at[:2] == pytest.approx(hole_at[:2])
        assert released_at[2] == pytest.approx(
            lid_height + sorting.hover + PerceivedSorting.half_height_of(piece)
        )


def test_the_cylinder_is_released_over_the_smaller_circular_hole(
    sorting: PerceivedSorting,
) -> None:
    """
    The board has two circular holes the cylinder fits through; it is dropped through
    the smaller one.
    """
    [cylinder] = [
        piece
        for piece in sorting.pieces
        if piece.shape_category is MontessoriShapeCategory.CYLINDER
    ]
    circular = [
        hole
        for hole in sorting.board.apertures
        if hole.shape_category is MontessoriShapeCategory.CYLINDER
    ]
    assert len(circular) == 2

    assert sorting.board.hole_for(cylinder) is min(
        circular, key=lambda hole: hole.cross_section_size
    )


def test_every_piece_is_sorted_in_the_order_it_was_reported(
    sorting: PerceivedSorting,
) -> None:
    """
    The sorter is handed each stood piece with its own release pose, in report order.
    """
    sorting.sort_every_piece()

    sorter = sorting.sorter
    assert [piece for piece, _ in sorter.sorted] == sorting.pieces
    for piece, release_pose in sorter.sorted:
        assert release_pose.to_position().to_np() == pytest.approx(
            sorting.release_pose_for(piece).to_position().to_np()
        )
