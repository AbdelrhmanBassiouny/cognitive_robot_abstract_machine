"""
Walking through the shipped captures, watching what the pipeline makes of each.

What each capture is detected *as* is measured in
:mod:`experiments_test.test_montessori_detection_on_captures`; these tests are about the
walk itself -- that every capture asked for is detected on, drawn, and that a key press
stops the walk.
"""

from __future__ import annotations

import pytest

from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.perception.viewer import (
    CameraFrameViewer,
    PerceptionWindow,
    QuitKey,
)
from experiments.montessori.perception.watch_captures import CaptureReview

from .dataset import montessori_capture_fixtures
from .test_montessori_viewer import KeyPressingDisplay

pytest_plugins = [montessori_capture_fixtures.__name__]

# %% the captures a walk is made over


@pytest.fixture
def two_captures() -> list[str]:
    """
    Two of the shipped captures, which is enough for a walk to have a second step.
    """
    return SceneCapture.names_in()[:2]


# %% walking them


def test_every_capture_asked_for_is_detected_on_and_drawn(
    capture_pipeline: MontessoriPerceptionPipeline, two_captures: list[str]
) -> None:
    display = KeyPressingDisplay()
    review = CaptureReview(
        pipeline=capture_pipeline,
        viewer=CameraFrameViewer(display=display),
        seconds_per_capture=0.0,
    )

    review.review(two_captures)

    assert list(review.scenes) == two_captures
    assert set(display.drawn) == set(PerceptionWindow)


def test_a_review_without_a_viewer_detects_without_drawing(
    capture_pipeline: MontessoriPerceptionPipeline, two_captures: list[str]
) -> None:
    review = CaptureReview(pipeline=capture_pipeline)

    review.review(two_captures[:1])

    assert list(review.scenes) == two_captures[:1]


def test_pressing_quit_stops_the_walk_where_it_stands(
    capture_pipeline: MontessoriPerceptionPipeline, two_captures: list[str]
) -> None:
    display = KeyPressingDisplay(key_presses=[QuitKey.Q])
    review = CaptureReview(
        pipeline=capture_pipeline, viewer=CameraFrameViewer(display=display)
    )

    review.review(two_captures)

    assert list(review.scenes) == two_captures[:1]
