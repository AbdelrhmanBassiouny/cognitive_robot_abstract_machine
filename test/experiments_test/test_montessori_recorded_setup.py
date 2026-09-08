"""
The setup the shipped captures were made on, read as a world a statement can be written
over.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.montessori.hole_geometry import HOLE_NAME_BY_CATEGORY
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.detections import (
    MontessoriBoardDetection,
    MontessoriDetection,
)
from experiments.montessori.perception.recorded_setup import (
    board_holes_in,
    perception_pipeline,
    recorded_world,
)
from experiments.montessori.perception.step_by_step import DEMONSTRATION_CAPTURE
from semantic_digital_twin.world import World
from semantic_digital_twin.world_description.world_entity import Body

# %% the holes a look puts in the world


@pytest.fixture
def recorded_scene_world() -> World:
    """
    The world the shipped captures' own setup describes.
    """
    return recorded_world()


@pytest.fixture
def capture_board(recorded_scene_world: World) -> MontessoriBoardDetection:
    """
    The board as the demonstration's capture shows it.
    """
    pipeline = perception_pipeline(recorded_scene_world)
    return pipeline.board_in(SceneCapture.load(DEMONSTRATION_CAPTURE).to_frame())


def how_far_apart(body: Body, detection: MontessoriDetection) -> float:
    """
    :param body: The body a hole was placed as.
    :param detection: What a look found there.
    :return: How far apart the two stand, in metres.
    """
    return float(
        np.linalg.norm(
            body.global_pose.to_position().to_np()[:3]
            - detection.pose.to_position().to_np()[:3]
        )
    )


def test_a_hole_body_stands_where_the_look_found_that_hole(
    recorded_scene_world: World, capture_board: MontessoriBoardDetection
):
    """
    A statement naming a hole is answered about the body placed for it, so that body has
    to stand where the look put the hole rather than where the board's own mesh would
    put it at a size the board is not.
    """
    placed = board_holes_in(recorded_scene_world, capture_board)

    assert {
        HOLE_NAME_BY_CATEGORY[hole.category]: how_far_apart(
            placed[HOLE_NAME_BY_CATEGORY[hole.category]], hole
        )
        for hole in capture_board.holes
        if hole.category in HOLE_NAME_BY_CATEGORY
    } == pytest.approx(dict.fromkeys(HOLE_NAME_BY_CATEGORY.values(), 0.0), abs=1e-9)
