"""
Tests for :mod:`experiments.tracy_experiments.montessori.scene_builder`: the scene a run
on Tracy is set in is either built from Tracy's description or stood in the world the
robot publishes by its own camera, and a run on the robot over the perceived scene is
watched, asked and recorded without any simulation -- measured on the capture whose
table was laid out with a tape, in the world Tracy's own description gives.
"""

from __future__ import annotations

import numpy as np
import pytest
from coraplex.datastructures.enums import ExecutionType
from semantic_digital_twin.adapters.multi_sim import MultiSimSynchronizer
from semantic_digital_twin.robots.tracy import Tracy
from semantic_digital_twin.spatial_types.spatial_types import Vector3
from semantic_digital_twin.world import World

from experiments.episodes.episode import Episode
from experiments.montessori.exceptions import WorldHoldsNoSuchRobot
from experiments.montessori.perception.captures import SceneCapture
from experiments.montessori.perception.node import pipeline_of
from experiments.montessori.perception.recorded_setup import lab_board
from experiments.montessori.perception.scene_publishing import PerceivedScene
from experiments.montessori.perception.scene_source import RecordedFrame
from experiments.montessori.pieces import FULL_SIZE_PIECES, SMALLER_PIECES
from experiments.montessori.scenarios import (
    HOW_FAR_A_MOVED_HOLE_GOES,
    LayoutAsFound,
    PieceShoved,
    RealScene,
    SortingScene,
    SortingStep,
    TracyWatchesTheSceneStandStill,
)
from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingBoard,
)
from experiments.montessori.watched_run import WatchedSortingRun
from experiments.questions.question import Memory
from experiments.scenarios.runner import RecordedOperatorPrompt
from experiments.scenarios.trial import TrialOutcome
from experiments.tracy_experiments.equipment import parse_tracy
from experiments.tracy_experiments.montessori.scene_builder import (
    TracyLookingAtItsOwnTable,
    TracyOnItsOwnTable,
)

from .dataset.montessori_capture_truths import CAPTURE_TRUTHS, CaptureTruth
from .dataset.synthetic_grasping_robot import SyntheticGraspingRobot
from .test_episode_recording import TrialsKeptInMemory
from .test_montessori_detection_on_captures import TAPE_TOLERANCE

MEASURED_CAPTURE = "scaled_pieces_in_a_row"
"""
The capture whose pieces and board were measured with a tape, taken by Tracy's own
camera.
"""

SHOVED_PIECE = MontessoriShapeCategory.CUBE
"""
The piece the person at the table is asked to move.
"""

A_SHOVE = PieceShoved(
    step=SortingStep.SETTLE,
    category=SHOVED_PIECE,
    displacement=Vector3(HOW_FAR_A_MOVED_HOLE_GOES, 0.0, 0.0),
)
"""
The perturbation a run on the robot asks the person for.
"""


@pytest.fixture
def truth() -> CaptureTruth:
    """
    What the measured capture really holds.
    """
    return CAPTURE_TRUTHS[MEASURED_CAPTURE]


@pytest.fixture
def published_world() -> World:
    """
    A world standing in for the one the robot publishes: Tracy on its own table, as its
    description gives it, holding no board and no pieces.
    """
    world = parse_tracy()
    Tracy.from_world(world)
    return world


@pytest.fixture
def look(published_world: World) -> RecordedFrame:
    """
    The measured capture, looked at afresh for every request through the pipeline the
    live node builds on the published world.
    """
    return RecordedFrame(
        pipeline=pipeline_of(published_world),
        frame=SceneCapture.load(MEASURED_CAPTURE).to_frame(),
    )


@pytest.fixture
def perceived(published_world: World, look: RecordedFrame) -> TracyLookingAtItsOwnTable:
    """
    Tracy's table as its camera finds it on the measured capture.
    """
    return TracyLookingAtItsOwnTable(
        scene=PerceivedScene(
            world=published_world, look=look, described_board=lab_board()
        )
    )


def _distance_on_the_table(stands_at: np.ndarray, x: float, y: float) -> float:
    """
    :return: How far a position lies from a place on the table, in metres.
    """
    return float(np.hypot(stands_at[0] - x, stands_at[1] - y))


# %% the scene built from Tracy's description


@pytest.mark.parametrize("piece_set", [FULL_SIZE_PIECES, SMALLER_PIECES])
def test_the_built_scene_stands_the_set_it_is_told_on_tracys_own_table(piece_set):
    builder = TracyOnItsOwnTable(piece_set=piece_set)

    world = builder.build(Tracy)

    scene = SortingScene(world)
    assert type(scene.robot) is Tracy
    assert builder.piece_set is piece_set
    assert scene.categories == set(piece_set.by_category)
    for category in scene.categories:
        standing_on = (
            scene.body_of(category)
            .collision.as_bounding_box_collection_in_frame(world.root)
            .bounding_box()
        )
        assert float(standing_on.min_z) == pytest.approx(builder.table_top_z)


def test_the_built_scene_is_the_full_size_set_unless_told_otherwise():
    assert TracyOnItsOwnTable().piece_set is FULL_SIZE_PIECES


# %% the scene Tracy's camera finds


def test_the_perceived_scene_is_the_published_world_with_what_the_look_found(
    perceived: TracyLookingAtItsOwnTable, published_world: World, truth: CaptureTruth
):
    """
    The world handed over is the one the robot publishes, now holding the board and one
    piece per piece on the table, each within the tape's tolerance of where the tape
    put it.
    """
    world = perceived.build(Tracy)

    assert world is published_world
    assert ShapeSortingBoard.held_by(world) is perceived.scene.board
    pieces = world.get_semantic_annotations_by_type(MontessoriShape)
    assert pieces == perceived.scene.pieces
    assert sorted(piece.shape_category for piece in pieces) == sorted(
        truth.pieces_on_table
    )
    for measured in truth.tape_measured:
        [piece] = [
            piece for piece in pieces if piece.shape_category is measured.category
        ]
        stands_at = piece.root.global_transform.to_position().to_np()
        assert (
            _distance_on_the_table(stands_at, measured.place.x, measured.place.y)
            <= TAPE_TOLERANCE
        ), (measured, stands_at)


def test_the_perceived_scene_says_which_table_and_which_set_its_pieces_are_of(
    perceived: TracyLookingAtItsOwnTable, look: RecordedFrame
):
    assert perceived.table_top_z == pytest.approx(look.pipeline.table.height)
    assert perceived.piece_set is look.pipeline.pieces


def test_the_perceived_scene_is_looked_at_afresh_every_time_it_is_built(
    perceived: TracyLookingAtItsOwnTable, published_world: World
):
    """
    The second build stands the pieces again -- the first build's are gone from the
    world -- and keeps the board the first build found.
    """
    perceived.build(Tracy)
    board, first = perceived.scene.board, list(perceived.scene.pieces)

    world = perceived.build(Tracy)

    assert perceived.scene.board is board
    assert world.get_semantic_annotations_by_type(MontessoriShape) == (
        perceived.scene.pieces
    )
    assert len(perceived.scene.pieces) == len(first)
    assert not {piece.root for piece in first} & set(world.bodies)


def test_the_perceived_scene_refuses_a_robot_the_published_world_does_not_hold(
    perceived: TracyLookingAtItsOwnTable, published_world: World
):
    with pytest.raises(WorldHoldsNoSuchRobot) as refused:
        perceived.build(SyntheticGraspingRobot)

    assert refused.value.robot_type is SyntheticGraspingRobot
    assert refused.value.world is published_world
    assert published_world.get_semantic_annotations_by_type(MontessoriShape) == []


def test_the_layout_found_on_tracys_table_is_where_the_tape_put_the_pieces(
    perceived: TracyLookingAtItsOwnTable, truth: CaptureTruth
):
    world = perceived.build(Tracy)

    found = LayoutAsFound().stand_in(world, perceived)

    assert sorted(found.categories) == sorted(truth.pieces_on_table)
    for measured in truth.tape_measured:
        placement = found.placement_of(measured.category)
        assert placement.piece is truth.piece_set.by_category[measured.category]
        assert (
            _distance_on_the_table(
                np.array([placement.x, placement.y]),
                measured.place.x,
                measured.place.y,
            )
            <= TAPE_TOLERANCE
        )


# %% a run on the robot over the perceived scene


def _run_on_the_robot(
    perceived: TracyLookingAtItsOwnTable, repetitions: int = 1
) -> tuple[TracyWatchesTheSceneStandStill, WatchedSortingRun, RecordedOperatorPrompt]:
    """
    The static run on the robot, set in the perceived scene, watched and recorded in
    memory, with nobody at the table.
    """
    scenario = TracyWatchesTheSceneStandStill(
        layout=LayoutAsFound(),
        world_builder=perceived,
        execution_type=ExecutionType.REAL,
    )
    prompt = RecordedOperatorPrompt()
    run = WatchedSortingRun(
        episode=Episode.from_run(scenario),
        records_trials=TrialsKeptInMemory(),
        operator_prompt=prompt,
        repetitions=repetitions,
    )
    return scenario, run, prompt


def test_a_run_on_the_robot_is_asked_of_the_perceived_scene_without_a_simulation(
    perceived: TracyLookingAtItsOwnTable, published_world: World
):
    scenario, run, _ = _run_on_the_robot(perceived)

    run.run(scenario)

    assert type(scenario.physics) is RealScene
    assert scenario.physics.world is published_world
    assert (
        MultiSimSynchronizer.all_callbacks_of_this_type_from_world(published_world)
        == []
    )
    assert run.episode.execution_type is ExecutionType.REAL
    [trial] = run.records_trials.trials
    assert trial.outcome is TrialOutcome.SUCCEEDED
    assert trial.queries
    assert {query.question.memory for query in trial.queries} == {Memory.WORKING}
    assert all(query.answered_correctly is not None for query in trial.queries)


def test_a_shove_on_the_robot_is_asked_of_the_person_and_disturbs_the_scene(
    perceived: TracyLookingAtItsOwnTable,
):
    scenario, run, prompt = _run_on_the_robot(perceived)

    run.run(scenario, perturbations=[A_SHOVE])

    assert prompt.shown == [A_SHOVE.instruction_for_a_person()]
    [trial] = run.records_trials.trials
    assert trial.outcome is TrialOutcome.FAILED
    stood_at = scenario.starting_layout.placement_of(SHOVED_PIECE)
    stands_at = SortingScene(scenario.physics.world).position_of(SHOVED_PIECE)
    assert float(stands_at.x) - stood_at.x == pytest.approx(HOW_FAR_A_MOVED_HOLE_GOES)
    assert float(stands_at.y) - stood_at.y == pytest.approx(0.0)


def test_every_trial_on_the_robot_looks_at_the_table_afresh(
    perceived: TracyLookingAtItsOwnTable, published_world: World
):
    """
    A shove in the first trial does not carry into the second: the second trial's
    scene is stood by a fresh look, so its layout is the tape's again.
    """
    scenario, run, prompt = _run_on_the_robot(perceived, repetitions=2)

    run.run(scenario, perturbations=[A_SHOVE])

    assert len(prompt.shown) == 2
    first, second = run.records_trials.trials
    assert (first.outcome, second.outcome) == (
        TrialOutcome.FAILED,
        TrialOutcome.FAILED,
    )
    assert len(published_world.get_semantic_annotations_by_type(MontessoriShape)) == (
        len(scenario.starting_layout.placements)
    )
    stood_at = scenario.starting_layout.placement_of(SHOVED_PIECE)
    truth = CAPTURE_TRUTHS[MEASURED_CAPTURE]
    [measured] = [
        measured
        for measured in truth.tape_measured
        if measured.category is SHOVED_PIECE
    ]
    assert (
        _distance_on_the_table(
            np.array([stood_at.x, stood_at.y]), measured.place.x, measured.place.y
        )
        <= TAPE_TOLERANCE
    )
