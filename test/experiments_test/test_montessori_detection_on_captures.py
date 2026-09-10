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

import pytest
from typing_extensions import List

from experiments.montessori.hole_geometry import detect_hole_footprints
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.recorded_setup import WIDEST_WORKSPACE
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The hole classifier still measures a contour's fill and aspect instead of "
        "fitting the known outlines, so it finds five of the board's six holes and "
        "calls most of them triangular prisms. Owned by the plan item "
        "holes-fitted-like-pieces."
    ),
)
def test_every_hole_in_the_board_is_found(scene: MontessoriScene) -> None:
    """
    The board has as many holes as its own mesh was cut with, of the same categories.
    """
    assert scene.board is not None
    assert Counter(hole.category for hole in scene.board.holes) == Counter(
        footprint.category for footprint in detect_hole_footprints()
    )


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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "A piece standing on the lid is reported a second time on the table, where "
        "the table pass rectified it. Owned by the plan item one-detection-per-thing."
    ),
)
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
The captures whose lid pieces the detectors cannot yet read.

Their pieces either wear the lid's own hue or touch one another, so segmentation hands
the edge fit either nothing to start from or one blob covering several pieces.
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
                    "Pieces on the lid are lost to it or to one another; owned by the "
                    "plan item detector-parameters-from-knowledge."
                ),
            )
        )
    found = detections_on(scene, capture_pipeline.lid.name)
    assert not (Counter(truth.pieces_on_lid) - found)


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
