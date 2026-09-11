"""
A sorting run watched by an event monitor and asked the frozen question set at its
answer step, so the trial it records carries ticks and scored queries.

Every scene here is built headless on the test dataset's own grasping robot, the way
:mod:`test_montessori_scenarios` builds its scenes.
"""

from __future__ import annotations

import pytest
from segmind.datastructures.events import DetectionEvent
from semantic_digital_twin.adapters.mujoco_video_recording import RecordedVideo

from experiments.episodes.episode import Episode
from experiments.montessori.scenarios import (
    LayoutArea,
    MontessoriSortingScenario,
    PieceLayout,
    TrialNotFilmedError,
)
from experiments.montessori.semantics import MontessoriShapeCategory
from experiments.montessori.watched_run import WatchedSortingRun
from experiments.questions.question import Memory

from .test_episode_recording import TrialsKeptInMemory
from .test_montessori_scenarios import (
    SEED,
    SyntheticGrasperHoldsAPiece,
    SyntheticGrasperSortsAPiece,
    SyntheticGrasperWatchesTheSceneStandStill,
    board_and_the_arm,
)

HELD_PIECE = MontessoriShapeCategory.CYLINDER
"""
The piece the in-gripper run holds.
"""


@pytest.fixture()
def area() -> LayoutArea:
    return LayoutArea.on_the_table_beside_the_board()


def watched(scenario: MontessoriSortingScenario) -> WatchedSortingRun:
    """
    One watched run of the given scenario, keeping its trials in memory.
    """
    return WatchedSortingRun(
        episode=Episode.from_run(scenario), records_trials=TrialsKeptInMemory()
    )


# %% which piece the script acts on


def test_the_static_run_acts_on_no_piece(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    assert scenario.acted_on_category is None


def test_the_held_piece_run_acts_on_the_piece_it_holds(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=HELD_PIECE,
    )

    assert scenario.acted_on_category is HELD_PIECE


# %% the run is watched and asked


def test_a_watched_run_records_the_monitors_ticks_on_the_trial(area):
    scenario = SyntheticGrasperHoldsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        held_category=HELD_PIECE,
    )
    run = watched(scenario)

    run.run(scenario)

    [trial] = run.records_trials.trials
    assert trial.ticks
    assert all(
        isinstance(event, DetectionEvent)
        for tick in trial.ticks
        for event in tick.events
    )
    assert [tick.moment for tick in trial.ticks] == sorted(
        tick.moment for tick in trial.ticks
    )


def test_a_watched_run_asks_the_working_memory_set_at_the_answer_step(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    run = watched(scenario)

    run.run(scenario)

    [trial] = run.records_trials.trials
    assert trial.queries
    assert {query.question.memory for query in trial.queries} == {Memory.WORKING}
    assert all(query.answered_correctly is not None for query in trial.queries)
    assert all(query.moment <= trial.duration for query in trial.queries)


def test_the_monitor_of_one_trial_is_stopped_before_the_next_starts(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    run = watched(scenario)
    run.repetitions = 2

    run.run(scenario)

    assert run.monitor is None
    assert len(run.records_trials.trials) == 2


# %% the video of a filmed trial


def test_a_filmed_scenario_hands_over_the_video_of_its_trial(area):
    scenario = SyntheticGrasperSortsAPiece(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        sorted_category=MontessoriShapeCategory.CUBE,
        filmed=True,
    )
    run = watched(scenario)
    run.film = scenario

    run.run(scenario)

    assert isinstance(run.video, RecordedVideo)
    assert run.video.frames


def test_a_scenario_that_was_not_filmed_has_no_video_to_hand_over(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )
    scenario.build_world()

    with pytest.raises(TrialNotFilmedError):
        scenario.video_of_the_trial()


# %% whether a viewer is opened


def test_a_scenario_runs_headless_unless_told_otherwise(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
    )

    scenario.build_world()

    assert scenario.simulation.headless is True


def test_a_scenario_told_to_show_itself_carries_that_to_its_simulation(area):
    scenario = SyntheticGrasperWatchesTheSceneStandStill(
        layout=PieceLayout.randomized(seed=SEED, area=area),
        world_builder=board_and_the_arm(),
        headless=False,
    )

    scenario.build_world()

    assert scenario.simulation.headless is False
