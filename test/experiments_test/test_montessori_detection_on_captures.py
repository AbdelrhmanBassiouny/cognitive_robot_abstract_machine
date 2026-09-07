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

import pytest
from typing_extensions import List

from experiments.montessori.hole_geometry import detect_hole_footprints
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
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


TABLE_GHOSTS_STILL_REPORTED: List[str] = ["non_inserted_objects"]
"""
The captures where a piece on the lid is still read as one on the table.

What a raised thing hides from the camera is measured off the board as it was detected,
and the board's own orientation comes from the holes found in its lid. In this capture
alone the board is reported turned twenty-two degrees from where the other five put it,
about the same centre, so the stretch of table it is taken to stand in front of is
turned with it.
"""


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
    if capture.name in TABLE_GHOSTS_STILL_REPORTED:
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=(
                    "The board is read as turned away from where it stands, so what it "
                    "hides is turned with it; owned by the plan item "
                    "holes-fitted-like-pieces."
                ),
            )
        )
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
