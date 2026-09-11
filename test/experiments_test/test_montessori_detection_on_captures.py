"""
What the pipeline finds in the captures taken off the real camera.

These are the only tests that measure detection against the physical table rather than
against a rendered scene, so they are where a change to the detectors is judged. Each
capture states what it really holds
(:data:`~experiments_test.dataset.montessori_capture_fixtures.CAPTURE_TRUTHS`), and the
tests below say which parts of that the pipeline gets right today.

A test marked expected-to-fail names the plan item that will make it pass; the mark is
strict, so the day that item lands the test reports the mark as stale rather than
quietly passing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import cv2
import numpy as np
import pytest
from typing_extensions import List, Tuple

from experiments.montessori.board_description import DescribedBoard
from experiments.montessori.hole_geometry import BoardHoleLayout, detect_hole_footprints
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.orthophoto import Orthophoto
from experiments.montessori.perception.explanations import CompetingExplanations
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.pipeline import BOARD_SCALES_TRIED
from experiments.montessori.perception.recorded_setup import (
    WIDEST_WORKSPACE,
    perception_pipeline,
)
from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.montessori.perception.scene_request import SceneRequest
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.semantics import MontessoriShapeCategory, ShapeSortingBoard
from experiments.montessori.world import BOARD_SCALE
from semantic_digital_twin.datastructures.prefixed_name import PrefixedName

from .dataset import montessori_capture_fixtures
from .dataset.montessori_capture_truths import CAPTURE_TRUTHS, CaptureTruth

pytest_plugins = [montessori_capture_fixtures.__name__]

# %% running one capture


def detections_on(
    scene: MontessoriScene, surface: PrefixedName
) -> Counter[MontessoriShapeCategory]:
    """
    How many pieces of each category a look at the scene put on one surface.

    :param scene: The result of one look.
    :param surface: The surface to count the pieces resting on.
    """
    return Counter(
        shape.category for shape in scene.shapes if shape.supporting_surface == surface
    )


@pytest.fixture(params=sorted(CAPTURE_TRUTHS), ids=sorted(CAPTURE_TRUTHS))
def capture(request: pytest.FixtureRequest) -> SceneCapture:
    """
    Each shipped capture in turn.
    """
    return SceneCapture.load(request.param)


@pytest.fixture
def truth(capture: SceneCapture) -> CaptureTruth:
    """
    What the capture under test really holds.
    """
    return CAPTURE_TRUTHS[capture.name]


@pytest.fixture
def capture_pipeline(truth: CaptureTruth) -> MontessoriPerceptionPipeline:
    """
    The pipeline that reads the capture under test, over the surfaces it was taken on
    and for the set of pieces it holds.
    """
    return perception_pipeline(pieces=truth.piece_set)


@pytest.fixture
def scene(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> MontessoriScene:
    """
    One look at the capture under test.
    """
    return capture_pipeline.detect(capture.to_frame())


def brightness_within(outline: np.ndarray, lid: Orthophoto) -> float:
    """
    How bright the lid's rectified view is inside one outline.

    :param outline: World-frame ``(n, 2)`` points bounding the region to read.
    :param lid: The rectified view of the lid's plane.
    :return: The middle brightness of the pixels it encloses.
    """
    stencil = np.zeros(lid.image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(stencil, [lid.region.to_pixels(outline).round().astype(np.int32)], 255)
    return float(np.median(lid.hue_saturation_value[:, :, 2][stencil > 0]))


def lies_over_an_opening(
    hole: ShapeSortingHoleDetection,
    board: MontessoriBoardDetection,
    lid: Orthophoto,
) -> bool:
    """
    Whether a reported hole is darker than the board it is cut into.

    :param hole: The hole as reported.
    :param board: The board it belongs to.
    :param lid: The rectified view of the lid's plane.
    """
    return brightness_within(hole.outline, lid) < brightness_within(board.outline, lid)


# %% the board


def test_the_board_is_found_in_every_capture(
    scene: MontessoriScene, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    The board stands on the table in all of them, and its lid is the plane the pipeline
    was told to look for it on.
    """
    assert scene.board is not None
    assert scene.board.lid_height == capture_pipeline.lid.height


MESH_SCALE_TOLERANCE = 0.08
"""
How far from the mesh's own size the board may measure and still be that mesh's size.

A piece standing on a hole takes that opening away from the measurement and moves the
best size by up to seven parts in a hundred, measured with three pieces on the lid; a
camera pose that foreshortens the lid moved it by fourteen, which is what this keeps
out.
"""


def test_the_board_is_the_size_of_the_mesh_that_models_it(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    Of every size the board could be, the mesh's own explains the openings the camera
    saw best, within :data:`MESH_SCALE_TOLERANCE`.

    Where the holes lie relative to one another is cut into the board, so this keeps the
    mesh answerable from the captures rather than only asserted by them -- a camera pose
    that foreshortens the lid reads as a board smaller than its mesh.
    """
    lid = capture_pipeline.rectify(capture.to_frame(), capture_pipeline.lid.height)

    assert capture_pipeline.look_rules.find_the_board.board_detector.measure_scale(
        lid, candidates=BOARD_SCALES_TRIED
    ) == pytest.approx(1.0, abs=MESH_SCALE_TOLERANCE)


def test_every_hole_in_the_board_is_found(
    scene: MontessoriScene,
    capture: SceneCapture,
    truth: CaptureTruth,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    The board has as many holes as its own mesh was cut with, of the same categories,
    and each one is reported over an opening rather than over the lid's own wood --
    unless a piece standing on the lid covers it, which a piece can do to no more holes
    than there are pieces.

    The second half is what makes this a measurement. A detector that reads its holes
    off the board's model reports the model's categories wherever it puts them, so
    counting them says only that a board was found; that they are darker than the lid
    around them is what says they are the holes.
    """
    assert scene.board is not None
    assert Counter(hole.category for hole in scene.board.holes) == Counter(
        footprint.category for footprint in detect_hole_footprints()
    )
    lid = capture_pipeline.rectify(capture.to_frame(), capture_pipeline.lid.height)
    covered = [
        hole.category
        for hole in scene.board.holes
        if not lies_over_an_opening(hole, scene.board, lid)
    ]
    assert len(covered) <= len(truth.pieces_on_lid), covered


# %% the board found from its description

PLACEMENT_TOLERANCE = 0.02
"""
How far apart, in metres, the board found from its description and the board found on
the modelled lid may stand.

Within five millimetres on a lid whose openings are all in view; with three of the six
covered by pieces the two fits are held by half the openings and stand nineteen
millimetres apart, and that is what this allows for.
"""


def test_the_board_is_found_from_its_description_with_no_board_modelled(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    A board the world does not hold is found by fitting the layout a statement
    describes, on the plane its stated height puts the lid at above the table this look
    measured, and it stands where the board found on the modelled lid does.
    """
    frame = capture.to_frame()
    described = DescribedBoard.of_layout(
        BoardHoleLayout.of_board_mesh(),
        height=float(BOARD_SCALE.z),
    )
    unmodelled = replace(capture_pipeline, lid=None)

    found = unmodelled.detect(
        frame,
        SceneRequest(
            detection_type=MontessoriBoardDetection, described_board=described
        ),
    ).board

    modelled = capture_pipeline.board_in(frame)
    assert found is not None
    assert Counter(hole.category for hole in found.holes) == Counter(
        hole.category for hole in described.layout.holes
    )
    assert found.lid_height == pytest.approx(
        unmodelled.table_in(frame).height + described.height
    )
    found_at = found.pose.to_position().to_np()[:2]
    modelled_at = modelled.pose.to_position().to_np()[:2]
    assert float(np.linalg.norm(found_at - modelled_at)) <= PLACEMENT_TOLERANCE


def test_a_statement_describing_the_board_is_answered_with_the_board_it_found(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    Asking for a board by what it measures answers with the board annotation standing
    where the look found it, carrying the lid and the holes it was described with.
    """
    described = DescribedBoard.of_layout(
        BoardHoleLayout.of_board_mesh(),
        height=float(BOARD_SCALE.z),
    )
    looking = MontessoriPerceptionBackend(
        source=RecordedFrame(
            pipeline=replace(capture_pipeline, lid=None), frame=capture.to_frame()
        )
    )

    [board] = described.statement().evaluate(backend=looking)

    assert isinstance(board, ShapeSortingBoard)
    assert (board.lid_size, board.height) == (described.lid_size, described.height)
    assert [hole.shape_category for hole in board.apertures] == [
        hole.shape_category for hole in described.holes
    ]


# %% the loose pieces


TABLE_PIECES_STILL_MISREAD: List[str] = [
    "stuck_cube_in_hole",
    "displaced_cube_from_hole",
]
"""
The captures with a piece on the table this look reports as another kind, or not at all.

Both have the full-size cylinder standing off to the robot's left, where the camera sees
its side as well as its top, and the side's edges lie outside the top face. On
``stuck_cube_in_hole`` the cube's larger outline accounts for more of them than the
cylinder's own does (0.44 against 0.32 of the edges, a lead of 0.11 in strength), so a
cube is reported; on ``displaced_cube_from_hole`` the cylinder leads the cube by 0.074,
one thousandth under the lead a report requires, so nothing is. Recorded on 2026-09-11,
when the camera pose the captures state was corrected and the rectified top face became
a true circle; the old pose read it as an ellipse the cube fitted worse. Preferring the
outline that explains the edges *of a piece that size* rather than the most edges is
``competing-explanations``.
"""


def expected_to_misread_the_table(request: pytest.FixtureRequest, name: str) -> None:
    """
    Mark a test on a capture in :data:`TABLE_PIECES_STILL_MISREAD` expected to fail,
    strictly, so the day the misreading is fixed the mark reports as stale.

    :param request: The test being run.
    :param name: The capture it runs on.
    """
    if name in TABLE_PIECES_STILL_MISREAD:
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=(
                    "A cylinder seen with its side is reported as a cube, or not at "
                    "all - see TABLE_PIECES_STILL_MISREAD. Owned by the plan item "
                    "competing-explanations."
                ),
            )
        )


def test_every_piece_resting_on_the_table_is_found(
    request: pytest.FixtureRequest,
    scene: MontessoriScene,
    truth: CaptureTruth,
    capture: SceneCapture,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    Every piece lying on the bare steel is detected there, with its own category.
    """
    expected_to_misread_the_table(request, capture.name)
    found = detections_on(scene, capture_pipeline.table.name)
    assert not (Counter(truth.pieces_on_table) - found)


def test_only_the_pieces_resting_on_the_table_are_detected_there(
    request: pytest.FixtureRequest,
    scene: MontessoriScene,
    truth: CaptureTruth,
    capture: SceneCapture,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    Nothing is reported on the table that is not lying on it.
    """
    expected_to_misread_the_table(request, capture.name)
    assert detections_on(scene, capture_pipeline.table.name) == Counter(
        truth.pieces_on_table
    )


LID_PIECES_STILL_MISSED: List[str] = [
    "objects_on_montessori",
    "non_inserted_objects",
]
"""
The captures whose lid pieces this look does not report.

Their pieces wear the lid's own hue or touch one another, so no colour suggests a place
to look, and a look told where to expect a piece finds it (see
``test_a_piece_wearing_the_surfaces_own_hue_is_found_where_it_is_expected``). What can
tell it differs between these, and only one kind of telling exists on a capture.

Three captures left this list on 2026-09-11, when the camera pose the captures state was
corrected: ``disoriented_cube_on_hole`` and ``displaced_cube_from_hole`` are a cube on a
hole that is fitted once the lid is rectified where it really lies, and
``tracy_pickup_demo``'s cylinder standing *in* its hole is fitted at the tape-refined
pose and not at one nine millimetres from it, where a cube's outline on the hole's own
rim explains the edges nearly as well as the piece does (0.70 against 0.73). That the
answer turns on nine millimetres is the fragility ``competing-explanations`` is about:
separating a piece from a ghost that follows the same edges.

The other two are pieces nothing acted on, so no history says anything about them, and a
capture carries no world to say it instead.
"""


def test_every_piece_resting_on_the_lid_is_found(
    request: pytest.FixtureRequest,
    scene: MontessoriScene,
    truth: CaptureTruth,
    capture: SceneCapture,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    Every piece resting on the board's lid is detected there, with its own category.
    """
    if capture.name in LID_PIECES_STILL_MISSED:
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=(
                    "Colour cannot separate a piece on the lid, and what would tell "
                    "this look to expect one differs per capture - see "
                    "LID_PIECES_STILL_MISSED. Owned by the plan item "
                    "competing-explanations."
                ),
            )
        )
    found = detections_on(scene, capture_pipeline.lid.name)
    assert not (Counter(truth.pieces_on_lid) - found)


# %% where the tape put the pieces and the board

TAPE_TOLERANCE = 0.015
"""
How far, in metres, a reported place may lie from where a tape measure put a piece's
middle: the tape reads to about five millimetres, and a piece's middle is judged by eye.
"""

TAPE_MEASURED_CAPTURES = sorted(
    name for name, truth in CAPTURE_TRUTHS.items() if truth.tape_measured
)
"""
The captures whose scene was measured on the table rather than only read off the
picture.
"""


@pytest.fixture(params=TAPE_MEASURED_CAPTURES, ids=TAPE_MEASURED_CAPTURES)
def measured_capture(request: pytest.FixtureRequest) -> SceneCapture:
    """
    Each capture measured with a tape in turn.
    """
    return SceneCapture.load(request.param)


@pytest.fixture
def measured_scene(measured_capture: SceneCapture) -> MontessoriScene:
    """
    One look at the measured capture under test, for the set of pieces it holds.
    """
    pipeline = perception_pipeline(
        pieces=CAPTURE_TRUTHS[measured_capture.name].piece_set
    )
    return pipeline.detect(measured_capture.to_frame())


def test_every_piece_is_reported_where_the_tape_put_it(
    measured_capture: SceneCapture, measured_scene: MontessoriScene
) -> None:
    """
    Each piece the tape measured is reported once, as its own kind, within the tape's
    tolerance of where it stands -- which is what says the camera's pose, the pieces'
    stated sizes and the rectification agree with the table itself.
    """
    truth = CAPTURE_TRUTHS[measured_capture.name]

    for measured in truth.tape_measured:
        reported = [
            shape
            for shape in measured_scene.shapes
            if shape.category == measured.category
        ]
        assert len(reported) == 1, measured
        centre = reported[0].outline.mean(axis=0)
        assert (
            float(np.hypot(centre[0] - measured.place.x, centre[1] - measured.place.y))
            <= TAPE_TOLERANCE
        ), (measured, centre)


def test_the_board_is_reported_where_the_tape_put_its_corner(
    measured_capture: SceneCapture, measured_scene: MontessoriScene
) -> None:
    """
    The board's lid is outlined with its front-left corner within the tape's tolerance
    of where the tape put it.
    """
    corner = CAPTURE_TRUTHS[measured_capture.name].board_front_left_corner

    assert measured_scene.board is not None
    distances = np.hypot(
        measured_scene.board.outline[:, 0] - corner.x,
        measured_scene.board.outline[:, 1] - corner.y,
    )
    assert float(distances.min()) <= TAPE_TOLERANCE, measured_scene.board.outline


# %% what the stated lead buys


LEADS_MEASURED_AGAINST_EACH_OTHER = (0.0, 0.075, 0.2)
"""
Three statements of how costly a wrong report is, from *not at all* upwards.

The middle one is what :class:`~experiments.montessori.perception.explanations.CompetingExplanations`
states by default, and the outer two bracket it far enough for the trade between the two
kinds of error to be visible over six captures.
"""


def missed_and_invented(
    scene: MontessoriScene, truth: CaptureTruth, pipeline: MontessoriPerceptionPipeline
) -> Tuple[int, int]:
    """
    How many pieces a look failed to report, and how many it reported that are not
    there.

    :param scene: The result of one look.
    :param truth: What the capture really holds.
    :param pipeline: The pipeline that took the look, for what it calls each surface.
    :return: The two counts, in that order.
    """
    missed = invented = 0
    for surface, standing_there in (
        (pipeline.table.name, truth.pieces_on_table),
        (pipeline.lid.name, truth.pieces_on_lid),
    ):
        found = detections_on(scene, surface)
        missed += sum((Counter(standing_there) - found).values())
        invented += sum((found - Counter(standing_there)).values())
    return missed, invented


def test_saying_a_wrong_report_costs_more_trades_recall_for_it(
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    The plan's central claim as a measurement: what a look must show before it reports
    something is a statement about cost, and moving that statement moves the two kinds
    of error against each other rather than only one of them.

    This is the quantity the item exists to make plottable, kept answerable from the
    captures rather than written down as a table that stops being true.
    """
    frames = {
        name: SceneCapture.load(name).to_frame() for name in sorted(CAPTURE_TRUTHS)
    }
    measured = []
    for lead in LEADS_MEASURED_AGAINST_EACH_OTHER:
        capture_pipeline.explanations = CompetingExplanations(required_lead=lead)
        totals = [
            missed_and_invented(
                capture_pipeline.detect(frame), CAPTURE_TRUTHS[name], capture_pipeline
            )
            for name, frame in frames.items()
        ]
        measured.append(
            (sum(missed for missed, _ in totals), sum(made_up for _, made_up in totals))
        )

    missed = [count for count, _ in measured]
    invented = [count for _, count in measured]
    assert missed == sorted(missed)
    assert invented == sorted(invented, reverse=True)
    assert invented[0] > invented[-1]


# %% the table the look measured for itself


def test_the_table_is_measured_smaller_than_the_stretch_the_world_allows(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    A look reads the table rather than a rectangle drawn around it, so it searches less
    of the picture than the setup allows it to.
    """
    modelled = capture_pipeline.table.region
    measured = capture_pipeline.table_in(capture.to_frame()).region
    assert measured.area < modelled.area


def test_the_measured_table_stays_inside_the_stretch_the_world_allows(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    The measurement narrows what the world states and never grows it, so a run only ever
    searches ground the world had already described.
    """
    modelled = capture_pipeline.table.region
    measured = capture_pipeline.table_in(capture.to_frame()).region
    assert modelled.contains(measured.minimum_x, measured.minimum_y) and (
        modelled.contains(measured.maximum_x, measured.maximum_y)
    )


def test_tuning_the_workspace_no_longer_changes_what_a_look_searches(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    What this item replaces: the searched stretch used to be whatever a person had
    dragged the sliders to, and it is now what the camera shows, so starting from the
    whole stretch the camera looks over reaches the same answer as starting from a
    workspace already cut down by hand.
    """
    untuned = replace(
        capture_pipeline,
        table=replace(capture_pipeline.table, region=WIDEST_WORKSPACE),
    )
    frame = capture.to_frame()
    assert untuned.table_in(frame).region == capture_pipeline.table_in(frame).region


def test_every_piece_reported_stands_on_the_table_that_was_measured(
    capture: SceneCapture,
    capture_pipeline: MontessoriPerceptionPipeline,
    scene: MontessoriScene,
) -> None:
    """
    Nothing is reported outside the stretch the look measured, which is what says the
    narrowing threw away picture rather than pieces.
    """
    measured = capture_pipeline.table_in(capture.to_frame()).region
    outside = [
        shape.label
        for shape in scene.shapes
        if not measured.contains(
            float(shape.pose.to_position().x), float(shape.pose.to_position().y)
        )
    ]
    assert outside == []
