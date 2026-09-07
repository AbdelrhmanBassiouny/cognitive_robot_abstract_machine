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

import cv2
import numpy as np
import pytest
from typing_extensions import List, Tuple

from experiments.montessori.hole_geometry import detect_hole_footprints
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriScene,
    ShapeSortingHoleDetection,
)
from experiments.montessori.perception.orthophoto import Orthophoto
from experiments.montessori.perception.explanations import CompetingExplanations
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import (
    BOARD_SCALE_AGAINST_THE_MESH,
)
from experiments.montessori.semantics import MontessoriShapeCategory
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


def test_the_board_is_smaller_than_the_mesh_that_models_it(
    capture: SceneCapture, capture_pipeline: MontessoriPerceptionPipeline
) -> None:
    """
    The size this setup states its board to be explains the openings the camera saw, and
    the mesh's own size does not.

    Where the holes lie relative to one another is cut into the board, so a look that no
    placement of the layout reaches says the board is not the size the mesh was drawn
    at. This keeps the size that was written down answerable from the captures rather
    than only asserted by them.
    """
    lid = capture_pipeline.rectify(capture.to_frame(), capture_pipeline.lid.height)

    assert (
        capture_pipeline.board_detector.measure_scale(
            lid, candidates=(BOARD_SCALE_AGAINST_THE_MESH, 1.0)
        )
        == BOARD_SCALE_AGAINST_THE_MESH
    )


def test_every_hole_in_the_board_is_found(
    scene: MontessoriScene,
    capture: SceneCapture,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    The board has as many holes as its own mesh was cut with, of the same categories,
    and each one is reported over an opening rather than over the lid's own wood.

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
    assert [
        hole.category
        for hole in scene.board.holes
        if not lies_over_an_opening(hole, scene.board, lid)
    ] == []


# %% the loose pieces


def test_every_piece_resting_on_the_table_is_found(
    scene: MontessoriScene,
    truth: CaptureTruth,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    Every piece lying on the bare steel is detected there, with its own category.
    """
    found = detections_on(scene, capture_pipeline.table.name)
    assert not (Counter(truth.pieces_on_table) - found)


def test_only_the_pieces_resting_on_the_table_are_detected_there(
    scene: MontessoriScene,
    truth: CaptureTruth,
    capture_pipeline: MontessoriPerceptionPipeline,
) -> None:
    """
    Nothing is reported on the table that is not lying on it.
    """
    assert detections_on(scene, capture_pipeline.table.name) == Counter(
        truth.pieces_on_table
    )


LID_PIECES_STILL_MISSED: List[str] = [
    "objects_on_montessori",
    "disoriented_cube_on_hole",
    "displaced_cube_from_hole",
    "non_inserted_objects",
]
"""
The captures whose lid pieces no look at them expects.

Their pieces wear the lid's own hue or touch one another, so no colour suggests a place
to look; and a capture carries no world, so nothing else here believes anything about
the lid. A look told where to expect a piece finds it (see
``test_a_piece_wearing_the_surfaces_own_hue_is_found_where_it_is_expected``), and what
would tell it on a capture is the object's own history.
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
                    "Nothing tells this look to expect a piece on the lid, and colour "
                    "cannot separate one there. Owned by the plan item "
                    "expectations-from-events."
                ),
            )
        )
    found = detections_on(scene, capture_pipeline.lid.name)
    assert not (Counter(truth.pieces_on_lid) - found)


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
